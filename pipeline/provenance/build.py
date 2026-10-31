"""Build source-traced gate graphs from one versioned Yosys JSON export.

Example (from repository root):
  python pipeline/provenance/build.py --benchmark RS232-T2100

The output is a NEW graph version. Its row metadata belongs only to the .pt
written beside it; do not attach it to the supplied 2026-10-31 archive.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import deque
from pathlib import Path

import torch
from torch_geometric.data import Data

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "trusthub" / "scripts"))
sys.path.insert(0, str(ROOT / "pipeline" / "localization"))
from feature_extractor import classify_gate_type  # noqa: E402
from label_nodes import overlaps, src_ranges  # noqa: E402
from rtl_diff import trojan_lines  # noqa: E402

GATE_CLASSES = json.loads((ROOT / "trusthub" / "features" / "gate_vocab.json").read_text(encoding="utf-8"))["gate_classes"]
CELL_EXCLUDE = {"$scopeinfo", "$print", "$display"}
FLOW = "read_verilog; hierarchy; proc; opt; flatten; opt; techmap; opt; write_json (no ABC)"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files(benchmark, side):
    family = benchmark.split("-")[0]
    if family == "RS232":
        tag = "tjfree" if side == "clean" else "tjin"
        folder = ROOT / "trusthub" / "netlists" / "RS232" / benchmark / f"{tag}_patched_src"
        top = "uart"
    elif family == "AES":
        folder = ROOT / "trusthub" / "AES_unzipped" / benchmark / benchmark / "src" / ("TjFree" if side == "clean" else "TjIn")
        top = "aes_128"
    elif family == "memctrl":
        folder = ROOT / "runs" / "expansion" / benchmark / side
        top = "mc_top"
    elif family == "PIC16F84":
        folder = ROOT / "runs" / "expansion" / benchmark / side
        top = "pic_16f84_core"
    else:
        raise ValueError(f"No reviewed source layout for {family}")
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    files = sorted(p for p in folder.glob("*.v") if not p.name.lower().startswith(("test", "tb")) and not p.name.lower().endswith("_tb.v"))
    if not files:
        raise ValueError(f"No synthesizable Verilog in {folder}")
    if family == "AES" and side == "trojan" and any(re.search(r"\bmodule\s+top\b", p.read_text(errors="replace")) for p in files):
        top = "top"
    return files, top


def yosys_script(files, top, output, include_dir=None):
    # Repository-relative forward slashes work for native and YoWASP Yosys.
    relative = [p.relative_to(ROOT).as_posix() for p in files]
    include_flag = f"-I{include_dir.relative_to(ROOT).as_posix()} " if include_dir else ""
    commands = ["read_verilog " + include_flag + " ".join(relative), f"hierarchy -top {top}", "proc", "opt", "flatten", "opt", "techmap", "opt", f"write_json {output.relative_to(ROOT).as_posix()}"]
    return "; ".join(commands)


def distances(adjacency, starts):
    result = [-1] * len(adjacency)
    queue = deque(starts)
    for index in starts:
        result[index] = 0
    while queue:
        source = queue.popleft()
        for target in adjacency[source]:
            if result[target] == -1:
                result[target] = result[source] + 1
                queue.append(target)
    return result


def graph_from_json(document, top, graph_id, label, source_line_counts=None):
    module = document["modules"][top]
    cells = {name: cell for name, cell in module["cells"].items() if cell["type"].lower() not in CELL_EXCLUDE}
    names = sorted(cells)
    if not names:
        raise ValueError("No gates after synthesis")
    index = {name: i for i, name in enumerate(names)}
    drivers = {}
    for name in names:
        cell = cells[name]
        for port, direction in cell["port_directions"].items():
            if direction == "output":
                for bit in cell["connections"][port]:
                    if isinstance(bit, int):
                        if bit in drivers and drivers[bit] != name:
                            raise ValueError(f"Multiple gate drivers for bit {bit}")
                        drivers[bit] = name
    edges = set()
    for name in names:
        cell = cells[name]
        for port, direction in cell["port_directions"].items():
            if direction == "input":
                for bit in cell["connections"][port]:
                    upstream = drivers.get(bit) if isinstance(bit, int) else None
                    if upstream is not None and upstream != name:
                        edges.add((index[upstream], index[name]))
    edges = sorted(edges)
    successors, predecessors = [[] for _ in names], [[] for _ in names]
    for src, dst in edges:
        successors[src].append(dst)
        predecessors[dst].append(src)
    ctrl = distances(successors, [i for i, pred in enumerate(predecessors) if not pred])
    obs = distances(predecessors, [i for i, succ in enumerate(successors) if not succ])
    sentinel = max([*ctrl, *obs, 0]) + 1
    class_index = {name: i for i, name in enumerate(GATE_CLASSES)}
    features, types, classes, source_ranges, raw_sources = [], [], [], [], []
    for i, name in enumerate(names):
        cell = cells[name]
        gate_class = classify_gate_type(cell["type"])
        onehot = [0.0] * (len(GATE_CLASSES) + 1)
        onehot[class_index.get(gate_class, len(GATE_CLASSES))] = 1.0
        features.append(onehot + [float(len(predecessors[i])), float(len(successors[i])),
                                  float(ctrl[i] if ctrl[i] >= 0 else sentinel),
                                  float(obs[i] if obs[i] >= 0 else sentinel)])
        types.append(cell["type"])
        classes.append(gate_class)
        raw = cell.get("attributes", {}).get("src", "")
        raw_sources.append(raw)
        ranges = src_ranges(raw)
        if source_line_counts is not None:
            ranges = [span for span in ranges if span[0] in source_line_counts and
                      1 <= span[1] <= span[2] <= source_line_counts[span[0]]]
        source_ranges.append(ranges)
    data = Data(x=torch.tensor(features, dtype=torch.float32),
                edge_index=torch.tensor(edges, dtype=torch.long).T.contiguous() if edges else torch.empty((2, 0), dtype=torch.long),
                y=torch.tensor([label], dtype=torch.long))
    data.graph_id = graph_id
    name_checksum = hashlib.sha256(json.dumps(names, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    metadata = {"graph_id": graph_id, "label": label, "num_nodes": len(names), "num_edges": len(edges),
                "node_names": names, "node_names_sha256": name_checksum, "node_types": types,
                "node_gate_classes": classes, "node_src": raw_sources, "source_ranges": source_ranges,
                "source_covered_nodes": sum(bool(r) for r in source_ranges),
                "raw_src_nodes": sum(bool(s) for s in raw_sources), "reviewed": False}
    return data, metadata


def build_one(benchmark, side, out_root, yosys):
    files, top = source_files(benchmark, side)
    target = out_root / benchmark / side
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "yosys.json"
    script = yosys_script(files, top, json_path, files[0].parent if benchmark.startswith("memctrl-") else None)
    completed = subprocess.run([str(yosys), "-Q", "-T", "-q", "-p", script], cwd=ROOT, text=True,
                               capture_output=True)
    (target / "yosys.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode or not json_path.is_file():
        raise RuntimeError(f"Yosys failed for {benchmark}/{side}; see {target / 'yosys.log'}")
    document = json.loads(json_path.read_text(encoding="utf-8"))
    graph_id = f"provenance_v1/{benchmark}/{side}"
    source_line_counts = {p.name: len(p.read_text(encoding="utf-8", errors="replace").splitlines()) for p in files}
    if len(source_line_counts) != len(files):
        raise ValueError(f"Duplicate source basenames for {benchmark}/{side}")
    data, metadata = graph_from_json(document, top, graph_id, int(side == "trojan"), source_line_counts)
    metadata.update({"benchmark": benchmark, "side": side, "top": top, "synthesis_flow": FLOW,
                     "yosys_script": script, "yosys_json_sha256": sha256(json_path),
                     "sources": {p.relative_to(ROOT).as_posix(): sha256(p) for p in files}})
    torch.save(data, target / "graph.pt")
    (target / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    references = json.loads((ROOT / "data" / "localization_reference" / "manifest.json").read_text(encoding="utf-8"))
    reference = next((row for row in references if row["benchmark"] == benchmark), None)
    if reference is not None or benchmark.split("-")[0] in ("memctrl", "PIC16F84"):
        if reference is not None:
            changed = reference["changed_lines"] if side == "trojan" else {}
        else:
            clean_files, _ = source_files(benchmark, "clean")
            trojan_files, _ = source_files(benchmark, "trojan")
            changed, _ = trojan_lines(clean_files[0].parent, trojan_files[0].parent)
            if side == "clean":
                changed = {}
        candidates = [int(overlaps(ranges, changed)) if ranges else -1 for ranges in metadata["source_ranges"]]
        candidate_record = {"graph_id": graph_id, "node_names": metadata["node_names"],
                            "node_names_sha256": metadata["node_names_sha256"], "labels": candidates,
                            "source_ranges": metadata["source_ranges"], "reviewed": False,
                            "source": "Yosys cell src intersected with unreviewed RTL diff; candidate only",
                            "coverage": {"known": sum(v >= 0 for v in candidates),
                                         "candidate_trojan": sum(v == 1 for v in candidates),
                                         "unknown": sum(v == -1 for v in candidates)}}
        (target / "candidate_labels.json").write_text(json.dumps(candidate_record, indent=2), encoding="utf-8")
    return {"benchmark": benchmark, "side": side, "nodes": data.num_nodes, "edges": data.num_edges,
            "source_covered_nodes": metadata["source_covered_nodes"], "path": str(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--benchmark", action="append", help="Repeat for multiple paired benchmarks")
    selection.add_argument("--all-paired", action="store_true", help="Build every benchmark in the 21-pair manifest")
    parser.add_argument("--side", choices=["clean", "trojan", "both"], default="both")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "provenance_v1")
    parser.add_argument("--yosys", type=Path, default=ROOT / "trusthub" / "venv" / "Scripts" / "yowasp-yosys.exe")
    args = parser.parse_args()
    if not args.yosys.is_file():
        parser.error(f"Yosys not found: {args.yosys}")
    out_root = args.out.resolve()
    if not out_root.is_relative_to(ROOT):
        parser.error("Output must stay inside the repository so Yosys can write to it")
    references = json.loads((ROOT / "data" / "localization_reference" / "manifest.json").read_text(encoding="utf-8"))
    benchmarks = [row["benchmark"] for row in references] if args.all_paired else args.benchmark
    results = []
    for benchmark in benchmarks:
        for side in (("clean", "trojan") if args.side == "both" else (args.side,)):
            result = build_one(benchmark, side, out_root, args.yosys)
            results.append(result)
            print(json.dumps(result), flush=True)
    (out_root / "build_summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
