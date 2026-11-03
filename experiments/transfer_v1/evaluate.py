"""Refit native-only controls and compare the frozen graph-statistics probe on identical hosts."""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/"pipeline"), str(ROOT/"experiments/precision_v1")]
from lofo_graph_baselines import fit_predict, stats
from select_panel import source_fingerprints
from metrics import auroc
from bootstrap import summary
from provenance.build import graph_from_json

OUT = ROOT/"data/transfer_v1"
RUN = ROOT/"runs/transfer_v1"
SIDES = ("clean","benign","trojan")

def read(p):
    return json.loads(p.read_bytes())

def save(name, data):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False))

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rank(a,b):
    return float(a>b)+0.5*(a==b)

def load():
    decision=read(ROOT/"data/precision_v1/admission.json")
    items={}
    cohorts=defaultdict(set)
    ports={}
    for version in ("overlap_six_v1","precision_v1"):
        manifest=ROOT/"data"/version/"manifest.json"
        key="parent_manifest_sha256" if version=="overlap_six_v1" else "manifest_sha256"
        assert digest(manifest)==decision[key]
        for row in read(manifest)["records"]:
            h,s=row["host"],row["variant"]
            cohort="anchors" if version=="overlap_six_v1" else ("wrapper" if row["edit_kind"]=="guarded_output_fallback" else "native")
            cohorts[cohort].add(h)
            key=hashlib.sha256(json.dumps([row["sources"],row["mapped_json_sha256"],decision["protocol_sha256"]],sort_keys=True).encode()).hexdigest()
            items[h,s]=torch.load(ROOT/"runs/precision_v1/feature_cache"/(key+".pt"),weights_only=True)
            if cohort=="native":
                p=ROOT/"runs/precision_v1/hosts"/h/s/"yosys.json"
                assert digest(p)==row["mapped_json_sha256"]
                sig=read(p)["modules"][row["top"]]["ports"]
                ports[h,s]=sorted((n,v["direction"],len(v["bits"])) for n,v in sig.items())
    return decision,items,cohorts,ports

def probe(train,test,weights=None):
    x,y=zip(*train)
    return fit_predict(torch.stack(x),torch.tensor(y),torch.tensor(weights if weights is not None else [0.75 if label==0 else 1.5 for label in y]),torch.stack(test),42)

