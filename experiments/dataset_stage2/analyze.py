"""Audit fold makeup and paired host-level uncertainty after the fixed run."""
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
read = lambda path: json.loads((ROOT / path).read_text(encoding="utf-8"))
rows = [r for r in read("data/dataset_stage1/records.json") if r["role"] == "development"]
folds = read("data/dataset_stage1/folds.json")["folds"]
preds = read("data/dataset_stage2/predictions.json")
bad = set(read("data/dataset_stage1/summary.json")["saved_model_view_mismatches"])
fold_audit = []
for f in folds:
    group = [r for r in rows if r["key"] in set(f["test_keys"])]
    positive = [r for r in group if r["label"] == 1]
    uni = [r for r in group if r["key"] in bad]
    fold_audit.append({
        "fold": f["fold"], "records": len(group), "hosts": len(set(r["host"] for r in group)),
        "negative": len(group) - len(positive), "positive": len(positive),
        "positive_mechanisms": dict(sorted(Counter(r["mechanism_family"] for r in positive).items())),
        "unicode_copies": len(uni), "unicode_negative": sum(r["label"] == 0 for r in uni),
        "unicode_positive": sum(r["label"] == 1 for r in uni),
        "unicode_hosts": sorted(set(r["host"] for r in uni)),
    })

by_model = {}
for model, items in preds.items():
    per = defaultdict(list)
    for r in items:
        per[r["host"]].append(r)
    scores = {}
    for h, group in per.items():
        pos = [r["probability"] for r in group if r["label"] == 1]
        neg = [r["probability"] for r in group if r["label"] == 0]
        scores[h] = np.mean([float(a > b) + .5 * float(a == b) for a in pos for b in neg])
    by_model[model] = scores

hosts = sorted(by_model["size_only/logistic"])
seed = 20261103
rng = np.random.default_rng(seed)
draws = rng.integers(0, len(hosts), (10000, len(hosts)))
uncertainty = {}
for name in ("size_only/logistic", "graph_aggregates/logistic", "pooled_codebert/logistic", "combined/logistic"):
    vector = np.array([by_model[name][h] for h in hosts])
    boot = vector[draws].mean(1)
    delta = vector - np.array([by_model["size_only/logistic"][h] for h in hosts])
    delta_boot = delta[draws].mean(1)
    uncertainty[name] = {
        "equal_host_auroc": float(vector.mean()),
        "host_bootstrap_95pct_interval": [float(v) for v in np.quantile(boot, [.025, .975])],
        "delta_vs_size_only": float(delta.mean()),
        "delta_host_bootstrap_95pct_interval": [float(v) for v in np.quantile(delta_boot, [.025, .975])],
    }

result = {"fold_audit": fold_audit, "unicode_total": len(bad), "unicode_hosts": len(set(r["host"] for r in rows if r["key"] in bad)), "uncertainty": uncertainty, "bootstrap_seed": seed, "bootstrap_draws": len(draws)}
unicode_hosts = {r["host"] for r in rows if r["key"] in bad}
result["subgroups"] = {}
for name in ("size_only/logistic", "graph_aggregates/logistic", "pooled_codebert/logistic", "combined/logistic"):
    items = preds[name]
    result["subgroups"][name] = {}
    for label, included in (
        ("native", {r["host"] for r in items if r["cohort"] == "native"}),
        ("non_native", {r["host"] for r in items if r["cohort"] != "native"}),
        ("excluding_unicode_hosts", set(hosts) - unicode_hosts),
    ):
        result["subgroups"][name][label] = {"hosts": len(included), "equal_host_auroc": float(np.mean([by_model[name][h] for h in included]))}
dest = ROOT / "data/dataset_stage2/audit.json"
dest.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
