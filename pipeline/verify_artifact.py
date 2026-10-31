"""Verify the portable pilot results against their manifest, folds, and inputs.

Run from the repository root: python pipeline/verify_artifact.py
This checks integrity and scoring, not the scientific validity of the data.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from metrics import summarize_predictions


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_metrics(saved, calculated):
    if saved.keys() != calculated.keys():
        return False
    for key, value in calculated.items():
        other = saved[key]
        if value is None or isinstance(value, int):
            if other != value:
                return False
        elif not isinstance(other, (float, int)) or not math.isclose(other, value, rel_tol=1e-10, abs_tol=1e-10):
            return False
    return True


def verify(root):
    root = Path(root)
    errors = []
    pilot = root / "results" / "legacy_baselines"
    provenance = json.loads((pilot / "provenance.json").read_text(encoding="utf-8"))
    samples = json.loads((root / "data" / "integrated" / "paired_manifest.json").read_text(encoding="utf-8"))["samples"]
    folds = json.loads((root / "data" / "integrated" / "group_folds.json").read_text(encoding="utf-8"))["folds"]

    for relative, expected in provenance["hashes"].items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing recorded input: {relative}")
        elif _sha256(path) != expected:
            errors.append(f"input hash changed: {relative}")

    expected = {(s["benchmark"], s["label"]): s for s in samples}
    if len(expected) != len(samples):
        errors.append("duplicate benchmark/label pair in manifest")
    test_fold = {}
    for fold in folds:
        train, test = set(fold["train_benchmarks"]), set(fold["test_benchmarks"])
        if train & test:
            errors.append(f"fold {fold['fold']} has train/test overlap")
        clean_train = {s["source_text_sha256"] for s in samples if s["benchmark"] in train and s["label"] == 0}
        clean_test = {s["source_text_sha256"] for s in samples if s["benchmark"] in test and s["label"] == 0}
        if clean_train & clean_test:
            errors.append(f"fold {fold['fold']} shares clean RTL across train/test")
        for benchmark in test:
            if benchmark in test_fold:
                errors.append(f"benchmark tested in multiple folds: {benchmark}")
            test_fold[benchmark] = fold["fold"]
    if set(test_fold) != {s["benchmark"] for s in samples}:
        errors.append("test folds do not cover every benchmark exactly once")

    model_metrics = {}
    for model in ("rtl", "gnn", "fusion"):
        folder = pilot / model
        rows = json.loads((folder / "predictions.json").read_text(encoding="utf-8"))
        saved = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        keys = [(r["benchmark"], r["true_label"]) for r in rows]
        if len(rows) != len(expected) or set(keys) != set(expected) or len(set(keys)) != len(keys):
            errors.append(f"{model}: predictions do not match all manifest samples exactly once")
        for row in rows:
            benchmark = row["benchmark"]
            probability = row["prob_trojan"]
            if row["fold"] != test_fold.get(benchmark):
                errors.append(f"{model}: wrong test fold for {benchmark}")
            if not isinstance(probability, (int, float)) or not math.isfinite(probability) or not 0 <= probability <= 1:
                errors.append(f"{model}: invalid probability for {benchmark}")
            elif row["predicted_label"] != int(probability >= 0.5):
                errors.append(f"{model}: predicted label disagrees with threshold for {benchmark}")
        calculated = summarize_predictions(rows)
        for split, value in calculated.items():
            if split not in saved or not _same_metrics(saved[split], value):
                errors.append(f"{model}: saved {split} metrics disagree with predictions")
        model_metrics[model] = calculated["pooled"]
    return {"status": "verified" if not errors else "failed", "evaluation_status": "exploratory_pilot",
            "samples": len(samples), "benchmarks": len(test_fold),
            "independent_clean_source_groups": len({s["source_text_sha256"] for s in samples if s["label"] == 0}),
            "models": {name: {"balanced_accuracy": metrics["balanced_accuracy"], "macro_f1": metrics["macro_f1"]}
                       for name, metrics in model_metrics.items()}, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = verify(args.root)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "verified" else 1)


if __name__ == "__main__":
    main()
