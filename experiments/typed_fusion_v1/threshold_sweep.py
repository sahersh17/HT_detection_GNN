"""Compare fixed and training-only threshold rules on saved experiment runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from calibrate import choose_threshold
from model import TypedFusion
from train import EXTERNAL, OUT, ROOT, load_data


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lower, upper = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[lower] + (pos - lower) * (ordered[upper] - ordered[lower])


def metrics(rows: list[dict], threshold: float) -> dict:
    tn = fp = fn = tp = 0
    for row in rows:
        predicted = int(row["prob_trojan"] >= threshold)
        if row["true_label"] == 0:
            fp += predicted
            tn += 1 - predicted
        else:
            tp += predicted
            fn += 1 - predicted
    return {"threshold": threshold, "tn": tn, "fp": fp, "fn": fn, "tp": tp,
            "balanced_accuracy": (tn / (tn + fp) + tp / (tp + fn)) / 2}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", type=Path)
    args = ap.parse_args()
    run = args.run.resolve()
    if not run.is_relative_to(OUT / "training"):
        ap.error("Run must be under runs/typed_fusion_v1/training")
    protocol = json.loads((run / "protocol.json").read_text())
    if protocol["status"] != "completed" or protocol["setting"] != "external":
        ap.error("Only completed external runs are supported")
    samples, manifest_sha = load_data()
    if manifest_sha != protocol["manifest_sha256"]:
        raise ValueError("Prepared manifest changed since training")
    train = [r for r in samples if r["benchmark"] not in EXTERNAL]
    arm = protocol["arm"]
    net = TypedFusion()
    net.load_state_dict(torch.load(run / f"{arm}_external.pt", map_location="cpu", weights_only=True))
    net.eval()
    torch.set_num_threads(4)
    with torch.no_grad():
        train_scores = [float(net(item, arm)["logit"].sigmoid()) for item in train]
    labels = [r["label"] for r in train]
    clean_scores = [score for score, label in zip(train_scores, labels) if label == 0]
    balanced, _ = choose_threshold(train_scores, labels)
    rules = {"fixed_0_5": 0.5, "train_balanced": balanced,
             "clean_q90": quantile(clean_scores, 0.90),
             "clean_q95": quantile(clean_scores, 0.95),
             "clean_max_plus_epsilon": max(clean_scores) + 1e-6}
    test = json.loads((run / "predictions.json").read_text())
    result = {"run": run.relative_to(ROOT).as_posix(),
              "scope": "previously inspected five-pair diagnostic; thresholds derived only from training scores",
              "train_clean_score_range": [min(clean_scores), max(clean_scores)],
              "train_trojan_score_range": [min(s for s, y in zip(train_scores, labels) if y == 1),
                                           max(s for s, y in zip(train_scores, labels) if y == 1)],
              "external_score_range": [min(r["prob_trojan"] for r in test),
                                       max(r["prob_trojan"] for r in test)],
              "rules": {name: metrics(test, threshold) for name, threshold in rules.items()}}
    (run / "threshold_sweep.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
