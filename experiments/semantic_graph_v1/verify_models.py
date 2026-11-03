"""Verify that both actual model branches accept the repaired graph schema."""
import json
import sys
from pathlib import Path
import torch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"pipeline"))
from models import GNNOnly,CrossAttentionFusion
torch.set_num_threads(2)
items=[torch.load(ROOT/f"runs/semantic_graph_v1/prepared/native_tt_um_rejunity_decoder_{side}.pt",weights_only=False)
       for side in ("benign","trojan")]
report={}
for arm,constructor in (("gnn",GNNOnly),("fusion",CrossAttentionFusion)):
 torch.manual_seed(42)
 model=constructor(node_dim=items[0]["graph"].x.shape[1])
 model.eval()
 logits=[]
 for item in items:
  output=(model(item["graph"],item["rtl"],return_attention=False) if arm=="fusion"
          else model(item["graph"],item["rtl"]))
  logits.append(output["logits"])
 loss=torch.nn.functional.cross_entropy(logits[-1],torch.tensor([1]))
 loss.backward()
 assert torch.isfinite(loss)
 assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
 report[arm]=dict(node_dim=items[0]["graph"].x.shape[1],finite_forward_and_backward=True,
                  random_head_logit_difference=float((logits[0]-logits[1]).abs().max().detach()))
(ROOT/"data/semantic_graph_v1/model_compatibility.json").write_text(json.dumps(report,indent=2))
print(report)
