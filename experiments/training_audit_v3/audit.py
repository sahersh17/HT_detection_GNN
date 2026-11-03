"""Audit previous model fitting, input ranges and duplicated detector inputs."""
import hashlib,json,sys
from collections import Counter,defaultdict
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"pipeline"))
from models import GNNOnly,CrossAttentionFusion
from metrics import summarize
torch.set_num_threads(4)
OUT=ROOT/"data/training_audit_v3"
manifest=json.loads((ROOT/"data/augmentation_v2/manifest.json").read_text())
samples=[torch.load(ROOT/r["file"],weights_only=False) for r in manifest["records"]]
def evaluate(model,items):
 model.eval();labels=[];scores=[]
 with torch.no_grad():
  for r in items:
   labels.append(r["label"]);scores.append(float(model(r["graph"],r["rtl"])["logits"].softmax(-1)[0,1]))
 return dict(metrics=summarize(labels,[int(p>=.5) for p in scores],scores),score_range=[min(scores),max(scores)],
             class_means={str(y):sum(p for p,t in zip(scores,labels) if t==y)/labels.count(y) for y in (0,1)})
report={}
for arm,constructor in (("gnn",GNNOnly),("fusion",CrossAttentionFusion)):
 for condition in ("baseline","augmented"):
  model=constructor();model.load_state_dict(torch.load(ROOT/f"runs/augmentation_v2/{arm}_{condition}_42.pt",weights_only=True))
  train=[r for r in samples if r["cohort"]!="test" and (condition=="augmented" or r["cohort"]=="baseline")]
  report[arm+"_"+condition]=dict(train=evaluate(model,train),test=evaluate(model,[r for r in samples if r["cohort"]=="test"]))
stats={}
for cohort in sorted({r["cohort"] for r in samples}):
 rows=[r for r in samples if r["cohort"]==cohort]
 x=torch.cat([r["graph"].x for r in rows])
 stats[cohort]=dict(labels=dict(Counter(r["label"] for r in rows)),finite=bool(torch.isfinite(x).all()),min=x.min(0).values.tolist(),max=x.max(0).values.tolist(),
                  rtl_norm_range=[min(float(r["rtl"].norm(dim=1).mean()) for r in rows),max(float(r["rtl"].norm(dim=1).mean()) for r in rows)])
report["input_statistics"]=stats
(OUT/"previous_fit_audit.json").write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
