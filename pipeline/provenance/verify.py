"""Check exact graph/metadata/candidate row alignment for a provenance export.

Usage: python pipeline/provenance/verify.py runs/provenance_v1
"""
import argparse
import hashlib
import json
from pathlib import Path

import torch

from build import ROOT, graph_from_json, sha256


def verify_one(folder):
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    from torch_geometric.data import Data
    from torch_geometric.data.data import DataEdgeAttr, DataTensorAttr
    from torch_geometric.data.storage import GlobalStorage
    with torch.serialization.safe_globals([Data, DataEdgeAttr, DataTensorAttr, GlobalStorage]):
        graph = torch.load(folder / "graph.pt", map_location="cpu", weights_only=True)
    document = json.loads((folder / "yosys.json").read_text(encoding="utf-8"))
    if sha256(folder / "yosys.json") != metadata["yosys_json_sha256"]:
        raise ValueError(f"Yosys JSON hash mismatch: {folder}")
    line_counts = {}
    for relative, expected_hash in metadata["sources"].items():
        if sha256(ROOT / relative) != expected_hash:
            raise ValueError(f"Source RTL hash mismatch: {relative}")
        filename = Path(relative).name
        if filename in line_counts:
            raise ValueError(f"Ambiguous source basename: {filename}")
        line_counts[filename] = len((ROOT / relative).read_text(encoding="utf-8", errors="replace").splitlines())
    rebuilt, expected_meta = graph_from_json(document, metadata["top"], metadata["graph_id"], metadata["label"], line_counts)
    if not torch.equal(graph.x, rebuilt.x) or not torch.equal(graph.edge_index, rebuilt.edge_index):
        raise ValueError(f"Graph tensor differs from Yosys JSON reconstruction: {folder}")
    names = metadata["node_names"]
    checksum = hashlib.sha256(json.dumps(names, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if graph.graph_id != metadata["graph_id"] or graph.num_nodes != metadata["num_nodes"]:
        raise ValueError(f"Graph identity or node count mismatch: {folder}")
    if graph.num_edges != metadata["num_edges"] or graph.x.shape[1] != 20:
        raise ValueError(f"Graph edge count or feature dimension mismatch: {folder}")
    if len(names) != graph.num_nodes or len(set(names)) != len(names) or checksum != metadata["node_names_sha256"]:
        raise ValueError(f"Node order checksum mismatch: {folder}")
    if len(metadata["source_ranges"]) != graph.num_nodes or len(metadata["node_src"]) != graph.num_nodes:
        raise ValueError(f"Source span count mismatch: {folder}")
    for ranges in metadata["source_ranges"]:
        for filename, start, end in ranges:
            if filename not in line_counts or not 1 <= start <= end <= line_counts[filename]:
                raise ValueError(f"Source span points outside original RTL: {folder}: {filename}:{start}-{end}")
    if names != expected_meta["node_names"] or metadata["source_ranges"] != json.loads(json.dumps(expected_meta["source_ranges"])):
        raise ValueError(f"Source/node order differs from Yosys JSON: {folder}")
    candidates_path = folder / "candidate_labels.json"
    if candidates_path.exists():
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        if candidates["reviewed"] or candidates["graph_id"] != graph.graph_id or candidates["node_names"] != names:
            raise ValueError(f"Candidate alignment/status mismatch: {folder}")
        if len(candidates["labels"]) != graph.num_nodes or any(v not in (-1, 0, 1) for v in candidates["labels"]):
            raise ValueError(f"Candidate label shape/value mismatch: {folder}")
    return {"graph_id": graph.graph_id, "nodes": graph.num_nodes,
            "source_covered_nodes": metadata["source_covered_nodes"],
            "candidate_trojan": (candidates["coverage"]["candidate_trojan"] if candidates_path.exists() else None)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    folders = sorted(p.parent for p in args.out.rglob("metadata.json"))
    if not folders:
        parser.error(f"No metadata.json in {args.out}")
    rows = [verify_one(folder) for folder in folders]
    summary = {"status": "verified", "graphs": len(rows), "benchmarks": len({row["graph_id"].split("/")[1] for row in rows}),
               "nodes": sum(row["nodes"] for row in rows),
               "source_covered_nodes": sum(row["source_covered_nodes"] for row in rows),
               "trojan_candidate_nodes": sum(row["candidate_trojan"] or 0 for row in rows),
               "reviewed_gate_labels": 0,
               "graph_version": "provenance_v1 (no ABC; differs from earlier and supplied ZIP graphs)"}
    if args.verbose:
        summary["graphs_detail"] = rows
    print(json.dumps(summary, indent=2))
    (args.out / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
