"""Exploratory family, source-bundle and synthesis-flow identity controls."""
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("stage2_baselines", ROOT / "experiments/dataset_stage2/baselines.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
rows = sorted(json.loads((ROOT / "data/dataset_v2/trusthub_primary.json").read_text(encoding="utf-8")), key=lambda r: r["key"])
folds = json.loads((ROOT / "data/dataset_v2/trusthub_folds.json").read_text(encoding="utf-8"))["folds"]
index = {r["key"]: i for i, r in enumerate(rows)}
result = {}
for field in ("family", "source_bundle_sha256", "synthesis_flow"):
    names = sorted({r[field] for r in rows})
    x = np.array([[float(r[field] == name) for name in names] for r in rows])
    scored = []
    unseen = []
    for fold in folds:
        tr = np.array([index[k] for k in fold["train_keys"]])
        te = np.array([index[k] for k in fold["test_keys"]])
        y = np.array([rows[i]["label"] for i in tr])
        prob, _ = base.logistic(x[tr], y, x[te])
        train_values = {rows[i][field] for i in tr}
        unseen.extend(rows[i]["key"] for i in te if rows[i][field] not in train_values)
        scored.extend({"key": rows[i]["key"], "family": rows[i]["family"], "label": rows[i]["label"], "score": float(p)} for i, p in zip(te, prob))
    scored.sort(key=lambda r: r["key"])
    groups = sorted({r["family"] for r in scored})
    auroc = {family: base.auc([r["label"] for r in scored if r["family"] == family],
                              [r["score"] for r in scored if r["family"] == family]) for family in groups}
    result[field] = {"equal_family_auroc": float(np.mean(list(auroc.values()))), "by_family_auroc": auroc,
                     "unseen_identity_records": len(unseen), "unseen_identity_keys": unseen,
                     "predictions": scored}
out = ROOT / "data/trusthub_primary_v1/metadata_controls.json"
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: {"equal_family_auroc": v["equal_family_auroc"], "unseen_identity_records": v["unseen_identity_records"]} for k, v in result.items()}, indent=2))
