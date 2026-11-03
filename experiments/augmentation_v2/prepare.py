"""Prepare exact graph and frozen CodeBERT views, then rerun shortcut controls."""
import hashlib,json,sys
from pathlib import Path
from collections import Counter
import torch
from transformers import AutoTokenizer,AutoModel

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"pipeline"),str(ROOT/"pipeline/provenance"),str(ROOT/"experiments/precision_v1")]
from build import graph_from_json
from embed_rtl import embed,MODEL,MODEL_REVISION
from lofo_graph_baselines import stats,wl,fit_predict
from bootstrap import summary

RUN=ROOT/"runs/augmentation_v2"
OUT=ROOT/"data/augmentation_v2"
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False))
def rank(a,b):return float(a>b)+.5*(a==b)

def main():
    torch.set_num_threads(4)
    rows=[]
    for r in read(ROOT/"data/overlap_six_v1/manifest.json")["records"]:
        rows.append(dict(r,cohort="baseline",mapped=f"runs/overlap_v1/{r['host']}/{r['variant']}/yosys.json"))
    unavailable=read(ROOT/"data/precision_v1/admission.json")["graph_unavailable"]
    for r in read(ROOT/"data/precision_v1/manifest.json")["records"]:
        if r["edit_kind"]!="guarded_output_fallback" and r["host"] not in unavailable:
            rows.append(dict(r,cohort="native",mapped=f"runs/precision_v1/hosts/{r['host']}/{r['variant']}/yosys.json"))
    for r in read(ROOT/"data/transfer_v1/intake.json")["records"]:
        if r["variant"]!="benign":rows.append(dict(r,cohort="four_projects"))
    for r in read(OUT/"intake.json")["records"]:
        rows.append(dict(r,cohort="external_authored" if r["host"]=="RS232" else "four_projects"))
    for r in read(ROOT/"runs/rtl_expansion_v1/manifest.json")["records"]:
        h,s=r["benchmark"],r["side"]
        folder="expansion_graphs" if h.startswith("memctrl") else "expansion_pic_graphs"
        rows.append(dict(host=h.split("-")[0],benchmark=h,variant=s,cohort="test",sources=r["sources"],
            mapped=f"runs/{folder}/{h}/{s}/yosys.json",embedding=f"runs/rtl_expansion_v1/{h}_{s}.pt",
            top="mc_top" if h.startswith("memctrl") else "pic_16f84_core"))
    tokenizer=AutoTokenizer.from_pretrained(MODEL,revision=MODEL_REVISION,local_files_only=True)
    encoder=AutoModel.from_pretrained(MODEL,revision=MODEL_REVISION,local_files_only=True).eval()
    cache=RUN/"embeddings";cache.mkdir(exist_ok=True)
    dest=RUN/"prepared";dest.mkdir(exist_ok=True)
    manifest=[];controls={};chunk_cache={}
    for i,r in enumerate(rows):
        label=int(r["variant"] not in ("clean","benign"))
        for p,digest in r["sources"].items():
            if sha(ROOT/p)!=digest:raise ValueError(p)
        mapped=ROOT/r["mapped"]
        expected=r.get("mapped_sha256",r.get("mapped_json_sha256"))
        if expected and sha(mapped)!=expected:raise ValueError(str(mapped))
        doc=read(mapped)
        graph,meta=graph_from_json(doc,r["top"],r["host"],label)
        # Same fixed input transformation for all models and cohorts.
        graph.x[:,-4:]=torch.log1p(graph.x[:,-4:].clamp(min=0))
        files=[ROOT/p for p in sorted(r["sources"]) if p.endswith(".v")]
        text="\n\n".join(p.read_text(errors="replace").replace("\r\n","\n") for p in files)
        text_hash=hashlib.sha256(text.encode()).hexdigest()
        embedding=ROOT/r["embedding"] if "embedding" in r else cache/(text_hash+".pt")
        encoded=tokenizer(text,truncation=True,max_length=512,stride=50,return_overflowing_tokens=True,padding="max_length",return_attention_mask=True)
        keys=[tuple(ids) for ids in encoded["input_ids"]]
        if not embedding.exists():
            missing=list(dict.fromkeys(k for k in keys if k not in chunk_cache))
            with torch.inference_mode():
                for start in range(0,len(missing),8):
                    part=missing[start:start+8]
                    ids=torch.tensor(part,dtype=torch.long)
                    mask=(ids!=tokenizer.pad_token_id).long()
                    hidden=encoder(input_ids=ids,attention_mask=mask).last_hidden_state
                    weight=mask.unsqueeze(-1).to(hidden.dtype)
                    vectors=((hidden*weight).sum(1)/weight.sum(1).clamp(min=1)).cpu().float()
                    for k,v in zip(part,vectors):chunk_cache[k]=v.clone()
            torch.save(torch.stack([chunk_cache[k] for k in keys]),embedding)
        rtl=torch.load(embedding,weights_only=True)
        for k,v in zip(keys,rtl):chunk_cache.setdefault(k,v.clone())
        bench=r.get("benchmark",r["host"])
        key=f"{r['cohort']}_{bench}_{r['variant']}"
        path=dest/(key+".pt")
        torch.save(dict(graph=graph,rtl=rtl,label=label,host=r["host"],benchmark=bench,variant=r["variant"],cohort=r["cohort"]),path)
        ports=doc["modules"][r["top"]]["ports"]
        controls[key]=dict(host=r["host"],variant=r["variant"],label=label,cohort=r["cohort"],
            scalars=dict(characters=len(text),lines=len(text.splitlines()),cells=graph.num_nodes,edges=graph.num_edges),
            ports=sorted((k,v["direction"],len(v["bits"])) for k,v in ports.items()),
            stats=stats(graph),wl=wl(graph),hist=torch.bincount(graph.x[:,:-4].argmax(1),minlength=16).float())
        manifest.append(dict(key=key,file=path.relative_to(ROOT).as_posix(),sha256=sha(path),host=r["host"],cohort=r["cohort"],
                             variant=r["variant"],label=label,source_sha256=r["sources"],mapped_sha256=sha(mapped),embedding_sha256=sha(embedding),
                             nodes=graph.num_nodes,chunks=len(rtl)))
        print(i+1,len(rows),key,graph.num_nodes,len(rtl),flush=True)
    save(OUT/"manifest.json",dict(records=manifest,model_revision=MODEL_REVISION))
    torch.save(controls,RUN/"controls.pt")
    for cohort in ("four_projects","external_authored"):
        subset=[v for v in controls.values() if v["cohort"]==cohort]
        hosts=sorted({r["host"] for r in subset})
        result={}
        for scalar in subset[0]["scalars"]:
            result[scalar]=summary({h:sum(rank(a["scalars"][scalar],b["scalars"][scalar]) for a in subset if a["host"]==h and a["label"]
                for b in subset if b["host"]==h and not b["label"])/(sum(r["host"]==h and r["label"] for r in subset)*sum(r["host"]==h and not r["label"] for r in subset)) for h in hosts})
        if len(hosts)>1:
            for key in ("stats","wl","hist"):
                ranks={}
                for h in hosts:
                    tr=[r for r in subset if r["host"]!=h];te=[r for r in subset if r["host"]==h]
                    scores=fit_predict(torch.stack([r[key] for r in tr]),torch.tensor([r["label"] for r in tr]),torch.ones(len(tr)),torch.stack([r[key] for r in te]),42)
                    ranks[h]=sum(rank(p,q) for r,p in zip(te,scores) if r["label"] for t,q in zip(te,scores) if not t["label"])/(sum(r["label"] for r in te)*sum(not r["label"] for r in te))
                result[key]=summary(ranks)
        signatures={h:len({tuple(map(tuple,r["ports"])) for r in subset if r["host"]==h}) for h in hosts}
        save(OUT/(cohort+"_shortcuts.json"),dict(controls=result,port_signature_counts=signatures,
            hard_stops=[k for k,v in result.items() if max(v["mean"],1-v["mean"])>=.90],
            scope="host-held-out fitted controls; one external host cannot support a fitted host-held-out probe"))
    print("prepared",len(rows),flush=True)
if __name__=="__main__":main()
