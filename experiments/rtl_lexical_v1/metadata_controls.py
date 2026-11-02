"""Evaluate RTL length and CodeBERT chunk-count shortcuts on frozen folds.

The transformed arms keep character and line counts fixed, but tokenization
can change the number of CodeBERT windows. This script never loads embeddings.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import summarize_predictions  # noqa: E402
from evaluate import ARMS, fit, paired_ranking, predict  # noqa: E402

RUN = ROOT / "runs/rtl_lexical_v1"
EVIDENCE = ROOT / "data/rtl_lexical_v1"
FEATURES = ("length", "chunks", "length_plus_chunks")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_counts(records, transformed):
    chars = lines = 0
    for item in records:
        path = ROOT / item["transformed" if transformed else "original"]
        content = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        expected = item["transformed_sha256" if transformed else "original_sha256"]
        if hashlib.sha256(content.encode("utf-8")).hexdigest() != expected:
            raise ValueError(f"Source hash mismatch: {path}")
        chars += len(content)
        lines += len(content.splitlines())
    return chars, lines


def build_features(samples, preparation, original, progress):
    source = {(r["benchmark"], r["side"], r["arm"]): r for r in preparation["records"]}
    original_chunks = {(r["benchmark"], r["side"]): r["num_chunks"] for r in original["records"]}
    control_chunks = {(r["benchmark"], r["side"], r["arm"]): r["chunks"]
                      for r in progress["records"]}
    values = {}
    raw = []
    for sample in samples:
        benchmark, side = sample["benchmark"], sample["class_name"]
        reference = source[(benchmark, side, "comments")]
        original_size = source_counts(reference["files"], False)
        for arm in ARMS:
            if arm == "original":
                size, chunks = original_size, original_chunks[(benchmark, side)]
            else:
                size = source_counts(source[(benchmark, side, arm)]["files"], True)
                chunks = control_chunks[(benchmark, side, arm)]
            if size != original_size:
                raise ValueError(f"Length control changed for {benchmark}/{side}/{arm}")
            key = (benchmark, side, arm)
            values[key] = {
                "length": [math.log1p(size[0]), math.log1p(size[1])],
                "chunks": [math.log1p(chunks)],
                "length_plus_chunks": [math.log1p(size[0]), math.log1p(size[1]), math.log1p(chunks)],
            }
            raw.append({"benchmark": benchmark, "side": side, "arm": arm,
                        "chars": size[0], "lines": size[1], "chunks": chunks})
    if len(raw) != len(samples) * len(ARMS):
        raise ValueError("Incomplete metadata-control cohort")
    return values, raw


def evaluate(samples, folds, values):
    rows = []
    for feature_name in FEATURES:
        for arm in ARMS:
            settings = ("within",) if arm == "original" else ("within", "original_to_control")
            for setting in settings:
                for fold in folds:
                    train = [s for s in samples if s["benchmark"] in fold["train_benchmarks"]]
                    test = [s for s in samples if s["benchmark"] in fold["test_benchmarks"]]
                    if set(s["benchmark"] for s in train) & set(s["benchmark"] for s in test):
                        raise ValueError("Train/test benchmark overlap")
                    training_arm = "original" if setting == "original_to_control" else arm
                    x_train = torch.tensor([values[(s["benchmark"], s["class_name"], training_arm)][feature_name]
                                            for s in train], dtype=torch.float32)
                    x_test = torch.tensor([values[(s["benchmark"], s["class_name"], arm)][feature_name]
                                           for s in test], dtype=torch.float32)
                    model, mean, std = fit(x_train, torch.tensor([s["label"] for s in train]), 42 + fold["fold"])
                    for sample, score in zip(test, predict(model, mean, std, x_test)):
                        rows.append({"feature": feature_name, "arm": arm, "setting": setting,
                                     "fold": fold["fold"], "benchmark": sample["benchmark"],
                                     "true_label": sample["label"], "predicted_label": int(score >= 0.5),
                                     "prob_trojan": score})
    results = {}
    for feature_name in FEATURES:
        for arm in ARMS:
            settings = ("within",) if arm == "original" else ("within", "original_to_control")
            for setting in settings:
                key = f"{feature_name}/{arm}/{setting}"
                selected = [r for r in rows if r["feature"] == feature_name
                            and r["arm"] == arm and r["setting"] == setting]
                if len(selected) != len(samples):
                    raise ValueError(f"Incomplete prediction group: {key}")
                results[key] = {"metrics": summarize_predictions(selected),
                                "paired_ranking": paired_ranking(selected)}
    return rows, results


def main():
    samples = read_json(ROOT / "data/integrated/paired_manifest.json")["samples"]
    folds = read_json(ROOT / "data/integrated/group_folds.json")["folds"]
    paths = {
        "paired_manifest": ROOT / "data/integrated/paired_manifest.json",
        "group_folds": ROOT / "data/integrated/group_folds.json",
        "lexical_manifest": RUN / "manifest.json",
        "original_rtl_manifest": ROOT / "runs/rtl_clean_v1/manifest.json",
        "embedding_progress": RUN / "embedding_progress.json",
        "compilation_verification": RUN / "verification.json",
    }
    verification = read_json(paths["compilation_verification"])
    if verification["passed"] != 126 or len(verification["checks"]) != 126:
        raise ValueError("Lexical sources did not pass the complete compilation check")
    values, raw = build_features(samples, read_json(paths["lexical_manifest"]),
                                 read_json(paths["original_rtl_manifest"]),
                                 read_json(paths["embedding_progress"]))
    rows, results = evaluate(samples, folds, values)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    predictions = EVIDENCE / "metadata_controls_predictions.json"
    predictions.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    summary = {"status": "exploratory_development_folds", "n_design_sides": len(samples),
               "independent_clean_source_groups": 3, "threshold": 0.5,
               "fit": "train-fold-only standardization, class-weighted linear classifier, seed 42 + fold",
               "source_hashes": {name: sha256(path) for name, path in paths.items()},
               "predictions_sha256": sha256(predictions),
               "chunk_totals": {arm: sum(r["chunks"] for r in raw if r["arm"] == arm) for arm in ARMS},
               "results": results}
    (EVIDENCE / "metadata_controls.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for key, result in results.items():
        print(key, "BA", result["metrics"]["pooled"]["balanced_accuracy"],
              "AUROC", result["metrics"]["pooled"]["auroc"])


if __name__ == "__main__":
    main()
