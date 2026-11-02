"""Parse Trojan-only RS232 technology netlists as a separate graph version."""
import json
import subprocess
from pathlib import Path
import torch

from build import ROOT, graph_from_json, sha256
from synth_gate_netlists import cell_ports, OUTPUT_PORTS

SOURCE = ROOT / "runs/new_trusthub/rs232_gate"
OUT = ROOT / "runs/rs232_gate_v1"
YOSYS = ROOT / "trusthub/venv/Scripts/yowasp-yosys.exe"


def stubs(text):
    lines = []
    for name, ports in sorted(cell_ports(text).items()):
        output_names = OUTPUT_PORTS | {"Y", "Z", "ZN"}
        outputs = set(ports) & output_names
        inputs = set(ports) - output_names
        if name.startswith("MUX") and "S" in ports:
            inputs.add("S"); outputs.discard("S")
        elif name.startswith("FADD") and "S" in ports:
            outputs.add("S"); inputs.discard("S")
        if not outputs or not inputs:
            raise ValueError(f"Unclassified RS232 cell ports: {name}: {sorted(ports)}")
        declaration = ", ".join([f"input {p}" for p in sorted(inputs)] +
                                [f"output {p}" for p in sorted(outputs)])
        lines.append(f"(* blackbox *) module {name}({declaration}); endmodule")
    return "\n".join(lines) + "\n"


def main():
    records = json.loads((SOURCE / "inventory.json").read_text(encoding="utf-8"))
    summary = []
    for record in records:
        source = ROOT / record["source"]
        if sha256(source) != record["sha256"]:
            raise ValueError(f"RS232 source hash mismatch: {source}")
        target = OUT / record["benchmark"] / record["technology"] / "trojan"
        target.mkdir(parents=True, exist_ok=True)
        stub = target / "cell_stubs.v"
        stub.write_text(stubs(source.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        json_path = target / "yosys.json"
        script = (f"read_verilog -lib {stub.relative_to(ROOT).as_posix()}; "
                  f"read_verilog {source.relative_to(ROOT).as_posix()}; "
                  f"hierarchy -check -top uart; flatten; write_json {json_path.relative_to(ROOT).as_posix()}")
        completed = subprocess.run([str(YOSYS), "-Q", "-T", "-q", "-p", script], cwd=ROOT,
                                   capture_output=True, text=True)
        (target / "yosys.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode or not json_path.is_file():
            raise RuntimeError(f"RS232 parse failed: {record['benchmark']} {record['technology']}")
        graph_id = f"rs232_gate_v1/{record['benchmark']}/{record['technology']}/trojan"
        lines = {source.name: len(source.read_text(encoding="utf-8", errors="replace").splitlines())}
        graph, metadata = graph_from_json(json.loads(json_path.read_text(encoding="utf-8")),
                                          "uart", graph_id, 1, lines)
        metadata.update({"benchmark": record["benchmark"], "side": "trojan", "technology": record["technology"],
                         "top": "uart", "source_level": "gate_netlist_lines_not_RTL",
                         "synthesis_flow": "mapped RS232 netlist with port-direction stubs; no clean counterpart",
                         "yosys_script": script, "yosys_json_sha256": sha256(json_path),
                         "cell_stubs_sha256": sha256(stub),
                         "sources": {record["source"]: sha256(source)}})
        torch.save(graph, target / "graph.pt")
        (target / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        named = [n for n in metadata["node_names"] if "trojan" in n.lower()]
        summary.append({"graph_id": graph_id, "nodes": graph.num_nodes, "edges": graph.num_edges,
                        "trojan_named_candidates": len(named), "source_sha256": record["sha256"],
                        "status": "trojan_only_unreviewed"})
        print(graph_id, graph.num_nodes, len(named), flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
