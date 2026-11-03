"""Descriptive size-overlap and provenance checks on frozen out-of-fold scores."""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/trusthub_primary_v1"
rows = json.loads((ROOT / "data/dataset_v2/trusthub_primary.json").read_text(encoding="utf-8"))
pred = json.loads((OUT / "predictions.json").read_text(encoding="utf-8"))
by_key = {r["key"]: r for r in rows}
family = defaultdict(list)
for r in rows:
    family[r["family"]].append(r)


def auc(pairs):
    return float(np.mean(pairs)) if pairs else None


result = {"family_provenance": {}, "size_matched_within_family": {}, "within_size_quartile": {}}
for f, items in sorted(family.items()):
    result["family_provenance"][f] = {
        "circuits": len(items),
        "clean_source_bundles": len({r["source_bundle_sha256"] for r in items if r["label"] == 0}),
        "synthesis_flows": sorted({r["synthesis_flow"] for r in items}),
    }

# A fixed 5% mapped-node tolerance, using both labels within the same family.
for model, predictions in pred.items():
    scores = {r["key"]: r["score"] for r in predictions}
    comparisons = []
    contributing_families = []
    family_scores = {}
    for f, items in sorted(family.items()):
        local = []
        for positive in (r for r in items if r["label"] == 1):
            for negative in (r for r in items if r["label"] == 0):
                ratio = abs(positive["graph_nodes"] - negative["graph_nodes"]) / max(positive["graph_nodes"], negative["graph_nodes"])
                if ratio <= .05:
                    local.append(float(scores[positive["key"]] > scores[negative["key"]]) + .5 * float(scores[positive["key"]] == scores[negative["key"]]))
        if local:
            family_scores[f] = auc(local)
            comparisons.extend(local)
            contributing_families.append(f)
    result["size_matched_within_family"][model] = {
        "node_tolerance": .05,
        "families_with_overlap": contributing_families,
        "n_families": len(contributing_families),
        "n_comparisons": len(comparisons),
        "equal_family_pair_accuracy": auc(list(family_scores.values())),
        "by_family": family_scores,
    }

nodes = np.array([math.log1p(r["graph_nodes"]) for r in rows])
cuts = np.quantile(nodes, [0, .25, .5, .75, 1])
for model, predictions in pred.items():
    scores = {r["key"]: r["score"] for r in predictions}
    out = []
    for i in range(4):
        selected = [r for r in rows if cuts[i] <= math.log1p(r["graph_nodes"]) < cuts[i + 1] or
                    (i == 3 and math.log1p(r["graph_nodes"]) == cuts[i + 1])]
        y = np.array([r["label"] for r in selected])
        s = np.array([scores[r["key"]] for r in selected])
        p, n = s[y == 1], s[y == 0]
        rank = float(((p[:, None] > n).sum() + .5 * (p[:, None] == n).sum()) / (len(p) * len(n))) if len(p) and len(n) else None
        out.append({"quartile": i, "negative": int((y == 0).sum()), "positive": int((y == 1).sum()), "pooled_auroc": rank,
                    "families": sorted({r["family"] for r in selected})})
    result["within_size_quartile"][model] = out

(OUT / "size_overlap.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"size_matched_within_family": result["size_matched_within_family"],
                  "within_size_quartile": result["within_size_quartile"]["graph_aggregate_logistic"]}, indent=2))
