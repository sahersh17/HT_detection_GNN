"""Parse the B15 and s38584 gate netlists with explicit cell-port stubs.

These archives already contain mapped gate netlists, so re-synthesizing their
logic would change the benchmark. Yosys parses the original instances and
connectivity; the generated stubs provide *port directions only*. Their source
spans refer to gate-netlist lines, never to original RTL.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

from build import ROOT, graph_from_json, sha256

SOURCE = ROOT / "runs" / "new_trusthub"
DEFAULT_OUT = ROOT / "runs" / "new_gate_v1"
INSTANCE = re.compile(r"(?ms)^\s*([A-Za-z_][\w$]*)\s+([A-Za-z_][\w$]*)\s*\((.*?)\)\s*;")
PORT = re.compile(r"\.([A-Za-z_][\w$]*)\s*\(")
MODULE = re.compile(r"(?m)^\s*module\s+([A-Za-z_][\w$]*)\b")
OUTPUT_PORTS = {"Q", "QN", "CO", "SUM", "DIFF", "SO", "C1"}


def source_path(benchmark, side):
    folder = SOURCE / benchmark / side
    files = sorted(folder.glob("*.v"))
    if len(files) != 1:
        raise ValueError(f"Expected exactly one mapped gate netlist: {folder}")
    return files[0]


def cell_ports(text):
    defined = set(MODULE.findall(text))
    cells = {}
    for raw_type, _, body in INSTANCE.findall(text):
        if raw_type in defined or raw_type == "module":
            continue
        ports = set(PORT.findall(body))
        if not ports:
            raise ValueError(f"No named ports on {raw_type}")
        # Named-port instances may leave unused outputs disconnected.
        cells.setdefault(raw_type, set()).update(ports)
    if not cells:
        raise ValueError("No mapped library cells found")
    return cells


def stubs_for(benchmark):
    all_cells = {}
    for side in ("clean", "trojan"):
        for name, ports in cell_ports(source_path(benchmark, side).read_text(encoding="utf-8", errors="replace")).items():
            all_cells.setdefault(name, set()).update(ports)
    lines = []
    for name, ports in sorted(all_cells.items()):
        outputs = sorted(ports & OUTPUT_PORTS)
        inputs = sorted(ports - OUTPUT_PORTS)
        if not outputs or not inputs:
            raise ValueError(f"Unclassified cell ports: {name}: {sorted(ports)}")
        # S is a MUX select but an adder output; require an explicit exception.
        if name.startswith("MUX") and "S" in ports:
            inputs = sorted(set(inputs) | {"S"})
            outputs = sorted(set(outputs) - {"S"})
        elif name.startswith("FADD") and "S" in ports:
            inputs = sorted(set(inputs) - {"S"})
            outputs = sorted(set(outputs) | {"S"})
        if not outputs or not inputs:
            raise ValueError(f"Invalid cell interface after exceptions: {name}")
        declarations = [f"input {p}" for p in inputs] + [f"output {p}" for p in outputs]
        lines.append(f"(* blackbox *) module {name}({', '.join(declarations)}); endmodule")
    return "\n".join(lines) + "\n", all_cells


def synth_one(benchmark, side, out_root, yosys):
    family = benchmark.split("-")[0]
    if family not in ("b15", "s38584", "s15850", "s35932", "s38417"):
        raise ValueError(f"Unsupported mapped-netlist family: {family}")
    source = source_path(benchmark, side)
    target = out_root / benchmark / side
    target.mkdir(parents=True, exist_ok=True)
    stubs, cells = stubs_for(benchmark)
    stub_path = target / "cell_stubs.v"
    stub_path.write_text(stubs, encoding="utf-8")
    json_path = target / "yosys.json"
    top = family
    script = (f"read_verilog -lib {stub_path.relative_to(ROOT).as_posix()}; "
              f"read_verilog {source.relative_to(ROOT).as_posix()}; "
              f"hierarchy -check -top {top}; flatten; "
              f"write_json {json_path.relative_to(ROOT).as_posix()}")
    completed = subprocess.run([str(yosys), "-Q", "-T", "-q", "-p", script], cwd=ROOT,
                               capture_output=True, text=True)
    (target / "yosys.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode or not json_path.is_file():
        raise RuntimeError(f"Mapped netlist parse failed: {benchmark}/{side}; see {target / 'yosys.log'}")
    document = json.loads(json_path.read_text(encoding="utf-8"))
    graph_id = f"new_gate_v1/{benchmark}/{side}"
    line_counts = {source.name: len(source.read_text(encoding="utf-8", errors="replace").splitlines())}
    data, metadata = graph_from_json(document, top, graph_id, int(side == "trojan"), line_counts)
    metadata.update({"benchmark": benchmark, "side": side, "top": top,
                     "synthesis_flow": "mapped netlist parse; blackbox cell port stubs; flatten; write_json",
                     "source_level": "gate_netlist_lines_not_RTL", "reviewed": False,
                     "yosys_script": script, "yosys_json_sha256": sha256(json_path),
                     "cell_stubs_sha256": sha256(stub_path), "cell_types": len(cells),
                     "sources": {source.relative_to(ROOT).as_posix(): sha256(source)}})
    import torch
    torch.save(data, target / "graph.pt")
    (target / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"graph_id": graph_id, "nodes": data.num_nodes, "edges": data.num_edges,
            "source_covered_nodes": metadata["source_covered_nodes"], "cell_types": len(cells)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True, choices=("b15", "s38584", "s15850", "s35932", "s38417"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--yosys", type=Path, default=ROOT / "trusthub" / "venv" / "Scripts" / "yowasp-yosys.exe")
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT):
        parser.error("Output must be inside repository")
    rows = []
    for folder in sorted(SOURCE.glob(f"{args.family}-T*")):
        if folder.is_dir():
            for side in ("clean", "trojan"):
                row = synth_one(folder.name, side, out, args.yosys)
                rows.append(row)
                print(json.dumps(row), flush=True)
    if not rows:
        parser.error(f"No extracted {args.family} benchmarks")
    (out / f"{args.family}_build_summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
