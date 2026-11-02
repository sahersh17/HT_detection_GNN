"""Yosys SAT output-difference witnesses for v2 combinational host variants."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/independent_benchmark_v2/runs"
REPORT = ROOT / "data/independent_benchmark_v2/formal_combinational.json"
sys.path.insert(0, str(ROOT / "experiments/independent_benchmark_v1"))
import formal_check as base  # noqa: E402

base.OUT = OUT


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
        if source["mechanism"] != "combinational" or source["host"].startswith("s") or (args.host and source["host"] not in args.host):
            continue
        folder = ROOT / source["folder"]
        upstream_summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        run = {"run_id": source["run_id"], "host": source["host"],
               "command": ["main.py", upstream_summary["netlist"]]}
        for variant in source["records"]:
            key = f"{source['run_id']}/{variant['source_path']}"
            previous = next((r for r in prior["records"] if r["variant"] == key), None)
            if previous and previous["status"] == "independent_combinational_output_difference_witness":
                continue
            print("formal", key, flush=True)
            row = base.verify_variant(run, {"file": key, "sha256": variant["source_sha256"]})
            if previous:
                prior["records"].remove(previous)
            prior["records"].append(row)
            prior["status"] = "independent_combinational_host_output_witnesses_only"
            save_json(REPORT, prior)
            print(row["status"], len(row.get("witness", {}).get("different_outputs", [])), flush=True)
    if any(r["status"] != "independent_combinational_output_difference_witness" for r in prior["records"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
