"""Apply the precommitted controls without fitting a detector."""
from collections import Counter, defaultdict
from functools import lru_cache
from itertools import product
import json
import re
import sys

import numpy as np
import torch
from transformers import AutoTokenizer

from build_cohort import DATA, FAMILIES, HERE, ROOT, RUN, SIDES, digest, relative, report

sys.path.insert(0,str(HERE.parent/"tier12_v3"))
from typed_pairs import distinguish, graph_view, provenance
sys.path.insert(0,str(HERE.parent/"matched_insertion_v3"))
import controls as motifs
from lofo_graph_baselines import fit_predict, stats, wl
motifs.OUT=RUN

KEYWORDS=set("always and assign automatic begin buf case casez casex default else end endcase endfunction endmodule endtask for function generate endgenerate if initial inout input integer localparam module negedge or output parameter posedge reg signed task wire while xor".split())
TOKENS=re.compile(r"(?:\d+)?'[sS]?[hHbBoOdD][a-fA-F0-9_xXzZ?]+|[a-zA-Z_$][\w$]*|\d+|===|!==|>>>|<<|>>|<=|>=|==|!=|&&|\|\||\S")
TOKENIZER=AutoTokenizer.from_pretrained("microsoft/codebert-base",revision="3b0952feddeffad0063f274080e3c23d75e7eb39",local_files_only=True)


def read(p):
    return json.loads(p.read_text())


@lru_cache(maxsize=256)
def lexical(paths):
    text="\n".join(p.read_text(errors="replace") for p in paths)
    body=re.sub(r"/\*.*?\*/|//[^\n]*","",text,flags=re.S)
    words=re.findall(r"[A-Za-z_][A-Za-z_0-9]*",body)
    tokens=TOKENS.findall(body)
    norm=" ".join(
        "id" if (t[0].isalpha() or t[0] in "_$") and t not in KEYWORDS else t for t in tokens)
    def windows(s):
        return len(TOKENIZER(s,truncation=True,max_length=512,stride=50,return_overflowing_tokens=True)["input_ids"])
    return dict(characters=len(text),lines=len(text.splitlines()),windows=windows(text),
                neutral_names=sum(bool(re.fullmatch(r"v\d+",w)) for w in words)/max(len(words),1),
                comment_fraction=1-len(body)/max(len(text),1),normalized_tokens=len(tokens),
                normalized_characters=len(norm),normalized_windows=windows(norm))


def rank(a,b):
    return float(a>b)+0.5*(a==b)


def summary(by_host):
    values=list(by_host.values())
    draws=[np.mean(s) for s in product(values,repeat=len(values))]
    lo,hi=np.quantile(draws,[0.025,0.975],method="inverted_cdf")
    return dict(mean=float(np.mean(values)),ci95=[lo,hi],by_host=by_host)


def collect(row):
    h,s=row["host"],row["variant"]
    paths=tuple(ROOT/p for p in row["sources"])
    if any(digest(p)!=row["sources"][relative(p)] for p in paths):
        raise ValueError("Source hash mismatch")
    path=RUN/h/s/"yosys.json"
    if digest(path)!=row["mapped_json_sha256"]: raise ValueError("Mapped hash mismatch")
    doc=read(path)
    graph,meta=provenance.graph_from_json(doc,row["top"],h,row["label"])
    scalar=dict(lexical(paths),cells=graph.num_nodes,edges=graph.num_edges)
    hist=Counter(meta["node_types"])
    features=dict(metadata=torch.tensor([scalar[k] for k in ("characters","lines","windows")]).float(),
                  gate_hist=graph.x[:,:-4].sum(0),graph_stats=stats(graph),wl2=wl(graph),wl8=wl(graph,rounds=8),
                  input_fanout=motifs.input_fanout_motifs(row),output_xor=motifs.output_xor_motifs(row),
                  output_cone=motifs.output_cone_equivalence(row))
    # The first gate channels in each typed cell node are the unchanged gate vocabulary.
    # A different histogram already certifies distinct typed node features.
    return scalar,hist,features


def typed_check(h,neg,items):
    a,b=items[h,neg],items[h,"trojan"]
    if not torch.equal(a[2]["gate_hist"],b[2]["gate_hist"]):
        return "distinct_gate_feature_histograms"
    # The typed builder adds a distinct vertex for each binary constant.
    # Its forward degree counts every input-pin use, including multiplicity.
    degrees=[]
    for s in (neg,"trojan"):
        module=read(RUN/h/s/"yosys.json")["modules"][FAMILIES[h]]
        degrees.append(Counter(bit for cell in module["cells"].values()
                               if cell["type"].lower() not in provenance.CELL_EXCLUDE
                               for pin,bits in cell["connections"].items()
                               if cell["port_directions"][pin]=="input"
                               for bit in bits if isinstance(bit,str) and bit in ("0","1")))
    if degrees[0]!=degrees[1]:
        return "distinct_typed_constant_vertex_degrees"
    graphs=[]
    for s in (neg,"trojan"):
        doc=read(RUN/h/s/"yosys.json")
        graph,meta=provenance.graph_from_json(doc,FAMILIES[h],h,0)
        graphs.append(graph_view(doc,dict(meta,top=FAMILIES[h]),graph))
    return "distinct_typed_features_or_edges" if distinguish(*graphs)["distinguished"] else "inconclusive"


