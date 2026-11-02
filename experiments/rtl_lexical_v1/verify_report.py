"""Recompute tracked ablation metrics and verify their source-artifact hashes."""
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import summarize_predictions  # noqa: E402
from evaluate import paired_ranking  # noqa: E402

RUN = ROOT / "runs/rtl_lexical_v1"
EVIDENCE = ROOT / "data/rtl_lexical_v1"


def main():
    summary = json.loads((EVIDENCE / "summary.json").read_text(encoding="utf-8"))
    rows = json.loads((EVIDENCE / "predictions.json").read_text(encoding="utf-8"))
    for name, expected in summary["source_artifact_hashes"].items():
        actual = hashlib.sha256((RUN / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Artifact hash changed: {name}")
    if len(rows) != 42 * 7:
        raise ValueError(f"Expected 294 predictions, found {len(rows)}")
    for key, expected in summary["results"].items():
        arm, setting = key.split("/")
        selected = [row for row in rows if row["arm"] == arm and row["setting"] == setting]
        computed = summarize_predictions(selected)
        computed["paired_ranking"] = paired_ranking(selected)
        if len(selected) != 42:
            raise ValueError(f"Incomplete prediction group: {key}")
        for section, metrics in computed.items():
            for metric, value in metrics.items():
                prior = expected[section][metric]
                if isinstance(value, float):
                    if not math.isclose(value, prior, rel_tol=1e-12, abs_tol=1e-12):
                        raise ValueError(f"Metric mismatch: {key}/{section}/{metric}")
                elif value != prior:
                    raise ValueError(f"Metric mismatch: {key}/{section}/{metric}")
    print("Seven groups, 294 predictions, metrics and artifact hashes verified")


if __name__ == "__main__":
    main()
