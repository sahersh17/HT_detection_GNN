"""Add typed ports, cell pins, and constants to the G1c diagnostic graphs.

This view uses no cell instance name or top-level port spelling as a feature.
It is an exploratory representation change after the audit_v1 snapshot.
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import torch
from torch_geometric.data import Data

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
from build import graph_from_json  # noqa: E402

SOURCE = ROOT / "runs/matched_insertion_v3"
OUT = ROOT / "runs/port_aware_v2"
ROLES = ("primary_input", "real_output", "cell_input_pin", "constant", "undriven")
PINS = ("A", "B", "C", "D", "E", "F", "G", "H", "S", "CLK", "EN", "RST", "OTHER")
CONSTANTS = ("0", "1", "x", "z")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert(document, top, graph_id, label, gate_labels):
    gate, metadata = graph_from_json(document, top, graph_id, label)
    module = document["modules"][top]
    names = metadata["node_names"]
    index = {name: i for i, name in enumerate(names)}
    input_bits = sorted({bit for port in module["ports"].values() if port["direction"] == "input"
                         for bit in port["bits"] if isinstance(bit, int)})
    outputs = [(name, i, bit) for name, port in module["ports"].items()
               if port["direction"] == "output" for i, bit in enumerate(port["bits"])]
    input_index = {bit: len(names) + i for i, bit in enumerate(input_bits)}
    output_offset = len(names) + len(input_bits)
    # Wide memory/arithmetic cells can have thousands of bit connections.
    # Keep their original direct gate edges; type pins on one-bit primitives.
    typed_names = {name for name in names if module["cells"][name]["type"].startswith("$_")
                   and all(len(module["cells"][name]["connections"][pin]) == 1
                           for pin, direction in module["cells"][name]["port_directions"].items()
                           if direction == "input")}
    pin_specs = [(name, pin, i, bit) for name in names if name in typed_names
                 for pin, direction in sorted(module["cells"][name]["port_directions"].items())
                 if direction == "input"
                 for i, bit in enumerate(module["cells"][name]["connections"][pin])]
    pin_offset = output_offset + len(outputs)
    constant_values = sorted({str(bit).lower() for _, _, _, bit in pin_specs if isinstance(bit, str)} |
                             {str(bit).lower() for _, _, bit in outputs if isinstance(bit, str)})
    if set(constant_values) - set(CONSTANTS):
        raise ValueError(f"Unknown Yosys constant: {set(constant_values) - set(CONSTANTS)}")
    const_offset = pin_offset + len(pin_specs)
    const_index = {value: const_offset + i for i, value in enumerate(constant_values)}
    drivers = defaultdict(list)
    for name in names:
        cell = module["cells"][name]
        for pin, direction in cell["port_directions"].items():
            if direction == "output":
                for bit in cell["connections"][pin]:
                    if isinstance(bit, int):
                        drivers[bit].append(index[name])
    undriven_bits = sorted({bit for _, _, _, bit in pin_specs if isinstance(bit, int)
                            and bit not in input_index and bit not in drivers} |
                           {bit for _, _, bit in outputs if isinstance(bit, int)
                            and bit not in input_index and bit not in drivers})
    unknown_offset = const_offset + len(constant_values)
    unknown_index = {bit: unknown_offset + i for i, bit in enumerate(undriven_bits)}
    node_count = unknown_offset + len(undriven_bits)
    old_gate_classes = gate.x.shape[1] - 4
    role_offset = old_gate_classes
    pin_role_offset = role_offset + len(ROLES)
    const_role_offset = pin_role_offset + len(PINS)
    numeric_offset = const_role_offset + len(CONSTANTS)
    x = torch.zeros((node_count, numeric_offset + 4), dtype=torch.float32)
    x[:len(names), :old_gate_classes] = gate.x[:, :old_gate_classes]
    x[:len(names), numeric_offset:] = gate.x[:, old_gate_classes:]
    for i in range(len(input_bits)):
        x[len(names) + i, role_offset + ROLES.index("primary_input")] = 1
    for i in range(len(outputs)):
        x[output_offset + i, role_offset + ROLES.index("real_output")] = 1
    for i, (_, pin, _, _) in enumerate(pin_specs):
        x[pin_offset + i, role_offset + ROLES.index("cell_input_pin")] = 1
        x[pin_offset + i, pin_role_offset + PINS.index(pin if pin in PINS else "OTHER")] = 1
    for value, i in const_index.items():
        x[i, role_offset + ROLES.index("constant")] = 1
        x[i, const_role_offset + CONSTANTS.index(value)] = 1
    for i in unknown_index.values():
        x[i, role_offset + ROLES.index("undriven")] = 1

    def sources(bit):
        if isinstance(bit, str):
            return [const_index[bit.lower()]]
        result = drivers.get(bit)
        if result:
            return result
        return [input_index[bit]] if bit in input_index else [unknown_index[bit]]

    edges = set(map(tuple, gate.edge_index.T.tolist()))
    for i, (name, _, _, bit) in enumerate(pin_specs):
        pin_node = pin_offset + i
        edges.add((pin_node, index[name]))
        for source in sources(bit):
            edges.add((source, pin_node))
    for i, (_, _, bit) in enumerate(outputs):
        for source in sources(bit):
            edges.add((source, output_offset + i))
    ordered = sorted(edges)
    data = Data(x=x, edge_index=torch.tensor(ordered, dtype=torch.long).T.contiguous(), y=gate.y)
    data.graph_id = graph_id
    labels = [*gate_labels, *([0] * (node_count - len(names)))]
    if len(labels) != node_count or sum(labels) != sum(gate_labels):
        raise ValueError("Gate-label alignment changed")
    parts = {"gate_nodes": len(names), "input_nodes": len(input_bits),
             "output_nodes": len(outputs), "pin_nodes": len(pin_specs),
             "typed_primitive_gate_nodes": len(typed_names),
             "untyped_gate_nodes": len(names) - len(typed_names),
             "constant_nodes": len(const_index), "undriven_nodes": len(undriven_bits),
             "gate_names_sha256": metadata["node_names_sha256"]}
    return data, labels, parts


def main():
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for row in manifest["records"]:
        source_dir = SOURCE / row["host"] / row["variant"]
        source_json = source_dir / "yosys.json"
        if sha256(source_json) != row["json_sha256"]:
            raise ValueError(f"Synthetic source changed: {source_json}")
        labels_record = json.loads((source_dir / "node_labels.json").read_text(encoding="utf-8"))
        document = json.loads(source_json.read_text(encoding="utf-8"))
        graph, labels, parts = convert(document, row["top"],
            f"port_aware_v2/{row['host']}/{row['variant']}", int(row["variant"] == "trojan"),
            labels_record["labels"])
        if labels_record["node_names_sha256"] != parts["gate_names_sha256"]:
            raise ValueError("Gate node order changed")
        target_dir = OUT / row["host"] / row["variant"]
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "graph.pt"
        torch.save(graph, target)
        (target_dir / "node_labels.json").write_text(json.dumps({"graph_id": graph.graph_id,
            "labels": labels, **parts}), encoding="utf-8")
        rows.append({"host": row["host"], "variant": row["variant"],
                     "source_json_sha256": row["json_sha256"], "graph_sha256": sha256(target),
                     "nodes": graph.num_nodes, "edges": int(graph.edge_index.shape[1]),
                     "positive_nodes": sum(labels), **parts})
        print(row["host"], row["variant"], graph.num_nodes, graph.edge_index.shape[1], flush=True)
    (OUT / "manifest.json").write_text(json.dumps({"status": "exploratory_typed_port_graph",
        "source": "runs/matched_insertion_v3", "raw_instance_or_port_names_in_features": False,
        "node_roles": ROLES, "pin_types": PINS, "constant_values": CONSTANTS,
        "direct_gate_edges_retained": True, "records": rows}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
