"""Generate the v2 development pilot in hash-seeded child processes."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "runs/independent_benchmark_v2"
EVIDENCE = ROOT / "data/independent_benchmark_v2"
sys.path.insert(0, str(ROOT / "experiments/independent_benchmark_v1"))
from intake import verify_upstream  # noqa: E402


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run_child(host, mechanism, seed, repeat=False):
    command = [sys.executable, str(HERE / "run_one.py"), "--host", host,
               "--mechanism", mechanism, "--seed", str(seed)]
    if repeat:
        command.append("--repeat")
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                             text=True, timeout=1800)
    if process.returncode:
        raise RuntimeError(f"Generation failed: {host}/{mechanism}: {(process.stdout + process.stderr)[-1500:]}")
    return process.stdout.strip()


def collect(host, mechanism, seed, repeat=False):
    run_id = f"{host}_{mechanism}_s{seed}"
    folder = OUT / ("repeat" if repeat else "runs") / run_id
    summary_path, vector_path = folder / "summary.json", folder / "activation_vectors.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    vectors = json.loads(vector_path.read_text(encoding="utf-8"))
    if len(summary["instances"]) != len(vectors["records"]):
        raise ValueError("Summary/vector count mismatch")
    records = []
    for info, item in zip(vectors["records"], summary["instances"]):
        source = folder / info["source_path"]
        if sha256(source) != info["source_sha256"] or not item["verify"].get("trigger_fired") or not item["verify"].get("payload_corrupted"):
            raise ValueError("Generated source or upstream validation failed")
        records.append({"index": info["index"], "source_sha256": info["source_sha256"],
                        "source_path": info["source_path"]})
    return {"run_id": run_id, "host": host, "mechanism": mechanism, "seed": seed,
            "folder": folder.relative_to(ROOT).as_posix(),
            "summary_sha256": sha256(summary_path),
            "activation_vectors_sha256": sha256(vector_path),
            "converted_clean_sha256": sha256(folder / (Path(summary["netlist"]).stem + "_conv.v")),
            "records": records, "status": "upstream_self_validated_only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append")
    parser.add_argument("--repeat-check", action="store_true",
                        help="Regenerate the selected runs in a separate folder and compare source hashes")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    tree = json.loads((ROOT / protocol["upstream_tree"]).read_text(encoding="utf-8"))
    verify_upstream(tree)
    settings = protocol["generator_settings"]
    selected = args.host or protocol["host_split"]["development"]
    if not set(selected) <= set(protocol["host_split"]["development"]):
        raise ValueError("Cannot run sealed hosts")
    path = EVIDENCE / "manifest.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "status": "v2_development_upstream_self_validation_only",
        "protocol_sha256": sha256(HERE / "protocol.json"),
        "upstream_tree_sha256": sha256(ROOT / protocol["upstream_tree"]),
        "records": []}
    if report["protocol_sha256"] != sha256(HERE / "protocol.json"):
        raise ValueError("Protocol changed after runs began")
    for host in selected:
        for mechanism in settings["mechanisms"]:
            for seed in settings["seeds"]:
                run_id = f"{host}_{mechanism}_s{seed}"
                existing = next((row for row in report["records"] if row["run_id"] == run_id), None)
                if not existing:
                    print("generate", run_id, flush=True)
                    print(run_child(host, mechanism, seed), flush=True)
                    existing = collect(host, mechanism, seed)
                    report["records"].append(existing)
                    save_json(path, report)
                if args.repeat_check and not existing.get("deterministic_repeat_match"):
                    print("repeat", run_id, flush=True)
                    print(run_child(host, mechanism, seed, repeat=True), flush=True)
                    repeated = collect(host, mechanism, seed, repeat=True)
                    same = (existing["converted_clean_sha256"] == repeated["converted_clean_sha256"] and
                            [r["source_sha256"] for r in existing["records"]] ==
                            [r["source_sha256"] for r in repeated["records"]])
                    existing["deterministic_repeat_match"] = same
                    save_json(path, report)
                    if not same:
                        raise RuntimeError(f"Pinned hash seed did not make {run_id} deterministic")
                    print("deterministic", run_id, flush=True)
    print("recorded", len(report["records"]), "development runs", flush=True)


if __name__ == "__main__":
    main()
