"""Verify labels, tensor bounds and unchanged graph inputs after wording removal."""
import json,re
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[2]
torch.set_num_threads(1)
old=json.loads((ROOT/"data/augmentation_v2/manifest.json").read_text())
new=json.loads((ROOT/"data/training_audit_v3/manifest.json").read_text())
assert [r["key"] for r in old["records"]]==[r["key"] for r in new["records"]]
train_hosts=set()
test_hosts=set()
for before,after in zip(old["records"],new["records"]):
 a=torch.load(ROOT/before["file"],weights_only=False)
 b=torch.load(ROOT/after["file"],weights_only=False)
 assert torch.equal(a["graph"].x,b["graph"].x)
 assert torch.equal(a["graph"].edge_index,b["graph"].edge_index)
 assert a["label"]==b["label"]==int(b["variant"] not in ("clean","benign"))
 graph=b["graph"]
 assert graph.x.shape[1]==20 and torch.isfinite(graph.x).all()
 assert torch.equal(graph.x[:,:16].sum(1),torch.ones(graph.num_nodes))
 assert graph.edge_index.min()>=0 and graph.edge_index.max()<graph.num_nodes
 assert b["rtl"].ndim==2 and b["rtl"].shape[1]==768 and len(b["rtl"])>0
 assert torch.isfinite(b["rtl"]).all()
 text=(ROOT/"runs/training_audit_v3/prepared"/(after["key"]+".v")).read_text()
 assert not re.search(new["sanitized_terms"],text,re.I)
 (test_hosts if b["cohort"]=="test" else train_hosts).add(b["host"])
assert not train_hosts&test_hosts
result=dict(records=len(new["records"]),graph_tensors_unchanged=True,labels_verified=True,finite_and_bounded=True,
            sanitized_terms_absent=True,train_hosts=len(train_hosts),test_hosts=sorted(test_hosts))
(ROOT/"data/training_audit_v3/integrity.json").write_text(json.dumps(result,indent=2))
print(result)
