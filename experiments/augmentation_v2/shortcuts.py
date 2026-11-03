"""Run admission controls independently of embedding preparation."""
import json,sys
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"pipeline"),str(ROOT/"pipeline/provenance"),str(ROOT/"experiments/precision_v1")]
from build import graph_from_json
from lofo_graph_baselines import stats,wl,fit_predict
from bootstrap import summary
torch.set_num_threads(1)
OUT=ROOT/"data/augmentation_v2"
def read(p):return json.loads(p.read_bytes())
rows=[r for r in read(ROOT/"data/transfer_v1/intake.json")["records"] if r["variant"]!="benign"]+read(OUT/"intake.json")["records"]
items=[]
for r in rows:
 g,m=graph_from_json(read(ROOT/r["mapped"]),r["top"],r["host"],0)
 text="\n".join((ROOT/p).read_text(errors="replace") for p in r["sources"] if p.endswith(".v"))
 items.append(dict(host=r["host"],variant=r["variant"],label=int(r["variant"] not in ("clean","benign")),
   counts=dict(cells=g.num_nodes,edges=g.num_edges,characters=len(text),lines=len(text.splitlines())),
   stats=stats(g),wl2=wl(g),gate_hist=g.x[:,:-4].sum(0),
   attack_string_count=text.lower().count("trojan"),ports=sorted((k,v["direction"],len(v["bits"])) for k,v in read(ROOT/r["mapped"])["modules"][r["top"]]["ports"].items())))
report={}
for scope,hs in (("four_projects",sorted({r["host"] for r in items if r["host"]!="RS232"})),("external_authored",["RS232"])):
 subset=[r for r in items if r["host"] in hs]
 metrics={}
 def ranking(te,scores):
  pos=[p for r,p in zip(te,scores) if r["label"]];neg=[p for r,p in zip(te,scores) if not r["label"]]
  return sum(float(a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))
 for k in subset[0]["counts"]:
  metrics[k]=summary({h:ranking([r for r in subset if r["host"]==h],[r["counts"][k] for r in subset if r["host"]==h]) for h in hs})
 if len(hs)>1:
  for k in ("stats","wl2","gate_hist"):
   folds={}
   for h in hs:
    tr=[r for r in subset if r["host"]!=h];te=[r for r in subset if r["host"]==h]
    prob=fit_predict(torch.stack([r[k] for r in tr]),torch.tensor([r["label"] for r in tr]),torch.ones(len(tr)),torch.stack([r[k] for r in te]),42)
    folds[h]=ranking(te,prob)
   metrics[k]=summary(folds)
 pairwise={}
 for negative in ("clean","benign"):
  eligible=[h for h in hs if any(r["host"]==h and r["variant"]==negative for r in subset)]
  if eligible:
   pairwise[negative]={k:summary({h:ranking([r for r in subset if r["host"]==h and (r["label"] or r["variant"]==negative)],
          [r["counts"][k] for r in subset if r["host"]==h and (r["label"] or r["variant"]==negative)]) for h in eligible}) for k in subset[0]["counts"]}
 report[scope]=dict(pairwise_scalar_controls=pairwise,controls=metrics,hard_stops=[k for k,v in metrics.items() if max(v["mean"],1-v["mean"])>=.9],
   port_signature_counts={h:len({tuple(r["ports"]) for r in subset if r["host"]==h}) for h in hs},
   measurements=[{k:v for k,v in r.items() if k not in ("stats","wl2","gate_hist","ports")} for r in subset])
for scope in ("four_projects","external_authored"):
 rows=report[scope]["measurements"]
 positives=[r["attack_string_count"] for r in rows if r["label"]]
 negatives=[r["attack_string_count"] for r in rows if not r["label"]]
 report[scope]["explicit_attack_word_control"]=sum(float(a>b)+.5*(a==b) for a in positives for b in negatives)/(len(positives)*len(negatives))
report["native_panel_previous_rerun"]=read(ROOT/"data/transfer_v1/native_audit.json")
(OUT/"shortcuts.json").write_text(json.dumps(report,indent=2))
print({k:v["hard_stops"] for k,v in report.items() if "hard_stops" in v})
