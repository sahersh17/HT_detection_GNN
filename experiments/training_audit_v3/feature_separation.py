"""Quantify within-host edit size relative to between-host feature variation."""
import json,sys
from pathlib import Path
from collections import defaultdict
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"pipeline"))
from lofo_graph_baselines import stats
torch.set_num_threads(1)
manifest=json.loads((ROOT/"data/training_audit_v3/manifest.json").read_text())
groups=defaultdict(list)
for meta in manifest["records"]:
 if meta["cohort"]=="test":continue
 row=torch.load(ROOT/meta["file"],weights_only=False)
 groups[row["host"]].append((row["label"],row["rtl"].mean(0),stats(row["graph"])))
report={}
for feature,index in (("rtl_mean",1),("graph_statistics",2)):
 clean={h:torch.stack([r[index] for r in rows if r[0]==0]).mean(0) for h,rows in groups.items()}
 within=[float((r[index]-clean[h]).norm()) for h,rows in groups.items() for r in rows if r[0]==1]
 hosts=sorted(clean)
 between=[float((clean[a]-clean[b]).norm()) for i,a in enumerate(hosts) for b in hosts[i+1:]]
 report[feature]=dict(median_positive_to_host_negative=float(torch.tensor(within).median()),
 median_between_host_negative=float(torch.tensor(between).median()))
(ROOT/"data/training_audit_v3/feature_separation.json").write_text(json.dumps(report,indent=2))
print(report)
