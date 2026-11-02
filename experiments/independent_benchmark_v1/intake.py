"""Hash-check and run the pinned DATE 2025 generator on development hosts only.

This is an intake stage, not a validated benchmark or a model-training command.
The upstream framework's own activation check is recorded separately from
independent equivalence, divergence, decoy and lineage gates.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
VENDOR = ROOT / "runs/third_party/date2025_vendor"
OUT = ROOT / "runs/independent_benchmark_v1"
EVIDENCE = ROOT / "data/independent_benchmark_v1"
SOURCE_TREE = HERE / "upstream_tree.json"
PROTOCOL = HERE / "protocol.json"
MAX_RUN_SECONDS = 1800


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path):
    content = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def normalized_verilog_sha256(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
    text = re.sub(r"\s+", "", text)
    return hashlib.sha256(text.encode()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def load_frozen():
    tree = json.loads(SOURCE_TREE.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if tree["commit"] != protocol["generator"]["commit"]:
        raise ValueError("Upstream commit mismatch")
    if set(protocol["host_split"]["development"]) & set(protocol["host_split"]["sealed_final_candidate"]):
        raise ValueError("Development/final host overlap")
    return tree, protocol


def verify_upstream(tree):
    records = []
    for row in tree["files"]:
        path = VENDOR / row["path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = git_blob_sha1(path)
        if path.stat().st_size != row["bytes"] or actual != row["git_blob_sha1"]:
            raise ValueError(f"Pinned upstream blob changed: {row['path']}")
        records.append({"path": row["path"], "sha256": sha256(path),
                        "git_blob_sha1": actual, "bytes": row["bytes"]})
    return records


def check_local_duplicates(hosts):
    # Single-file exact/whitespace-comment checks. This does not prove semantic
    # independence; a different circuit with the same behavior can evade it.
    local = {}
    for path in (ROOT / "trusthub").rglob("*.v"):
        if not path.is_file():
            continue
        key = (sha256(path), normalized_verilog_sha256(path))
        local.setdefault(key[0], []).append(path.relative_to(ROOT).as_posix())
        local.setdefault(key[1], []).append(path.relative_to(ROOT).as_posix())
    result = []
    for host in hosts:
        candidates = sorted((VENDOR / "netlists").glob(host + "*.v"))
        if len(candidates) != 1:
            raise ValueError(f"Expected exactly one upstream source for {host}: {candidates}")
        path = candidates[0]
        exact = local.get(sha256(path), [])
        normalized = local.get(normalized_verilog_sha256(path), [])
        result.append({"host": host, "source": path.relative_to(VENDOR).as_posix(),
                       "source_sha256": sha256(path),
                       "normalized_sha256": normalized_verilog_sha256(path),
                       "exact_local_matches": exact,
                       "comment_whitespace_normalized_matches": normalized})
    return result


def source_audit():
    tree, protocol = load_frozen()
    files = verify_upstream(tree)
    hosts = protocol["host_split"]["development"] + protocol["host_split"]["sealed_final_candidate"]
    dedup = check_local_duplicates(hosts)
    report = {"status": "source_intake_only", "upstream_commit": tree["commit"],
              "protocol_sha256": sha256(PROTOCOL), "upstream_tree_sha256": sha256(SOURCE_TREE),
              "verified_files": files, "host_dedup": dedup,
              "sealed_final_candidate": protocol["host_split"]["sealed_final_candidate"],
              "limitations": ["Only exact and whitespace/comment-normalized source duplicates checked",
                              "No final host generated or synthesized",
                              "No semantic benchmark gate passed"]}
    save_json(EVIDENCE / "source_audit.json", report)
    if any(row["exact_local_matches"] or row["comment_whitespace_normalized_matches"] for row in dedup):
        raise ValueError("A candidate host duplicates an existing local source")
    print(f"Verified {len(files)} pinned upstream files and {len(dedup)} candidate host source hashes")
    return protocol


def run_pilot(protocol, selected):
    settings = protocol["generator"]["pilot_parameters"]
    dev = protocol["host_split"]["development"]
    if selected and not set(selected) <= set(dev):
        raise ValueError("Only development hosts may be generated")
    manifest_path = OUT / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["protocol_sha256"] != sha256(PROTOCOL):
            raise ValueError("Existing output belongs to another protocol")
    else:
        manifest = {"status": "upstream_self_validation_only", "protocol_sha256": sha256(PROTOCOL),
                    "upstream_tree_sha256": sha256(SOURCE_TREE), "records": []}
    for host in selected or dev:
        candidates = list((VENDOR / "netlists").glob(host + "*.v"))
        if len(candidates) != 1:
            raise ValueError(f"Missing source: {host}")
        source = candidates[0]
        for mechanism in settings["mechanisms"]:
            for seed in settings["seeds"]:
                run_id = f"{host}_{mechanism}_s{seed}"
                prior = next((r for r in manifest["records"] if r["run_id"] == run_id), None)
                if prior:
                    if prior["status"] != "upstream_self_validated":
                        raise ValueError(f"Existing failed run needs separate investigation: {run_id}")
                    print("skip", run_id, flush=True)
                    continue
                outdir = OUT / run_id
                command = [sys.executable, "main.py", source.relative_to(VENDOR).as_posix(),
                           "-o", str(outdir), "-q", str(settings["trigger_nodes"]),
                           "-n", str(settings["instances_per_host_mechanism"]),
                           "--vectors", str(settings["vectors"]),
                           "--max-rare", str(settings["max_rare"]),
                           "--detect", str(settings["detect"]),
                           "--trojan-type", mechanism, "--counter-width", str(settings["counter_width"]),
                           "--seed", str(seed), "--no-visualize"]
                print("run", run_id, flush=True)
                try:
                    process = subprocess.run(command, cwd=VENDOR, capture_output=True,
                                             text=True, timeout=MAX_RUN_SECONDS)
                    log = (process.stdout + "\n" + process.stderr)[-10000:]
                    code = process.returncode
                except subprocess.TimeoutExpired as error:
                    log = (error.stdout or b"").decode(errors="replace") if isinstance(error.stdout, bytes) else str(error.stdout or "")
                    code = None
                outdir.mkdir(parents=True, exist_ok=True)
                (outdir / "intake.log").write_text(log, encoding="utf-8")
                summary_path = outdir / "summary.json"
                row = {"run_id": run_id, "host": host, "mechanism": mechanism,
                       "seed": seed, "source_sha256": sha256(source),
                       "command": command[1:], "exit_code": code,
                       "log_sha256": sha256(outdir / "intake.log")}
                if code == 0 and summary_path.is_file():
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                    instances = summary.get("instances", [])
                    valid = (len(instances) == settings["instances_per_host_mechanism"] and
                             all(r.get("verify", {}).get("trigger_fired") and
                                 r.get("verify", {}).get("payload_corrupted") for r in instances))
                    row["summary_sha256"] = sha256(summary_path)
                    row["variants"] = []
                    for item in instances:
                        path = Path(item["file"])
                        if not path.is_file() or not path.resolve().is_relative_to(outdir.resolve()):
                            raise ValueError(f"Invalid generated file: {path}")
                        row["variants"].append({"file": path.relative_to(OUT).as_posix(),
                                                "sha256": sha256(path),
                                                "trigger_nodes": item.get("trigger_nodes", []),
                                                "payload": item.get("payload"),
                                                "trigger_signal": item.get("trigger_signal")})
                    row["status"] = "upstream_self_validated" if valid else "upstream_validation_failed"
                else:
                    row["status"] = "run_failed"
                manifest["records"].append(row)
                save_json(manifest_path, manifest)
                print(run_id, row["status"], flush=True)
                if row["status"] != "upstream_self_validated":
                    raise RuntimeError(f"Pilot run failed: {run_id}; see {outdir / 'intake.log'}")
    save_json(EVIDENCE / "pilot_manifest.json", manifest)
    print(f"Recorded {len(manifest['records'])} development runs; independent benchmark gates remain pending")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-pilot", action="store_true")
    parser.add_argument("--host", action="append", help="Development host to run; repeat as needed")
    args = parser.parse_args()
    protocol = source_audit()
    if args.run_pilot:
        run_pilot(protocol, args.host)


if __name__ == "__main__":
    main()
