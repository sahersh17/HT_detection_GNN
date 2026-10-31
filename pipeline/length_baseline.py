"""Sanity baseline: classify using only synthesizable RTL size, no semantics.

Run on the same three clean-source-held-out pilot folds. Strong performance
would warn that benchmark editing artifacts can drive detection scores.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

import config as C
from metrics import summarize_predictions
from train_cv import class_weights

sys.path.insert(0, str(C.ROOT / "pipeline" / "provenance"))
from build import source_files  # noqa: E402


def features(sample):
    files, _ = source_files(sample["benchmark"], sample["class_name"])
    contents = [p.read_text(encoding="utf-8", errors="replace") for p in files]
    chars = sum(len(s) for s in contents)
    lines = sum(len(s.splitlines()) for s in contents)
    return [math.log1p(chars), math.log1p(lines)]


def graph_size_features(sample):
    path = C.PROVENANCE_ROOT / sample["benchmark"] / sample["class_name"] / "metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    return [math.log1p(metadata["num_nodes"]), math.log1p(metadata["num_edges"])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-size", action="store_true", help="Use only graph node and edge counts")
    args = parser.parse_args()
    feature_fn = graph_size_features if args.graph_size else features
    samples = json.loads(C.PAIRED_MANIFEST.read_text(encoding="utf-8"))["samples"]
    folds = json.loads(C.FOLDS.read_text(encoding="utf-8"))["folds"]
    rows = []
    for fold in folds:
        train_set, test_set = set(fold["train_benchmarks"]), set(fold["test_benchmarks"])
        train = [s for s in samples if s["benchmark"] in train_set]
        test = [s for s in samples if s["benchmark"] in test_set]
        torch.manual_seed(C.SEED + fold["fold"])
        x_train = torch.tensor([feature_fn(s) for s in train], dtype=torch.float32)
        x_test = torch.tensor([feature_fn(s) for s in test], dtype=torch.float32)
        mean, std = x_train.mean(0), x_train.std(0).clamp(min=1e-6)
        x_train, x_test = (x_train - mean) / std, (x_test - mean) / std
        labels = torch.tensor([s["label"] for s in train])
        classifier = torch.nn.Linear(2, 2)
        optimizer = torch.optim.LBFGS(classifier.parameters(), max_iter=100)
        weights = class_weights(labels.tolist(), torch.device("cpu"))

        def closure():
            optimizer.zero_grad()
            loss = F.cross_entropy(classifier(x_train), labels, weight=weights)
            loss.backward()
            return loss

        optimizer.step(closure)
        with torch.no_grad():
            probabilities = torch.softmax(classifier(x_test), -1)[:, 1].tolist()
        rows += [{"fold": fold["fold"], "benchmark": s["benchmark"], "true_label": int(s["label"]),
                  "predicted_label": int(p >= 0.5), "prob_trojan": float(p)}
                 for s, p in zip(test, probabilities)]
    out = C.RUNS / ("provenance_clean_graph_size" if args.graph_size else "provenance_clean_length")
    out.mkdir(parents=True, exist_ok=True)
    summary = summarize_predictions(rows)
    (out / "predictions.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    descriptions = (["log1p graph nodes", "log1p graph edges"] if args.graph_size else
                    ["log1p RTL characters", "log1p RTL lines"])
    (out / "summary.json").write_text(json.dumps({"evaluation_status": "exploratory_sanity_check",
                                                   "features": descriptions,
                                                   "seed": C.SEED, **summary}, indent=2), encoding="utf-8")
    print(json.dumps(summary["pooled"], indent=2))


if __name__ == "__main__":
    main()
