"""Build v2 source-traced graph candidates using the separately versioned adapter."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/independent_benchmark_v2/runs"
REPORT = ROOT / "data/independent_benchmark_v2/graph_lineage.json"
sys.path.insert(0, str(ROOT / "experiments/independent_benchmark_v1"))
import build_graphs as base  # noqa: E402

base.OUT = OUT
base.VERSION = "independent_v2"


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "data/independent_benchmark_v2/manifest.json").read_text(encoding="utf-8"))
    prior = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {"records": []}
    for source in manifest["records"]:
        if args.host and source["host"] not in args.host:
            continue
        summary = json.loads((ROOT / source["folder"] / "summary.json").read_text(encoding="utf-8"))
        run = {"run_id": source["run_id"], "host": source["host"],
               "mechanism": source["mechanism"],
               "command": ["main.py", summary["netlist"]]}
        for variant in source["records"]:
            key = f"{source['run_id']}/{variant['source_path']}"
            if any(r["variant"] == key for r in prior["records"]):
                continue
            print("graph", key, flush=True)
            row = base.build(run, {"file": key, "sha256": variant["source_sha256"]})
            prior["records"].append(row)
            prior["status"] = "construction_derived_candidate_labels_not_reviewed"
            save_json(REPORT, prior)
            print(row["positive"], row["negative"], row["unknown"], flush=True)


if __name__ == "__main__":
    main()
