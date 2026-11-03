"""Test whether the unchanged architectures can learn a balanced four-circuit control."""
import json,sys,hashlib
from pathlib import Path
from collections import defaultdict
import torch
from torch.nn import functional as F
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"pipeline"))
from models import GNNOnly,CrossAttentionFusion
from metrics import summarize
torch.set_num_threads(4)
manifest=json.loads((ROOT/"data/augmentation_v2/manifest.json").read_text())
rows=[torch.load(ROOT/r["file"],weights_only=False) for r in manifest["records"]]
groups=defaultdict(list)
for row,meta in zip(rows,manifest["records"]):
 graph=row["graph"]
 h=hashlib.sha256()
 for tensor in (graph.x,graph.edge_index):
  h.update(str(tuple(tensor.shape)).encode());h.update(tensor.numpy().tobytes())
 groups[h.hexdigest()].append(dict(key=meta["key"],label=row["label"]))
collisions=[v for v in groups.values() if len({r["label"] for r in v})>1]
toy=[r for r in rows if r["host"]=="uart16550"]
results={}
for arm,constructor in (("gnn",lambda:GNNOnly(dropout=0.)),("fusion",lambda:CrossAttentionFusion(dropout=0.))):
 torch.manual_seed(42);model=constructor()
 opt=torch.optim.AdamW(model.parameters(),lr=1e-3,weight_decay=0.)
 losses=[]
 for step in range(200):
  model.train();opt.zero_grad();total=0.
  for row in toy:
   loss=F.cross_entropy(model(row["graph"],row["rtl"])["logits"],torch.tensor([row["label"]]))/len(toy)
   loss.backward();total+=float(loss.detach())
  torch.nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step()
  losses.append(total)
  if step%25==0:print(arm,step,total,flush=True)
 model.eval()
 with torch.no_grad():probs=[float(model(r["graph"],r["rtl"])["logits"].softmax(-1)[0,1]) for r in toy]
 results[arm]=dict(losses=losses,probabilities=probs,metrics=summarize([r["label"] for r in toy],[int(p>=.5) for p in probs],probs))
output=dict(opposite_label_exact_graph_collisions=collisions,positive_controls=results)
(ROOT/"data/training_audit_v3/positive_controls.json").write_text(json.dumps(output,indent=2))
print({k:v["metrics"] for k,v in results.items()},flush=True)