def audit(decision,items,cohorts,ports):
    hosts=sorted(cohorts["native"])
    gh=[h for h in hosts if h not in decision["graph_unavailable"]]
    out={}
    for side in ("clean","benign"):
        controls={}
        for name in items[hosts[0],side][0]:
            controls[name]=summary({h:rank(items[h,"trojan"][0][name],items[h,side][0][name]) for h in hosts})
        for name in items[gh[0],side][2]:
            selected=hosts if name=="metadata" else gh
            folds={}
            for h in selected:
                train=[items[t,s][2][name] for t in selected if t!=h for s in (side,"trojan")]
                scores=fit_predict(torch.stack(train),torch.tensor([0,1]*(len(train)//2)),torch.ones(len(train)),
                    torch.stack([items[h,s][2][name] for s in (side,"trojan")]),42+selected.index(h))
                assert np.isfinite(scores).all()
                folds[h]=rank(scores[1],scores[0])
            controls[name]=summary(folds)
        out[side]=controls
    origin={s:{k:summary({h:m["by_host"][h] for h in hosts}) for k,m in mm.items()} for s,mm in decision["origin_controls"].items()}
    different=[h for h in hosts if len({tuple(ports[h,s]) for s in SIDES})>1]
    stops=[(s,k,v["mean"]) for s,mm in out.items() for k,v in mm.items() if max(v["mean"],1-v["mean"])>=.90]
    margins=[(domain,s,k,v["ci95"]) for domain,groups in (("class",out),("origin",origin)) for s,mm in groups.items() for k,v in mm.items()
             if (domain=="origin" or k in items[hosts[0],"clean"][0]) and (v["ci95"][0]<.30 or v["ci95"][1]>.70)]
    save("native_audit.json",dict(hosts=hosts,graph_hosts=gh,class_controls=out,origin_controls=origin,
         differing_port_signatures=different,hard_stops=stops,margin_failures=margins,
         inconclusive_or_unavailable=[(h,s) for h in hosts for s,v in decision["overlap"][h].items() if v["typed_view"]=="inconclusive"],
         wrapper_stress=[r for r in decision["construction_sensitivity"] if r["domain"]=="class" and r["metric"]=="cells"]))

def summarize(rows):
    y=[int(s not in ("clean","benign")) for h,s,p in rows]
    perf={}
    for h in sorted({h for h,s,p in rows}):
        pairs=[(label,p,s) for (host,s,p),label in zip(rows,y) if host==h]
        auc=auroc([v[0] for v in pairs],[v[1] for v in pairs])
        recall=np.mean([p>=.5 for label,p,s in pairs if label])
        fp={s:float(np.mean([p>=.5 for _,p,name in pairs if name==s])) for s in ("clean","benign") if any(name==s for _,_,name in pairs)}
        perf[h]=dict(auroc=auc,recall=float(recall),false_positive_rate=fp,balanced_accuracy=(recall+1-np.mean(list(fp.values())))/2)
    return dict(hosts=perf,host_auc=summary({h:v["auroc"] for h,v in perf.items()}),
                pooled_auc=auroc(y,[p for _,_,p in rows]),predictions=rows)

def supplement(base,extra,target):
    # In the original triplets each host has 1.5 weight per class.
    rows=list(base)
    weights=[0.75 if y==0 else 1.5 for _,y in rows]
    for h in sorted({h for h,_,_ in extra}):
        for positive in (False,True):
            group=[v for host,s,v in extra if h==host and (s not in ("clean","benign"))==positive]
            rows.extend((v,int(positive)) for v in group)
            weights.extend([1.5/len(group)]*len(group))
    scores=probe(rows,[v for _,_,v in target],weights)
    if not np.isfinite(scores).all(): raise ValueError("Nonfinite supplement score")
    return [(h,s,p) for (h,s,_),p in zip(target,scores)]

def extra_arm(result,rows):
    after=summarize(rows)
    before=result["plus_native"]
    result["plus_four_projects"]=after
    result["four_project_delta"]=summary({h:v["auroc"]-before["hosts"][h]["auroc"] for h,v in after["hosts"].items()})

def compare(train,tests):
    result={}
    for arm,rows in train.items():
        scores=probe(rows,[v for _,_,v in tests])
        assert np.isfinite(scores).all()
        result[arm]=summarize([(h,s,p) for (h,s,_),p in zip(tests,scores)])
    a,b=result.values()
    result["paired_delta"]=summary({h:b["hosts"][h]["auroc"]-v["auroc"] for h,v in a["hosts"].items()})
    return result

def main():
    torch.set_num_threads(1)
    d,items,cohorts,ports=load()
    if "--audit" in sys.argv:
        audit(d,items,cohorts,ports)
        return
    usable=cohorts["native"]-set(d["graph_unavailable"])
    def training(hosts):
        return [(items[h,s][2]["graph_stats"],int(s=="trojan")) for h in sorted(hosts) for s in SIDES]
    train={"six_projects":training(cohorts["anchors"]),"plus_native":training(cohorts["anchors"]|usable)}
    tests=[]
    size_tests=[]
    for r in read(OUT/"intake.json")["records"]:
        p=ROOT/r["mapped"]
        assert digest(p)==r["mapped_sha256"]
        g,_=graph_from_json(read(p),r["top"],r["host"],0)
        tests.append((r["host"],r["variant"],stats(g)))
        size_tests.append((r["host"],r["variant"],g.num_nodes))
    # Check the scored clean implementations against every training source lineage.
    trainprints={}
    for version in ("overlap_six_v1","precision_v1"):
        for r in read(ROOT/"data"/version/"manifest.json")["records"]:
            if r["variant"]=="clean" and r["host"] in cohorts["anchors"]|usable:
                trainprints[r["host"]]=source_fingerprints([ROOT/p for p in r["sources"]])
    related=set()
    for r in read(OUT/"intake.json")["records"]:
        if r["variant"]!="clean": continue
        modules,shape=source_fingerprints([ROOT/p for p in r["sources"]])
        for h,(other,grams) in trainprints.items():
            if modules&other or (shape and grams and len(shape&grams)/min(len(shape),len(grams))>.80):
                related.add(h)
    new_train={"six_projects":training(cohorts["anchors"]-related),
               "plus_native":training((cohorts["anchors"]|usable)-related)}
    result={"new_projects":compare(new_train,tests),"lineage_exclusions":sorted(related)}
    new_examples=list(tests)
    result["new_project_size_control"]={h:auroc([int(s in ("toggle","suppress")) for host,s,n in size_tests if host==h],
                                         [n for host,s,n in size_tests if host==h]) for h in sorted({h for h,s,n in size_tests})}
    rows=[]
    for h in sorted({h for h,s,v in tests}):
        rows.extend(supplement(new_train["plus_native"],[r for r in tests if r[0]!=h],[r for r in tests if r[0]==h]))
    extra_arm(result["new_projects"],rows)
    # Existing real benchmark diagnostic, with the original threshold and both arms.
    real=[]
    for p in sorted((ROOT/"runs/expansion").glob("*/*/graph.pt")):
        side=p.parent.name
        bench=p.parent.parent.name
        h=bench.split("-")[0]
        real.append((h,side,stats(torch.load(p,weights_only=False,map_location="cpu"))))
    if len(real)!=10:
        real=[]
        for root in ("expansion_graphs","expansion_pic_graphs"):
            for p in sorted((ROOT/"runs"/root).glob("*/*/graph.pt")):
                real.append((p.parent.parent.name.split("-")[0],p.parent.name,stats(torch.load(p,weights_only=False,map_location="cpu"))))
    assert len(real)==10
    result["trusthub_diagnostic"]=compare(train,real)
    extra_arm(result["trusthub_diagnostic"],supplement(train["plus_native"],new_examples,real))
    # Cross an existing host cohort with an independent mutation engine.
    old=[]
    for r in read(ROOT/"data/tier12_v2/manifest.json")["records"]:
        h,s=r["host"],r["variant"]
        p=ROOT/"runs/tier12_v2"/h/s/"yosys.json"
        assert digest(p)==r["mapped_json_sha256"]
        graph,_=graph_from_json(read(p),"top",h,0)
        old.append((h,s,stats(graph)))
    def matrix(target,shared_hosts):
        predictions={name:[] for name in train}
        for h in sorted({r[0] for r in target}):
            fold=[r for r in target if r[0]==h]
            oldtrain=[(v,int(s=="trojan")) for t,s,v in old if shared_hosts or t!=h]
            for name,base in train.items():
                probs=probe(base+oldtrain,[r[2] for r in fold])
                if not np.isfinite(probs).all(): raise ValueError("Invalid matrix score")
                predictions[name].extend((t,s,p) for (t,s,_),p in zip(fold,probs))
        a,b=[summarize(rows) for rows in predictions.values()]
        return dict(six_projects=a,plus_native=b,paired_delta=summary({h:b["hosts"][h]["auroc"]-v["auroc"] for h,v in a["hosts"].items()}))
    result["same_engine_unseen_host"]=matrix(old,False)
    for kind in ("addition","removal","replacement"):
        tests=[]
        for r in read(ROOT/"data/tier12_v3"/kind/"manifest.json")["records"]:
            h,s=r["host"],r["variant"]
            p=ROOT/"runs/tier12_v3"/kind/h/s/"yosys.json"
            assert digest(p)==r["mapped_json_sha256"]
            g,_=graph_from_json(read(p),"top",h,0)
            tests.append((h,s,stats(g)))
        result["yosys_"+kind]=compare(train,tests)
        extra_arm(result["yosys_"+kind],supplement(train["plus_native"],new_examples,tests))
        result["unseen_engine_seen_hosts_"+kind]=matrix(tests,True)
        result["unseen_engine_unseen_hosts_"+kind]=matrix(tests,False)
    save("comparison.json",result)

if __name__=="__main__":
    main()
