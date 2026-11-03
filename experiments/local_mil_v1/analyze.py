"""Paired host-bootstrap uncertainty for the one-way transfer diagnostic."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
local = json.loads((ROOT / "data/local_mil_v1/transfer_from_fold4.json").read_text(encoding="utf-8"))["models"]
control = json.loads((ROOT / "data/local_mil_v1/transfer_controls.json").read_text(encoding="utf-8"))["models"]
models = {**local, **control}
hosts = sorted({r["host"] for r in local["prior_cell_pool_gnn"]["predictions"]})
assert len(hosts) == 48


def host_auc(rows):
    result = []
    for host in hosts:
        part = [r for r in rows if r["host"] == host]
        pos = [r["probability"] for r in part if r["label"] == 1]
        neg = [r["probability"] for r in part if r["label"] == 0]
        result.append(np.mean([float(a > b) + .5 * float(a == b) for a in pos for b in neg]))
    return np.array(result)


vectors = {name: host_auc(model["predictions"]) for name, model in models.items()}
rng = np.random.default_rng(20261103)
draws = rng.integers(0, len(hosts), size=(10000, len(hosts)))
reference = vectors["prior_cell_pool_gnn"]
report = {}
for name, vector in vectors.items():
    difference = vector - reference
    report[name] = {
        "equal_host_auroc": float(vector.mean()),
        "host_bootstrap_95pct_interval": [float(x) for x in np.quantile(vector[draws].mean(1), [.025, .975])],
        "delta_vs_prior_gnn": float(difference.mean()),
        "delta_bootstrap_95pct_interval": [float(x) for x in np.quantile(difference[draws].mean(1), [.025, .975])],
    }
result = {"scope": "descriptive uncertainty on 48 development hosts; one-way fold-4-trained comparison", "seed": 20261103, "draws": 10000, "models": report}
(ROOT / "data/local_mil_v1/transfer_uncertainty.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
