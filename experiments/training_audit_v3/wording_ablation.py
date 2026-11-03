"""Measure wording removal at fixed old fusion weights."""
import json,sys
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"pipeline"),str(ROOT/"experiments/training_audit_v3")]
from models import CrossAttentionFusion
from train import predictions,metrics
torch.set_num_threads(2)
old=json.loads((ROOT/"data/augmentation_v2/manifest.json").read_text())
clean=json.loads((ROOT/"data/training_audit_v3/manifest.json").read_text())
rows={}
for label,manifest in (("raw",old),("sanitized",clean)):
 rows[label]=[torch.load(ROOT/r["file"],weights_only=False) for r in manifest["records"] if r["cohort"]=="test"]
result=[]
for seed in (42,43,44):
 model=CrossAttentionFusion()
 model.load_state_dict(torch.load(ROOT/f"runs/augmentation_v2/fusion_augmented_{seed}.pt",weights_only=True))
 scores={name:predictions(model,items,"fusion") for name,items in rows.items()}
 result.append(dict(seed=seed,metrics={name:metrics(p) for name,p in scores.items()},
                    maximum_probability_change=max(abs(a["probability"]-b["probability"]) for a,b in zip(scores["raw"],scores["sanitized"]))))
(ROOT/"data/training_audit_v3/wording_ablation.json").write_text(json.dumps(result,indent=2))
print([(r["seed"],r["metrics"]["raw"]["pooled"]["auroc"],r["metrics"]["sanitized"]["pooled"]["auroc"],r["maximum_probability_change"]) for r in result])
