"""Compare frozen RTL and metadata predictions at the clean-source group level."""
import hashlib
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import summarize_predictions  # noqa: E402

RTL = ROOT / "data/rtl_lexical_v1/predictions.json"
CONTROL = ROOT / "data/rtl_lexical_v1/metadata_controls_predictions.json"
FOLDS = ROOT / "data/integrated/group_folds.json"
OUT = ROOT / "data/audit_v1/error_overlap.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_sign_flip(differences):
    """Two-sided and positive one-sided exact tests of group metric differences."""
    observed = sum(differences) / len(differences)
    reference = [sum(sign * value for sign, value in zip(signs, differences)) / len(differences)
                 for signs in itertools.product((-1, 1), repeat=len(differences))]
    tolerance = 1e-12
    return {"groups": len(differences), "permutations": len(reference),
            "observed_mean_difference": observed,
            "one_sided_p": sum(value >= observed - tolerance for value in reference) / len(reference),
            "two_sided_p": sum(abs(value) >= abs(observed) - tolerance for value in reference) / len(reference),
            "minimum_possible_one_sided_p": 1 / len(reference),
            "minimum_possible_two_sided_p_for_nonzero_symmetric_statistic": 2 / len(reference)}


def selected(path, kind):
    rows = json.loads(path.read_text(encoding="utf-8"))
    if kind == "rtl":
        return [r for r in rows if r["arm"] == "original" and r["setting"] == "within"]
    return [r for r in rows if r["feature"] == "length_plus_chunks"
            and r["arm"] == "original" and r["setting"] == "within"]


def main():
    rtl = selected(RTL, "rtl")
    control = selected(CONTROL, "control")
    folds = json.loads(FOLDS.read_text(encoding="utf-8"))["folds"]
    key = lambda r: (r["benchmark"], r["true_label"])
    a, b = ({key(r): r for r in rows} for rows in (rtl, control))
    if len(a) != 42 or len(b) != 42 or set(a) != set(b):
        raise ValueError("Predictions do not cover the same 42 design sides")
    error_a = {k for k, r in a.items() if r["predicted_label"] != r["true_label"]}
    error_b = {k for k, r in b.items() if r["predicted_label"] != r["true_label"]}
    per_group = []
    for fold in folds:
        group = fold["fold"]
        expected = set(fold["test_benchmarks"])
        rows_a = [r for r in rtl if r["fold"] == group]
        rows_b = [r for r in control if r["fold"] == group]
        if {r["benchmark"] for r in rows_a} != expected or {r["benchmark"] for r in rows_b} != expected:
            raise ValueError(f"Fold membership changed: {group}")
        stats_a, stats_b = summarize_predictions(rows_a)["pooled"], summarize_predictions(rows_b)["pooled"]
        per_group.append({"fold": group, "pairs": len(expected), "rtl": stats_a,
                          "metadata": stats_b,
                          "balanced_accuracy_difference": stats_a["balanced_accuracy"] - stats_b["balanced_accuracy"],
                          "auroc_difference": stats_a["auroc"] - stats_b["auroc"]})
    result = {"status": "retrospective_inspected_folds",
              "input_sha256": {"rtl_predictions": sha256(RTL),
                               "metadata_predictions": sha256(CONTROL), "folds": sha256(FOLDS)},
              "design_sides": len(a), "independent_clean_source_groups": len(folds),
              "rtl_errors": len(error_a), "metadata_errors": len(error_b),
              "shared_errors": len(error_a & error_b),
              "rtl_only_errors": sorted([list(k) for k in error_a - error_b]),
              "metadata_only_errors": sorted([list(k) for k in error_b - error_a]),
              "per_group": per_group,
              "exact_group_sign_flip": {
                  "balanced_accuracy": exact_sign_flip([r["balanced_accuracy_difference"] for r in per_group]),
                  "auroc": exact_sign_flip([r["auroc_difference"] for r in per_group])},
              "interpretation": "Equal per-group metrics do not imply equal decisions; no evidence of RTL superiority over metadata in these three groups."}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("rtl_errors", "metadata_errors", "shared_errors",
                                                "exact_group_sign_flip")}, indent=2))


if __name__ == "__main__":
    main()
