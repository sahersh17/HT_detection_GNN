"""Assess a training-only decision threshold for an existing experiment run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from model import TypedFusion
from train import EXTERNAL, OUT, ROOT, load_data


def choose_threshold(scores: list[float], labels: list[int]) -> tuple[float, float]:
    ordered = sorted(set(scores))
    choices = [ordered[0] - 1e-6, ordered[-1] + 1e-6]
    choices += [(a + b) / 2 for a, b in zip(ordered, ordered[1:])]
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        raise ValueError("Both labels are needed for calibration")
    ranked = []
    for threshold in choices:
        tpr = sum(y == 1 and p >= threshold for p, y in zip(scores, labels)) / positives
        tnr = sum(y == 0 and p < threshold for p, y in zip(scores, labels)) / negatives
        ranked.append(((tpr + tnr) / 2, -abs(threshold - 0.5), threshold))
    balanced, _, threshold = max(ranked)
    return threshold, balanced


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", type=Path, help="Completed training directory")
    args = ap.parse_args()
    run = args.run.resolve()
    if not run.is_relative_to(OUT / "training"):
        ap.error("Run must be under runs/typed_fusion_v1/training")
    protocol = json.loads((run / "protocol.json").read_text())
    if protocol["status"] != "completed" or protocol.get("ablation", "none") != "none":
        ap.error("Calibration requires a completed unablated run")
    arm = protocol["arm"]
    samples, manifest_sha = load_data()
    if manifest_sha != protocol["manifest_sha256"]:
        raise ValueError("Prepared manifest changed since training")
    folds = json.loads((ROOT / "data/integrated/group_folds.json").read_text())["folds"]
    test_rows = json.loads((run / "predictions.json").read_text())
    torch.set_num_threads(4)
    result = {"status": "training_only_threshold_diagnostic", "arm": arm,
              "run": run.relative_to(ROOT).as_posix(), "folds": {}}
    for name in protocol["folds"]:
        if name == "external":
            train = [r for r in samples if r["benchmark"] not in EXTERNAL]
        else:
            held = set(next(f["test_benchmarks"] for f in folds if str(f["fold"]) == name))
            train = [r for r in samples if r["benchmark"] not in EXTERNAL and r["benchmark"] not in held]
        net = TypedFusion()
        net.load_state_dict(torch.load(run / f"{arm}_{name}.pt", map_location="cpu", weights_only=True))
        net.eval()
        with torch.no_grad():
            scores = [float(net(item, arm)["logit"].sigmoid()) for item in train]
        threshold, train_bacc = choose_threshold(scores, [item["label"] for item in train])
        rows = [r for r in test_rows if r["fold"] == name]
        y = [r["true_label"] for r in rows]
        p = [int(r["prob_trojan"] >= threshold) for r in rows]
        tp = sum(a == 1 and b == 1 for a, b in zip(y, p))
        tn = sum(a == 0 and b == 0 for a, b in zip(y, p))
        result["folds"][name] = {"threshold": threshold, "train_balanced_accuracy": train_bacc,
                                 "test_balanced_accuracy": (tp / sum(y) + tn / (len(y) - sum(y))) / 2,
                                 "test_tn": tn, "test_fp": len(y) - sum(y) - tn,
                                 "test_fn": sum(y) - tp, "test_tp": tp}
        print(f"{name}: train threshold={threshold:.4f}, train bacc={train_bacc:.3f}, "
              f"test bacc={result['folds'][name]['test_balanced_accuracy']:.3f}", flush=True)
    (run / "calibration.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
