"""Build separate source-traced gate graphs and construction-derived label candidates.

Only generated development hosts are processed. Labels are based on source
instance diff and Yosys source spans; any ambiguous or missing mapping is -1.
The graph/label files are preliminary and must not be treated as reviewed truth.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "runs/independent_benchmark_v1"
EVIDENCE = ROOT / "data/independent_benchmark_v1"
VERSION = "independent_v1"
YOSYS = ROOT / "trusthub/venv/Scripts/yowasp-yosys.exe"
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
from build import graph_from_json, sha256  # noqa: E402

CELL = re.compile(r"^\s*(and|or|nand|nor|not|xor|xnor|buf|sdff|sdffr)\s+(\S+)\s*\(", re.I)


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def source_instances(path):
    result = {}
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        match = CELL.match(line)
        if not match:
            continue
        name = match.group(2)
        if name in result:
            raise ValueError(f"Duplicate instance name: {path}/{name}")
        result[name] = {"line": number, "text": re.sub(r"\s+", "", line),
                        "type": match.group(1).lower()}
    return result


def source_top(path):
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\(",
                      path.read_text(encoding="utf-8", errors="replace"))
    if not match:
        raise ValueError(f"No top module declaration: {path}")
    return match.group(1)


def source_diff(clean, infected):
    a, b = source_instances(clean), source_instances(infected)
    added = {name: b[name] for name in b.keys() - a.keys()}
    removed = {name: a[name] for name in a.keys() - b.keys()}
    changed = {name: b[name] for name in a.keys() & b.keys()
               if a[name]["text"] != b[name]["text"]}
    return {"added": added, "removed": removed, "changed": changed,
            "clean_instance_count": len(a), "infected_instance_count": len(b)}


def synthesize(source, top, target, sequential):
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "yosys.json"
    if json_path.exists():
        return json_path
    commands = []
    if sequential:
        commands.append(f"read_verilog -lib {(HERE / 'scan_ff_stub.v').relative_to(ROOT).as_posix()}")
    commands.extend([f"read_verilog {source.relative_to(ROOT).as_posix()}",
                     f"hierarchy -check -top {top}", "proc", "opt", "flatten", "opt",
                     "techmap", "opt", f"write_json {json_path.relative_to(ROOT).as_posix()}"])
    process = subprocess.run([str(YOSYS), "-Q", "-T", "-q", "-p", "; ".join(commands)],
                             cwd=ROOT, capture_output=True, text=True, timeout=600)
    (target / "yosys.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    if process.returncode or not json_path.exists():
        raise RuntimeError(f"Yosys failed: {source}; see {target / 'yosys.log'}")
    return json_path


def graph_one(source, top, target, graph_id, label, sequential):
    json_path = synthesize(source, top, target, sequential)
    document = json.loads(json_path.read_text(encoding="utf-8"))
    counts = {source.name: len(source.read_text(encoding="utf-8", errors="replace").splitlines())}
    data, metadata = graph_from_json(document, top, graph_id, label, counts)
    metadata.update({"source": source.relative_to(ROOT).as_posix(), "source_sha256": sha256(source),
                     "yosys_json_sha256": sha256(json_path),
                     "scan_ff_port_stub_only": sequential,
                     "status": "construction_derived_unreviewed"})
    torch.save(data, target / "graph.pt")
    save_json(target / "metadata.json", metadata)
    ports = {name: (port["direction"], len(port["bits"]))
             for name, port in document["modules"][top]["ports"].items()}
    return metadata, ports


def labels_for(metadata, diff, source_name):
    added_lines = {row["line"] for row in diff["added"].values()}
    changed_lines = {row["line"] for row in diff["changed"].values()}
    labels = []
    for spans in metadata["source_ranges"]:
        relevant = {number for name, start, end in spans if name == source_name
                    for number in range(start, end + 1)}
        if not relevant or relevant & changed_lines:
            labels.append(-1)
        elif relevant <= added_lines:
            labels.append(1)
        elif relevant & added_lines:
            labels.append(-1)
        else:
            labels.append(0)
    return labels


def build(run, variant):
    run_dir = OUT / run["run_id"]
    host = run["host"]
    clean = run_dir / f"{Path(run['command'][1]).stem}_conv.v"
    top = source_top(clean)
    infected = OUT / variant["file"]
    if sha256(infected) != variant["sha256"]:
        raise ValueError("Generated source hash changed")
    sequential = run["mechanism"] == "sequential" or host.startswith("s")
    clean_target = run_dir / "graphs" / "clean"
    infected_target = run_dir / "graphs" / infected.stem
    clean_meta, clean_ports = graph_one(clean, top, clean_target,
                                        f"{VERSION}/{run['run_id']}/clean", 0, sequential)
    infected_meta, infected_ports = graph_one(infected, top, infected_target,
                                             f"{VERSION}/{run['run_id']}/{infected.stem}",
                                             1, sequential)
    if clean_ports != infected_ports:
        raise ValueError("Clean/infected top interfaces differ")
    diff = source_diff(clean, infected)
    labels = labels_for(infected_meta, diff, infected.name)
    if len(labels) != infected_meta["num_nodes"]:
        raise ValueError("Node/label row count mismatch")
    digest = hashlib.sha256(json.dumps(labels, separators=(",", ":")).encode()).hexdigest()
    node_labels = {"status": "construction_derived_unreviewed",
                   "graph_id": infected_meta["graph_id"],
                   "graph_sha256": sha256(infected_target / "graph.pt"),
                   "node_names_sha256": infected_meta["node_names_sha256"],
                   "ordered_labels_sha256": digest, "labels": labels,
                   "source_diff": diff,
                   "limitations": ["Source instance diff, not independently reviewed ground truth",
                                   "Cells with missing or ambiguous source spans marked -1",
                                   "Sequential scan FF stub has port directions only"]}
    save_json(infected_target / "node_labels.json", node_labels)
    return {"run_id": run["run_id"], "variant": variant["file"],
            "clean_graph_sha256": sha256(clean_target / "graph.pt"),
            "infected_graph_sha256": sha256(infected_target / "graph.pt"),
            "node_labels_sha256": sha256(infected_target / "node_labels.json"),
            "clean_nodes": clean_meta["num_nodes"], "infected_nodes": infected_meta["num_nodes"],
            "added_source_instances": len(diff["added"]),
            "removed_source_instances": len(diff["removed"]),
            "changed_source_instances": len(diff["changed"]),
            "positive": labels.count(1), "negative": labels.count(0), "unknown": labels.count(-1),
            "top_port_count": len(clean_ports), "scan_ff_port_stub_only": sequential}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append")
    args = parser.parse_args()
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    allowed = set(protocol["host_split"]["development"])
    prior_path = EVIDENCE / "graph_lineage.json"
    report = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.exists() else {"records": []}
    for run in manifest["records"]:
        if run["host"] not in allowed or (args.host and run["host"] not in args.host):
            continue
        if run["status"] != "upstream_self_validated":
            raise ValueError("Upstream run failed")
        for variant in run["variants"]:
            if any(r["variant"] == variant["file"] for r in report["records"]):
                print("skip", variant["file"], flush=True)
                continue
            print("graph", variant["file"], flush=True)
            row = build(run, variant)
            report["records"].append(row)
            report["status"] = "construction_derived_candidate_labels_not_reviewed"
            save_json(prior_path, report)
            print(row["positive"], row["negative"], row["unknown"], flush=True)


if __name__ == "__main__":
    main()
