"""Add primary-input and real-output nodes to the versioned G1c gate graphs."""
import hashlib
import json
import sys
from pathlib import Path

import torch
from torch_geometric.data import Data

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
from build import graph_from_json  # noqa: E402

SOURCE = ROOT / "runs/matched_insertion_v3"
OUT = ROOT / "runs/port_aware_v1"


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert(document, top, graph_id, label, gate_labels):
    gate, metadata = graph_from_json(document, top, graph_id, label)
    module = document["modules"][top]
    names = metadata["node_names"]
    gate_index = {name: i for i, name in enumerate(names)}
    input_bits = sorted({bit for port in module["ports"].values() if port["direction"] == "input"
                         for bit in port["bits"] if isinstance(bit, int)})
    outputs = [(name, i, bit) for name, port in module["ports"].items()
               if port["direction"] == "output" for i, bit in enumerate(port["bits"])]
    input_index = {bit: len(names) + i for i, bit in enumerate(input_bits)}
    output_offset = len(names) + len(input_bits)
    drivers = {}
    for name in names:
        cell = module["cells"][name]
        for pin, direction in cell["port_directions"].items():
            if direction == "output":
                for bit in cell["connections"][pin]:
                    if isinstance(bit, int):
                        drivers[bit] = gate_index[name]
    edges = set(map(tuple, gate.edge_index.T.tolist()))
    for name in names:
        cell = module["cells"][name]
        for pin, direction in cell["port_directions"].items():
            if direction == "input":
                for bit in cell["connections"][pin]:
                    if bit in input_index:
                        edges.add((input_index[bit], gate_index[name]))
    for i, (_, _, bit) in enumerate(outputs):
        source = drivers.get(bit, input_index.get(bit))
        if source is not None:
            edges.add((source, output_offset + i))
    n_gate, n_input, n_output = len(names), len(input_bits), len(outputs)
    original = gate.x
    old_onehot = original.shape[1] - 4
    x = torch.zeros((n_gate + n_input + n_output, original.shape[1] + 2), dtype=torch.float32)
    x[:n_gate, :old_onehot] = original[:, :old_onehot]
    x[:n_gate, old_onehot + 2:] = original[:, old_onehot:]
    x[n_gate:n_gate + n_input, old_onehot] = 1
    x[n_gate + n_input:, old_onehot + 1] = 1
    ordered_edges = sorted(edges)
    data = Data(x=x, edge_index=torch.tensor(ordered_edges, dtype=torch.long).T.contiguous(), y=gate.y)
    data.graph_id = graph_id
    labels = [*gate_labels, *([0] * (n_input + n_output))]
    if len(labels) != data.num_nodes:
        raise ValueError("Node-label length mismatch")
    return data, labels, {"gate_nodes": n_gate, "input_nodes": n_input,
                          "output_nodes": n_output, "gate_names_sha256": metadata["node_names_sha256"]}


def main():
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for row in manifest["records"]:
        source_dir = SOURCE / row["host"] / row["variant"]
        source_json = source_dir / "yosys.json"
        if hash_file(source_json) != row["json_sha256"]:
            raise ValueError(f"Synthetic source changed: {source_json}")
        labels_record = json.loads((source_dir / "node_labels.json").read_text(encoding="utf-8"))
        document = json.loads(source_json.read_text(encoding="utf-8"))
        graph, labels, parts = convert(document, row["top"],
            f"port_aware_v1/{row['host']}/{row['variant']}", int(row["variant"] == "trojan"),
            labels_record["labels"])
        if labels_record["node_names_sha256"] != parts["gate_names_sha256"]:
            raise ValueError("Gate node order changed")
        target_dir = OUT / row["host"] / row["variant"]
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "graph.pt"
        torch.save(graph, target)
        (target_dir / "node_labels.json").write_text(json.dumps({"graph_id": graph.graph_id,
            "labels": labels, **parts}), encoding="utf-8")
        item = {"host": row["host"], "variant": row["variant"], "source_json_sha256": row["json_sha256"],
                "graph_sha256": hash_file(target), "nodes": graph.num_nodes,
                "edges": int(graph.edge_index.shape[1]), "positive_nodes": sum(labels), **parts}
        rows.append(item)
        print(row["host"], row["variant"], graph.num_nodes, graph.edge_index.shape[1], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps({"status": "diagnostic_graph_view",
        "source": "runs/matched_insertion_v3", "port_names_in_features": False,
        "role_features": ["primary_input", "real_output"], "records": rows}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