def probe_cohort(hosts,items):
    scores={}
    for neg in ("clean","benign"):
        measures={}
        for k in items[hosts[0],neg][0]:
            measures[k]=summary({h:rank(items[h,"trojan"][0][k],items[h,neg][0][k]) for h in hosts})
        for k in items[hosts[0],neg][2]:
            folds={}
            for index,h in enumerate(hosts):
                train=[(other,s) for other in hosts if other!=h for s in (neg,"trojan")]
                test=[(h,s) for s in (neg,"trojan")]
                score=fit_predict(torch.stack([items[key][2][k] for key in train]),
                    torch.tensor([int(s=="trojan") for _,s in train]),torch.ones(len(train)),
                    torch.stack([items[key][2][k] for key in test]),42+index)
                folds[h]=rank(score[1],score[0])
            measures[k]=summary(folds)
        scores[neg]=measures
    return scores


def origin(cohorts,items):
    native=defaultdict(lambda:defaultdict(list))
    for r in read(ROOT/"runs/typed_fusion_v1/manifest.json")["records"]:
        bench,side=r["benchmark"],r["side"]
        paths,_=provenance.source_files(bench,side)
        native[side][bench.split("-")[0]].append(dict(lexical(tuple(paths)),cells=r["cells"]))
    results={}
    for name,hosts in cohorts.items():
        for comparison in (["same_family","other_families"] if name=="shared" else ["other_families"]):
            group={}
            for side in SIDES:
                families=native["trojan" if side=="trojan" else "clean"]
                metrics={}
                for k in next(iter(families.values()))[0]:
                    by_host={}
                    for h in hosts:
                        refs=[v for fam,v in families.items() if (fam==h)==(comparison=="same_family")]
                        value=items[h,side][0][k]
                        by_host[h]=float(np.mean([np.mean([rank(value,r[k]) for r in members]) for members in refs]))
                    metrics[k]=summary(by_host)
                group[side]=metrics
            results[name+"_"+comparison]=group
    return results


def main():
    torch.set_num_threads(1)
    manifest=read(DATA/"manifest.json")
    if manifest["protocol_sha256"]!=digest(HERE/"protocol.json"): raise ValueError("Protocol changed")
    rows=manifest["records"]
    items={}
    for row in rows:
        items[row["host"],row["variant"]]=collect(row)
        print("controls",row["host"],row["variant"],flush=True)
    cohorts={c:sorted({r["host"] for r in rows if r["cohort"]==c}) for c in ("tier3","shared")}
    overlap={}
    for h in FAMILIES:
        pos=items[h,"trojan"][1]
        overlap[h]={}
        for neg in ("clean","benign"):
            hist=items[h,neg][1]
            delta={k:pos[k]-hist[k] for k in pos.keys()|hist.keys() if pos[k]!=hist[k]}
            distance=sum(map(abs,delta.values()))/sum(hist.values())
            overlap[h][neg]=dict(relative_L1=distance,passed=distance<=0.05,delta=delta,
                                 typed_view=typed_check(h,neg,items))
    scores={c:probe_cohort(hosts,items) for c,hosts in cohorts.items()}
    sources=origin(cohorts,items)
    coverage={c:{k:sum(bool(items[h,s][2][k].abs().sum()) for h in hs for s in SIDES)
                 for k in ("input_fanout","output_xor","output_cone")} for c,hs in cohorts.items()}
    failures=[r["host"]+"/"+r["variant"] for r in rows if not r["source_and_mapped_match"]]
    cuts=[(domain,cohort,side,k) for domain,groups in (("class",scores),("origin",sources))
          for cohort,g in groups.items() for side,metrics in g.items() for k,m in metrics.items()
          if max(m["mean"],1-m["mean"])>=0.90]
    margins=[(domain,cohort,side,k) for domain,groups in (("class",scores),("origin",sources))
             for cohort,g in groups.items() for side,metrics in g.items() for k,m in metrics.items()
             if (domain=="origin" or k in items[rows[0]["host"],"clean"][0])
             and (m["ci95"][0]<0.30 or m["ci95"][1]>0.70)]
    hold=bool(failures or cuts or margins or len(FAMILIES)<6 or any(
        not v["passed"] or v["typed_view"]=="inconclusive" for g in overlap.values() for v in g.values()))
    status="hold" if hold else "eligible_for_development_training"
    report(DATA/"admission.json",dict(status=status,source_manifest_sha256=digest(DATA/"manifest.json"),
           frozen_protocol_sha256=digest(HERE/"protocol.json"),overlap=overlap,paired_controls=scores,
           origin_controls=sources,coverage=coverage,semantic_failures=failures,hard_stops=cuts,
           outside_equivalence_margin=margins,independent_families=len(FAMILIES),minimum_families=6,
           measurements=[dict(host=h,variant=s,**v[0],gates=v[1]) for (h,s),v in items.items()],
           uncertainty="Percentile host bootstrap conditional on the fixed reference panel and held-out predictions. Two families per cohort."))
    report(ROOT/"data/integrated/ver2_tier3_catalog.json",dict(previous_catalog="data/integrated/ver2_tier12_v3_catalog.json",
        previous_matched_pilot="data/trusthub_matched_v1/validation.json",manifest=relative(DATA/"manifest.json"),
        sha256=digest(DATA/"manifest.json"),admission=relative(DATA/"admission.json"),status=status,
        tier3_rows=6,shared_host_rows=6,admitted_records=0 if hold else len(rows),trained=False))
    print(status,len(cuts),"hard stops",flush=True)


if __name__=="__main__":
    main()
