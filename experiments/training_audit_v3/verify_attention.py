import json,sys
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"pipeline"))
from models import CrossAttentionFusion
torch.set_num_threads(1)
item=torch.load(ROOT/"runs/augmentation_v2/prepared/four_projects_uart16550_clean.pt",weights_only=False)
torch.manual_seed(42)
model=CrossAttentionFusion(dropout=0.)
a=model(item["graph"],item["rtl"])
a["logits"].sum().backward()
reference={n:p.grad.clone() for n,p in model.named_parameters()}
model.zero_grad()
b=model(item["graph"],item["rtl"],return_attention=False)
b["logits"].sum().backward()
max_output=float((a["logits"]-b["logits"]).abs().max())
max_gradient=max(float((reference[n]-p.grad).abs().max()) for n,p in model.named_parameters())
assert torch.allclose(a["logits"],b["logits"],atol=1e-6,rtol=1e-5)
for n,p in model.named_parameters():
 assert torch.allclose(reference[n],p.grad,atol=1e-5,rtol=1e-4),n
assert b["graph_to_rtl_attention"] is None and a["graph_to_rtl_attention"] is not None
(ROOT/"data/training_audit_v3/attention_parity.json").write_text(json.dumps(dict(max_logit_error=max_output,max_gradient_error=max_gradient),indent=2))
print(max_output,max_gradient)
