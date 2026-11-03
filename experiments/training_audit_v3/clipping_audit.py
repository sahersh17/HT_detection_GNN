"""Measure how per-circuit clipping changes the intended weighted gradient."""
import json,sys
from pathlib import Path
from collections import Counter
import torch
from torch.nn import functional as F
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"pipeline"))
from models import GNNOnly
torch.set_num_threads(2)
manifest=json.loads((ROOT/"data/augmentation_v2/manifest.json").read_text())
rows=[torch.load(ROOT/r["file"],weights_only=False) for r in manifest["records"] if r["cohort"]!="test"]
counts=Counter((r["host"],r["label"]) for r in rows)
model=GNNOnly()
model.load_state_dict(torch.load(ROOT/"runs/augmentation_v2/gnn_augmented_42.pt",weights_only=True))
model.eval()
measurements=[]
for row in rows:
 model.zero_grad()
 weight=len(rows)/(60*2*counts[row["host"],row["label"]])
 loss=F.cross_entropy(model(row["graph"])["logits"],torch.tensor([row["label"]]))*weight
 loss.backward()
 before=float(model.head[-1].bias.grad[1])
 norm=float(torch.nn.utils.clip_grad_norm_(model.parameters(),1.))
 after=float(model.head[-1].bias.grad[1])
 measurements.append(dict(label=row["label"],norm=norm,before=before,after=after))
result=dict(before_mean=sum(r["before"] for r in measurements)/len(rows),
 after_mean=sum(r["after"] for r in measurements)/len(rows),
 by_class={str(y):dict(clipped_fraction=sum(r["norm"]>1 for r in measurements if r["label"]==y)/sum(r["label"]==y for r in measurements),
 before_mean=sum(r["before"] for r in measurements if r["label"]==y)/sum(r["label"]==y for r in measurements),
 after_mean=sum(r["after"] for r in measurements if r["label"]==y)/sum(r["label"]==y for r in measurements)) for y in (0,1)})
(ROOT/"data/training_audit_v3/clipping_audit.json").write_text(json.dumps(result,indent=2))
print(result)
