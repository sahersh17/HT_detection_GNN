"""Check typed-port graph hashes, feature channels, and label alignment."""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from train_cv import _safe_classes  # noqa: E402

OUT = ROOT / "runs/port_aware_v2"
SOURCE = ROOT / "runs/matched_insertion_v3"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    roles, pins, constants = (manifest["node_roles"], manifest["pin_types"],
                              manifest["constant_values"])
    if len(manifest["records"]) != 12 or manifest["raw_instance_or_port_names_in_features"]:
        raise ValueError("Unexpected typed-port cohort")
    host_shapes = defaultdict(set)
    for row in manifest["records"]:
        folder = OUT / row["host"] / row["variant"]
        graph_path = folder / "graph.pt"
        source_path = SOURCE / row["host"] / row["variant"] / "yosys.json"
        if sha256(graph_path) != row["graph_sha256"] or sha256(source_path) != row["source_json_sha256"]:
            raise ValueError(f"Changed graph/source: {row['host']}/{row['variant']}")
        with torch.serialization.safe_globals(_safe_classes()):
            graph = torch.load(graph_path, map_location="cpu", weights_only=True)
        labels = json.loads((folder / "node_labels.json").read_text(encoding="utf-8"))
        if (graph.num_nodes != row["nodes"] or graph.edge_index.shape[1] != row["edges"] or
                len(labels["labels"]) != graph.num_nodes or labels["gate_names_sha256"] != row["gate_names_sha256"]):
            raise ValueError("Graph or row-order alignment mismatch")
        if graph.x.shape[1] < len(roles) + len(pins) + len(constants) + 4:
            raise ValueError("Feature width is too small")
        if not torch.isfinite(graph.x).all() or graph.edge_index.min() < 0 or graph.edge_index.max() >= graph.num_nodes:
            raise ValueError("Invalid graph tensor")
        n_gate = row["gate_nodes"]
        if any(labels["labels"][n_gate:]) or sum(labels["labels"]) != row["positive_nodes"]:
            raise ValueError("Non-gate node mislabeled")
        if row["variant"] != "trojan" and row["positive_nodes"]:
            raise ValueError("Benign graph has positive gate labels")
        base = graph.x.shape[1] - len(roles) - len(pins) - len(constants) - 4
        role = graph.x[:, base:base + len(roles)]
        if not torch.equal(role[:n_gate], torch.zeros_like(role[:n_gate])):
            raise ValueError("Gate assigned non-gate role")
        if not torch.equal(role[n_gate:].sum(1), torch.ones(graph.num_nodes - n_gate)):
            raise ValueError("Non-gate role is not one-hot")
        host_shapes[row["host"]].add((row["nodes"], row["edges"], row["pin_nodes"],
                                      row["constant_nodes"], row["undriven_nodes"]))
    if any(len(shapes) != 1 for shapes in host_shapes.values()):
        raise ValueError("Matched variants differ in structural counts")
    (OUT / "verification.json").write_text(json.dumps({
        "status": "hash_feature_label_verified",
        "manifest_sha256": sha256(OUT / "manifest.json"),
        "graphs": len(manifest["records"]), "hosts": len(host_shapes),
        "limits": ["Constructed labels only", "Local inserted-cone semantics checked in source pilot",
                   "Not a real Trust-Hub gate-label validation"]}, indent=2), encoding="utf-8")
    print(f"Verified {len(manifest['records'])} typed-port graphs across {len(host_shapes)} hosts")


if __name__ == "__main__":
    main()
