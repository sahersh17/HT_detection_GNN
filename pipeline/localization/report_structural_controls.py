"""Descriptive host bootstrap for unreviewed candidate-label controls."""
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/localization_gate_audit"


def main():
    records = json.loads((BASE / "structural_controls.json").read_text(encoding="utf-8"))["designs"]
    hosts = defaultdict(list)
    for row in records:
        hosts[row["family"]].append(row)
    methods = next(iter(records))["methods"]
    rng = random.Random(42)
    summary = {}
    for name in methods:
        per_host = {host: statistics.mean(r["methods"][name]["auroc"] for r in rows)
                    for host, rows in hosts.items()}
        values = list(per_host.values())
        boot = sorted(statistics.mean(rng.choice(values) for _ in values) for _ in range(10000))
        summary[name] = {"equal_host_mean_auroc": statistics.mean(values),
                         "host_bootstrap_95_percentile": [boot[250], boot[9749]],
                         "per_host": per_host}
    result = {"status": "exploratory_unreviewed_candidates", "hosts": len(hosts),
              "designs": len(records), "known_positive_nodes": sum(r["methods"]["fanin"]["positives"] for r in records),
              "limitations": "Only three inspected hosts; intervals are descriptive and labels are unreviewed.",
              "methods": summary}
    (BASE / "structural_controls_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for name, row in summary.items():
        print(name, round(row["equal_host_mean_auroc"], 3), row["host_bootstrap_95_percentile"])


if __name__ == "__main__":
    main()
