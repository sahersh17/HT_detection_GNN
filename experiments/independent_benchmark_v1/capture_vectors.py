"""Regenerate pinned insertion choices to expose their activation care bits.

The upstream summary omits the input vector. This script intercepts the
generator return value without editing its pinned source, verifies that the
regenerated netlist hashes match the original pilot, and saves the care bits.
Those bits are then checked by a separate verifier; they are not proof alone.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "runs/third_party/date2025_vendor"
OUT = ROOT / "runs/independent_benchmark_v1"
EVIDENCE = ROOT / "data/independent_benchmark_v1/activation_vectors.json"
sys.path.insert(0, str(VENDOR))
from ht_framework import pipeline  # noqa: E402


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append")
    args = parser.parse_args()
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads(EVIDENCE.read_text(encoding="utf-8")) if EVIDENCE.exists() else {"records": []}
    for run in manifest["records"]:
        if run["mechanism"] != "sequential" or (args.host and run["host"] not in args.host):
            continue
        if any(row["run_id"] == run["run_id"] for row in report["records"]):
            print("skip", run["run_id"], flush=True)
            continue
        settings = json.loads((Path(__file__).parent / "protocol.json").read_text(encoding="utf-8"))["generator"]["pilot_parameters"]
        source = run["command"][1]
        captures = []
        original = pipeline.ti.insert_trojan

        def intercept(*args, **kwargs):
            info = original(*args, **kwargs)
            captures.append(info)
            return info

        temp = OUT / "vector_regen" / run["run_id"]
        prior_cwd = Path.cwd()
        pipeline.ti.insert_trojan = intercept
        try:
            os.chdir(VENDOR)
            result = pipeline.run(netlist_path=source, outdir=str(temp),
                                  q=settings["trigger_nodes"],
                                  num_instances=settings["instances_per_host_mechanism"],
                                  theta_fraction=0.2, num_vectors=settings["vectors"],
                                  trojan_type="sequential", counter_width=settings["counter_width"],
                                  detection_patterns=0, run_detection=False,
                                  max_rare_nodes=settings["max_rare"],
                                  validate_each=False, visualize=False,
                                  seed=run["seed"], verbose=False)
        finally:
            pipeline.ti.insert_trojan = original
            os.chdir(prior_cwd)
        if len(captures) != len(run["variants"]) or len(result["instances"]) != len(captures):
            raise ValueError(f"Regeneration count mismatch: {run['run_id']}")
        variants = []
        for original_row, info in zip(run["variants"], captures):
            regenerated = Path(info["output_file"])
            if sha256(regenerated) != original_row["sha256"]:
                raise ValueError(f"Regenerated source differs: {run['run_id']}")
            variants.append({"file": original_row["file"],
                             "source_sha256": original_row["sha256"],
                             "merged_care_bits": info["merged_tv"],
                             "rare_values": info["rare_value"],
                             "trigger_signal": info["trigger_signal"],
                             "fire_signal": info["fire_signal"],
                             "payload": info["payload"],
                             "payload_tap": info["payload_tap"],
                             "counter_qs": info["counter_qs"]})
        report["records"].append({"run_id": run["run_id"], "host": run["host"],
                                  "status": "regenerated_care_bits_not_independent_validation",
                                  "variants": variants})
        save_json(EVIDENCE, report)
        print(run["run_id"], len(variants), "hash-matched", flush=True)


if __name__ == "__main__":
    main()
