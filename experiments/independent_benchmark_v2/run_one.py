"""Run one pinned DATE insertion and capture activation care bits in-process."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
VENDOR = ROOT / "runs/third_party/date2025_vendor"
OUT = ROOT / "runs/independent_benchmark_v2"
sys.path.insert(0, str(VENDOR))
from ht_framework import pipeline  # noqa: E402


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("PYTHONHASHSEED=0 must be set before Python starts")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--mechanism", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--repeat", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    settings = protocol["generator_settings"]
    if args.host not in protocol["host_split"]["development"]:
        raise ValueError("Sealed host cannot be generated")
    if args.mechanism not in settings["mechanisms"] or args.seed not in settings["seeds"]:
        raise ValueError("Run is outside the frozen settings")
    source = sorted((VENDOR / "netlists").glob(args.host + "*.v"))
    if len(source) != 1:
        raise ValueError("Missing or ambiguous source")
    run_id = f"{args.host}_{args.mechanism}_s{args.seed}"
    outdir = OUT / ("repeat" if args.repeat else "runs") / run_id
    if (outdir / "summary.json").exists():
        raise ValueError("Output already exists; never overwrite a generated run")
    captured = []
    original = pipeline.ti.insert_trojan

    def intercept(*call_args, **call_kwargs):
        info = original(*call_args, **call_kwargs)
        captured.append(info)
        return info

    pipeline.ti.insert_trojan = intercept
    cwd = Path.cwd()
    try:
        os.chdir(VENDOR)
        summary = pipeline.run(
            netlist_path=source[0].relative_to(VENDOR).as_posix(), outdir=str(outdir),
            q=settings["trigger_nodes"], num_instances=settings["instances_per_host_mechanism"],
            theta_fraction=0.2, num_vectors=settings["vectors"],
            trojan_type=args.mechanism, counter_width=settings["counter_width"],
            detection_patterns=settings["detect"], run_detection=settings["detect"] > 0,
            max_rare_nodes=settings["max_rare"], validate_each=True,
            visualize=False, seed=args.seed, verbose=False)
    finally:
        pipeline.ti.insert_trojan = original
        os.chdir(cwd)
    if len(captured) != settings["instances_per_host_mechanism"] or len(summary["instances"]) != len(captured):
        raise ValueError("Wrong number of generated instances")
    records = []
    for info, item in zip(captured, summary["instances"]):
        path = Path(info["output_file"])
        if not path.is_file() or not path.resolve().is_relative_to(outdir.resolve()):
            raise ValueError("Generated file escaped output directory")
        records.append({"index": item["index"], "source_sha256": sha256(path),
                        "source_path": path.relative_to(outdir).as_posix(),
                        "merged_care_bits": info["merged_tv"],
                        "rare_values": info["rare_value"],
                        "trigger_signal": info["trigger_signal"],
                        "fire_signal": info["fire_signal"],
                        "payload": info["payload"], "payload_tap": info["payload_tap"],
                        "counter_qs": info["counter_qs"],
                        "upstream_verify": item["verify"]})
    (outdir / "activation_vectors.json").write_text(json.dumps({
        "status": "upstream_care_bits_and_self_validation_only",
        "run_id": run_id, "pythonhashseed": "0", "source_sha256": sha256(source[0]),
        "records": records}, indent=2) + "\n", encoding="utf-8")
    print(run_id, len(records), "generated", flush=True)


if __name__ == "__main__":
    main()
