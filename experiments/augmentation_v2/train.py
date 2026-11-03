"""Train the actual repository GNN and cross-attention fusion on matched external tests."""
import json,sys,time,hashlib
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"pipeline"),str(ROOT/"experiments/precision_v1")]
from models import GNNOnly,CrossAttentionFusion
from metrics import auroc,summarize
from bootstrap import summary
RUN=ROOT/"runs/augmentation_v2"
OUT=ROOT/"data/augmentation_v2"

def read(p):return json.loads(p.read_bytes())
def save(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def evaluate(net,rows):
    net.eval();predictions=[]
    with torch.no_grad():
        for r in rows:
            p=float(net(r["graph"],r["rtl"])["logits"].softmax(-1)[0,1])
            if not np.isfinite(p):raise ValueError("Nonfinite prediction")
            predictions.append(dict(host=r["host"],benchmark=r["benchmark"],variant=r["variant"],label=r["label"],probability=p))
    byhost={}
    for h in sorted({r["host"] for r in rows}):
        ps=[p for p in predictions if p["host"]==h]
        byhost[h]=summarize([p["label"] for p in ps],[int(p["probability"]>=.5) for p in ps],[p["probability"] for p in ps])
    pooled=summarize([r["label"] for r in predictions],[int(r["probability"]>=.5) for r in predictions],[r["probability"] for r in predictions])
    return dict(pooled=pooled,hosts=byhost,host_auc=summary({h:r["auroc"] for h,r in byhost.items()}),predictions=predictions)

def main():
    torch.set_num_threads(4)
    protocol=read(ROOT/"experiments/augmentation_v2/protocol.json")
    manifest=read(OUT/"manifest.json")
    samples=[]
    for row in manifest["records"]:
        p=ROOT/row["file"]
        if sha(p)!=row["sha256"]:raise ValueError(str(p))
        samples.append(torch.load(p,weights_only=False,map_location="cpu"))
    test=[r for r in samples if r["cohort"]=="test"]
    trainall=[r for r in samples if r["cohort"]!="test"]
    assert not {r["host"] for r in test}&{r["host"] for r in trainall}
    basehash={d for r in manifest["records"] if r["cohort"]!="test" for d in r["source_sha256"].values()}
    testhash={d for r in manifest["records"] if r["cohort"]=="test" for d in r["source_sha256"].values()}
    # Identical ancillary files (e.g. headers) do not establish shared design lineage.
    if basehash&testhash:print("shared source file hashes",len(basehash&testhash),flush=True)
    results=[]
    for seed in protocol["seeds"]:
        for arm,constructor in (("gnn",GNNOnly),("fusion",CrossAttentionFusion)):
            for condition in ("baseline","baseline_matched_updates","augmented"):
                target=RUN/f"{arm}_{condition}_{seed}.json"
                if target.exists():
                    results.append(read(target));continue
                train=[r for r in trainall if condition=="augmented" or r["cohort"]=="baseline"]
                counts=Counter((r["host"],r["label"]) for r in train)
                weights=[len(train)/(len({r["host"] for r in train})*2*counts[r["host"],r["label"]]) for r in train]
                torch.manual_seed(seed)
                model=constructor()
                opt=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-3)
                start=time.monotonic()
                losses=[]
                target_updates=len(trainall)*protocol["epochs"] if condition=="baseline_matched_updates" else len(train)*protocol["epochs"]
                epochs_to_run=(target_updates+len(train)-1)//len(train)
                updates=0
                for epoch in range(epochs_to_run):
                    model.train();total=0.
                    for idx in torch.randperm(len(train)).tolist():
                        if updates>=target_updates:break
                        r=train[idx];opt.zero_grad(set_to_none=True)
                        logits=model(r["graph"],r["rtl"])["logits"]
                        loss=F.cross_entropy(logits,torch.tensor([r["label"]]))*weights[idx]
                        if not torch.isfinite(loss):raise ValueError("Nonfinite loss")
                        loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step()
                        total+=float(loss.detach());updates+=1
                    losses.append(total/len(train))
                    print(arm,condition,seed,epoch+1,round(losses[-1],4),round(time.monotonic()-start,1),flush=True)
                score=evaluate(model,test)
                result=dict(arm=arm,condition=condition,seed=seed,epochs=epochs_to_run,train_circuits=len(train),
                     train_hosts=len({r["host"] for r in train}),updates=updates,losses=losses,
                     elapsed_seconds=time.monotonic()-start,metrics=score,manifest_sha256=sha(OUT/"manifest.json"))
                torch.save(model.state_dict(),RUN/f"{arm}_{condition}_{seed}.pt")
                save(target,result);results.append(result)
                print("RESULT",arm,condition,seed,score["pooled"],flush=True)
    comparison={}
    for arm in ("gnn","fusion"):
        scores={}
        for condition in ("baseline","baseline_matched_updates","augmented"):
            group=[r for r in results if r["arm"]==arm and r["condition"]==condition]
            scores[condition]=dict(pooled_auc_mean=float(np.mean([r["metrics"]["pooled"]["auroc"] for r in group])),
               host_auc_mean=float(np.mean([r["metrics"]["host_auc"]["mean"] for r in group])),
               balanced_accuracy_mean=float(np.mean([r["metrics"]["pooled"]["balanced_accuracy"] for r in group])),
               per_seed=[dict(seed=r["seed"],pooled=r["metrics"]["pooled"],host_auc=r["metrics"]["host_auc"]) for r in group])
        deltas=[]
        for seed in protocol["seeds"]:
            a,b=[next(r for r in results if r["arm"]==arm and r["condition"]==c and r["seed"]==seed) for c in ("baseline","augmented")]
            deltas.append(dict(seed=seed,pooled_auc=b["metrics"]["pooled"]["auroc"]-a["metrics"]["pooled"]["auroc"],
                  host_delta={h:b["metrics"]["hosts"][h]["auroc"]-m["auroc"] for h,m in a["metrics"]["hosts"].items()}))
        scores["paired_deltas"]=deltas
        matched=[r for r in results if r["arm"]==arm and r["condition"]=="baseline_matched_updates"]
        scores["baseline_matched_updates"]=dict(pooled_auc_mean=float(np.mean([r["metrics"]["pooled"]["auroc"] for r in matched])),
           host_auc_mean=float(np.mean([r["metrics"]["host_auc"]["mean"] for r in matched])),
           balanced_accuracy_mean=float(np.mean([r["metrics"]["pooled"]["balanced_accuracy"] for r in matched])),
           per_seed=[dict(seed=r["seed"],pooled=r["metrics"]["pooled"],host_auc=r["metrics"]["host_auc"]) for r in matched])
        scores["mean_seed_host_delta"]=summary({h:float(np.mean([d["host_delta"][h] for d in deltas])) for h in deltas[0]["host_delta"]})
        comparison[arm]=scores
    save(OUT/"training_results.json",dict(protocol=protocol,comparison=comparison,runs=results))
if __name__=="__main__":main()
