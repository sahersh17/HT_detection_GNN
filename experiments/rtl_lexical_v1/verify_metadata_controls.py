"""Verify saved metadata-control inputs, predictions, and reported metrics."""
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import summarize_predictions  # noqa: E402
from evaluate import ARMS, paired_ranking  # noqa: E402

EVIDENCE = ROOT / "data/rtl_lexical_v1"
INPUTS = {
    "paired_manifest": ROOT / "data/integrated/paired_manifest.json",
    "group_folds": ROOT / "data/integrated/group_folds.json",
    "lexical_manifest": ROOT / "runs/rtl_lexical_v1/manifest.json",
    "original_rtl_manifest": ROOT / "runs/rtl_clean_v1/manifest.json",
    "embedding_progress": ROOT / "runs/rtl_lexical_v1/embedding_progress.json",
    "compilation_verification": ROOT / "runs/rtl_lexical_v1/verification.json",
}


def check_number(actual, expected):
    if isinstance(actual, float):
        return math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10)
    return actual == expected


def main():
    report = json.loads((EVIDENCE / "metadata_controls.json").read_text(encoding="utf-8"))
    path = EVIDENCE / "metadata_controls_predictions.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != report["predictions_sha256"]:
        raise ValueError("Prediction hash mismatch")
    for name, input_path in INPUTS.items():
        if hashlib.sha256(input_path.read_bytes()).hexdigest() != report["source_hashes"][name]:
            raise ValueError(f"Input hash mismatch: {name}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    samples = json.loads(INPUTS["paired_manifest"].read_text(encoding="utf-8"))["samples"]
    folds = json.loads(INPUTS["group_folds"].read_text(encoding="utf-8"))["folds"]
    fold_by_benchmark = {b: f["fold"] for f in folds for b in f["test_benchmarks"]}
    expected_members = {(s["benchmark"], s["label"], fold_by_benchmark[s["benchmark"]])
                        for s in samples}
    for key, saved in report["results"].items():
        feature, arm, setting = key.split("/")
        selected = [r for r in rows if (r["feature"], r["arm"], r["setting"]) ==
                    (feature, arm, setting)]
        members = {(r["benchmark"], r["true_label"], r["fold"]) for r in selected}
        if len(selected) != len(samples) or members != expected_members:
            raise ValueError(f"Incomplete or wrong folds: {key}")
        computed = {"metrics": summarize_predictions(selected),
                    "paired_ranking": paired_ranking(selected)}
        for section, value in computed.items():
            if section == "metrics":
                for group, metrics in value.items():
                    for metric, actual in metrics.items():
                        if not check_number(actual, saved[section][group][metric]):
                            raise ValueError(f"Metric mismatch: {key}/{group}/{metric}")
            else:
                for metric, actual in value.items():
                    if not check_number(actual, saved[section][metric]):
                        raise ValueError(f"Ranking mismatch: {key}/{metric}")
    if set(report["chunk_totals"]) != set(ARMS):
        raise ValueError("Missing chunk-count arm")
    print(f"Verified {len(report['results'])} groups, {len(rows)} predictions, inputs and metrics")


if __name__ == "__main__":
    main()
