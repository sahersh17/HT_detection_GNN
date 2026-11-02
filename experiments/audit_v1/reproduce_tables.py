"""Recompute compact audit tables from saved predictions without large runs/."""
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from six_host_rtl_control import ARMS, SEEDS, metrics  # noqa: E402
from compare_shortcuts import exact_sign_flip  # noqa: E402

DATA = ROOT / "data/audit_v1"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual, expected):
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(close(actual[k], value) for k, value in expected.items())
    if isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(close(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, float):
        return math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10)
    return actual == expected


def main():
    summary = json.loads((DATA / "six_host_summary.json").read_text(encoding="utf-8"))
    predictions_path = DATA / "six_host_predictions.json"
    if sha256(predictions_path) != summary["predictions_sha256"]:
        raise ValueError("Six-host prediction hash changed")
    rows = json.loads(predictions_path.read_text(encoding="utf-8"))
    if len(rows) != len(SEEDS) * len(ARMS) * summary["samples"]:
        raise ValueError("Six-host prediction count mismatch")
    for seed in SEEDS:
        for arm in ARMS:
            selected = [r for r in rows if r["seed"] == seed and r["arm"] == arm]
            expected = summary["results"][str(seed)][arm]
            if not close(metrics(selected), expected["pooled"]):
                raise ValueError(f"Pooled metric mismatch: {seed}/{arm}")
            for host in summary["hosts"]:
                subset = [r for r in selected if r["family"] == host]
                if not close(metrics(subset), expected["per_host"][host]):
                    raise ValueError(f"Host metric mismatch: {seed}/{arm}/{host}")
            auc = sum(expected["per_host"][h]["auroc"] for h in summary["hosts"]) / len(summary["hosts"])
            if not close(auc, expected["equal_host_auroc"]):
                raise ValueError("Equal-host metric mismatch")
    overlap = json.loads((DATA / "error_overlap.json").read_text(encoding="utf-8"))
    diffs = {name: [r[name + "_difference"] for r in overlap["per_group"]]
             for name in ("balanced_accuracy", "auroc")}
    for name, values in diffs.items():
        if not close(exact_sign_flip(values), overlap["exact_group_sign_flip"][name]):
            raise ValueError(f"Permutation mismatch: {name}")
    print(f"Recomputed {len(SEEDS)} seeds, {len(ARMS)} arms, {len(summary['hosts'])} hosts and exact group tests")


if __name__ == "__main__":
    main()
