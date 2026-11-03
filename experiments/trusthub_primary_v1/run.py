"""Locked Trust-Hub primary-panel CPU baselines and size audit."""
import hashlib
import importlib.util
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/trusthub_primary_v1"
spec = importlib.util.spec_from_file_location("stage2_baselines", ROOT / "experiments/dataset_stage2/baselines.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
torch.set_num_threads(1)


def read(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def local_features(graph):
    x = graph.x.float().numpy()
    return np.r_[x[:, :16].mean(0), [np.mean(x[:, channel] >= cut) for channel in (18, 19) for cut in (8, 16)]]


def family_auc(rows):
    by = defaultdict(list)
    for row in rows:
        by[row["family"]].append(row)
    return {family: base.auc([r["label"] for r in items], [r["score"] for r in items]) for family, items in sorted(by.items())}


def summarize(rows):
    by_family = family_auc(rows)
    y = np.array([r["label"] for r in rows])
    scores = np.array([r["score"] for r in rows])
    return {
        "equal_family_auroc": float(np.mean(list(by_family.values()))),
        "by_family_auroc": by_family,
        "pooled_auroc": base.auc(y, scores),
        "balanced_accuracy_at_0_5": float(((scores[y == 0] < .5).mean() + (scores[y == 1] >= .5).mean()) / 2),
    }


def size_audit(rows):
    pairs = defaultdict(dict)
    for r in rows:
        pairs[r["benchmark"]][r["label"]] = r
    deltas = {k: v[1]["graph_nodes"] - v[0]["graph_nodes"] for k, v in pairs.items()}
    # Global training-independent quantiles describe overlap; no model is selected with them.
    bounds = np.quantile([math.log1p(r["graph_nodes"]) for r in rows], [0, .25, .5, .75, 1])
    bins = []
    for j in range(4):
        selected = [r for r in rows if (bounds[j] <= math.log1p(r["graph_nodes"]) < bounds[j + 1] or
                    (j == 3 and math.log1p(r["graph_nodes"]) == bounds[j + 1]))]
        bins.append({"bin": j, "log_node_bounds": [float(bounds[j]), float(bounds[j + 1])],
                     "negative": sum(r["label"] == 0 for r in selected),
                     "positive": sum(r["label"] == 1 for r in selected),
                     "keys": [r["key"] for r in selected]})
    return {"paired_node_delta": deltas, "positive_larger": sum(v > 0 for v in deltas.values()),
            "positive_smaller": sum(v < 0 for v in deltas.values()), "bins": bins}


def main():
    rows = sorted(read("data/dataset_v2/trusthub_primary.json"), key=lambda r: r["key"])
    folds = read("data/dataset_v2/trusthub_folds.json")["folds"]
    assert len(rows) == 98 and len(folds) == 5
    idx = {r["key"]: i for i, r in enumerate(rows)}
    assert len(idx) == 98 and set.union(*(set(f["test_keys"]) for f in folds)) == set(idx)
    aggregate, local = [], []
    for n, r in enumerate(rows, 1):
        path = ROOT / r["graph_file"]
        if digest(path) != r["graph_sha256"]:
            raise ValueError("Graph hash mismatch: " + r["key"])
        graph = torch.load(path, map_location="cpu", weights_only=False)
        assert graph.x.shape == (r["graph_nodes"], 20) and graph.num_edges == r["graph_edges"]
        aggregate.append(base.graph_features(graph))
        local.append(local_features(graph))
        if n % 25 == 0:
            print(f"Verified {n}/98 graphs", flush=True)
    aggregate, local = np.stack(aggregate), np.stack(local)
    size = np.array([[math.log1p(r["graph_nodes"]), math.log1p(r["graph_edges"])] for r in rows])
    features = {"size_logistic": size, "graph_aggregate_logistic": np.c_[size, aggregate],
                "local_fraction_logistic": np.c_[size, local], "graph_aggregate_stumps": np.c_[size, aggregate]}
    predictions = defaultdict(list)
    for fold in folds:
        tr = np.array([idx[k] for k in fold["train_keys"]])
        te = np.array([idx[k] for k in fold["test_keys"]])
        assert not ({rows[i]["family"] for i in tr} & {rows[i]["family"] for i in te})
        y = np.array([rows[i]["label"] for i in tr])
        for name, matrix in features.items():
            model = base.boosted_stumps if name.endswith("stumps") else base.logistic
            prob, _ = model(matrix[tr], y, matrix[te])
            predictions[name].extend({"key": rows[i]["key"], "family": rows[i]["family"],
                                      "benchmark": rows[i]["benchmark"], "label": rows[i]["label"],
                                      "fold": fold["fold"], "score": float(p)} for i, p in zip(te, prob))
        print("Fold", fold["fold"], "complete", flush=True)
    summaries = {name: summarize(sorted(items, key=lambda r: r["key"])) for name, items in predictions.items()}
    families = sorted(summaries["size_logistic"]["by_family_auroc"])
    rng = np.random.default_rng(20261103)
    draws = rng.integers(0, len(families), (10000, len(families)))
    size_auc = np.array([summaries["size_logistic"]["by_family_auroc"][f] for f in families])
    for name, result in summaries.items():
        vector = np.array([result["by_family_auroc"][f] for f in families])
        delta = vector - size_auc
        result["family_bootstrap_95ci"] = np.quantile(vector[draws].mean(1), [.025, .975]).tolist()
        result["delta_vs_size"] = float(delta.mean())
        result["delta_bootstrap_95ci"] = np.quantile(delta[draws].mean(1), [.025, .975]).tolist()
    result = {"protocol_sha256": digest(ROOT / "experiments/trusthub_primary_v1/protocol.json"),
              "panel_sha256": digest(ROOT / "data/dataset_v2/trusthub_primary.json"),
              "folds_sha256": digest(ROOT / "data/dataset_v2/trusthub_folds.json"),
              "models": summaries, "size_audit": size_audit(rows),
              "pass_rule_met": summaries["graph_aggregate_logistic"]["delta_bootstrap_95ci"][0] > 0}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "predictions.json").write_text(json.dumps(predictions, indent=2) + "\n", encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass_rule_met": result["pass_rule_met"], "models": summaries}, indent=2), flush=True)


if __name__ == "__main__":
    main()
