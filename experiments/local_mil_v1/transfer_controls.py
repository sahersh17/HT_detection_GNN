"""Simple controls on the exact fold-4-to-folds-0-3 transfer split."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/dataset_stage2"))
from baselines import digest, graph_features, logistic, metrics

torch.set_num_threads(2)


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    records = sorted((r for r in read("data/dataset_stage1/records.json") if r["role"] == "development"), key=lambda r: r["key"])
    manifest = {r["key"]: r for r in read("data/training_audit_v3/manifest.json")["records"]}
    train_keys = set(read("data/dataset_stage1/folds.json")["folds"][4]["test_keys"])
    graph = []
    for row in records:
        m = manifest[row["key"]]
        path = ROOT / m["file"]
        if digest(path) != m["sha256"] or m["sha256"] != row["prepared_sha256"]:
            raise ValueError(row["key"])
        sample = torch.load(path, weights_only=False, map_location="cpu")
        graph.append(graph_features(sample["graph"]))
    graph = np.stack(graph)
    size = np.array([[math.log1p(r["legacy_nodes"]), math.log1p(r["legacy_edges"])] for r in records])
    train = np.array([i for i, r in enumerate(records) if r["key"] in train_keys])
    test = np.array([i for i, r in enumerate(records) if r["key"] not in train_keys])
    y = np.array([records[i]["label"] for i in train])
    assert len(train) == 38 and len(test) == 147
    result = {}
    for name, features in (("size_logistic", size), ("graph_aggregates_logistic", np.column_stack([size, graph]))):
        probs, _ = logistic(features[train], y, features[test])
        rows = [{"key": records[i]["key"], "host": records[i]["host"], "label": records[i]["label"], "probability": float(p)} for i, p in zip(test, probs)]
        result[name] = {"overall": metrics(rows, probs), "predictions": rows}
    path = ROOT / "data/local_mil_v1/transfer_controls.json"
    path.write_text(json.dumps({"scope": "fold 4 training, folds 0-3 scoring; same split as local_mil_v1 transfer", "models": result}, indent=2), encoding="utf-8")
    print(json.dumps({name: x["overall"] for name, x in result.items()}, indent=2))


if __name__ == "__main__":
    main()
