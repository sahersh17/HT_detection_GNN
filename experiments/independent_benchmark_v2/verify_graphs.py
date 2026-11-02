"""Rebuild and verify every v2 graph and construction-derived candidate label row."""
import hashlib
import json
import sys
from pathlib import Path

import torch
from torch_geometric.data import Data
from torch_geometric.data.data import DataEdgeAttr, DataTensorAttr
from torch_geometric.data.storage import GlobalStorage

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs/independent_benchmark_v2/runs"
EVIDENCE = ROOT / "data/independent_benchmark_v2"
sys.path.insert(0, str(ROOT / "experiments/independent_benchmark_v1"))
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
import build_graphs as source_builder  # noqa: E402
from build import graph_from_json, sha256  # noqa: E402


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_graph(folder):
    metadata = read_json(folder / "metadata.json")
    source = ROOT / metadata["source"]
    if sha256(source) != metadata["source_sha256"]:
        raise ValueError(f"Source hash mismatch: {folder}")
    yosys_path = folder / "yosys.json"
    if sha256(yosys_path) != metadata["yosys_json_sha256"]:
        raise ValueError(f"Yosys hash mismatch: {folder}")
    document = read_json(yosys_path)
    top = source_builder.source_top(source)
    lines = len(source.read_text(encoding="utf-8", errors="replace").splitlines())
    rebuilt, expected = graph_from_json(document, top, metadata["graph_id"],
                                        metadata["label"], {source.name: lines})
    with torch.serialization.safe_globals([Data, DataEdgeAttr, DataTensorAttr, GlobalStorage]):
        graph = torch.load(folder / "graph.pt", map_location="cpu", weights_only=True)
    if graph.graph_id != metadata["graph_id"] or graph.num_nodes != metadata["num_nodes"]:
        raise ValueError(f"Graph identity/count mismatch: {folder}")
    if not torch.equal(graph.x, rebuilt.x) or not torch.equal(graph.edge_index, rebuilt.edge_index):
        raise ValueError(f"Graph tensors differ from Yosys reconstruction: {folder}")
    for field in ("node_names", "node_types", "node_gate_classes", "node_src", "source_ranges",
                  "node_names_sha256", "num_edges"):
        if metadata[field] != json.loads(json.dumps(expected[field])):
            raise ValueError(f"Metadata {field} differs from reconstruction: {folder}")
    for spans in metadata["source_ranges"]:
        if any(name != source.name or not 1 <= start <= end <= lines
               for name, start, end in spans):
            raise ValueError(f"Invalid source span: {folder}")
    return metadata


def main():
    manifest = read_json(EVIDENCE / "manifest.json")
    lineage = read_json(EVIDENCE / "graph_lineage.json")["records"]
    by_variant = {row["variant"]: row for row in lineage}
    expected_variants = {f"{run['run_id']}/{variant['source_path']}"
                         for run in manifest["records"] for variant in run["records"]}
    if len(lineage) != len(expected_variants) or set(by_variant) != expected_variants:
        raise ValueError("Lineage rows missing, duplicated, or unexpected")
    verified = 0
    positive = negative = unknown = 0
    for run in manifest["records"]:
        folder = RUNS / run["run_id"]
        summary = read_json(folder / "summary.json")
        clean_source = folder / (Path(summary["netlist"]).stem + "_conv.v")
        if sha256(clean_source) != run["converted_clean_sha256"]:
            raise ValueError(f"Clean source hash mismatch: {run['run_id']}")
        clean_folder = folder / "graphs/clean"
        clean_meta = verify_graph(clean_folder)
        if clean_meta["label"] != 0 or sha256(clean_folder / "graph.pt") != by_variant[
                f"{run['run_id']}/{run['records'][0]['source_path']}"]["clean_graph_sha256"]:
            raise ValueError(f"Clean graph mismatch: {run['run_id']}")
        for variant in run["records"]:
            key = f"{run['run_id']}/{variant['source_path']}"
            row = by_variant[key]
            infected_source = folder / variant["source_path"]
            infected_folder = folder / "graphs" / infected_source.stem
            if sha256(infected_source) != variant["source_sha256"]:
                raise ValueError(f"Infected source hash mismatch: {key}")
            infected_meta = verify_graph(infected_folder)
            labels_path = infected_folder / "node_labels.json"
            labels_record = read_json(labels_path)
            labels = labels_record["labels"]
            diff = source_builder.source_diff(clean_source, infected_source)
            rebuilt_labels = source_builder.labels_for(infected_meta, diff, infected_source.name)
            digest = hashlib.sha256(json.dumps(labels, separators=(",", ":")).encode()).hexdigest()
            if labels != rebuilt_labels or labels_record["source_diff"] != diff:
                raise ValueError(f"Candidate labels differ from source reconstruction: {key}")
            if labels_record["graph_id"] != infected_meta["graph_id"] or labels_record[
                    "node_names_sha256"] != infected_meta["node_names_sha256"]:
                raise ValueError(f"Candidate label identity mismatch: {key}")
            if labels_record["ordered_labels_sha256"] != digest or any(v not in (-1, 0, 1) for v in labels):
                raise ValueError(f"Candidate label value/checksum mismatch: {key}")
            if labels_record["graph_sha256"] != sha256(infected_folder / "graph.pt"):
                raise ValueError(f"Candidate label graph hash mismatch: {key}")
            if (row["infected_graph_sha256"] != labels_record["graph_sha256"] or
                    row["node_labels_sha256"] != sha256(labels_path) or
                    row["positive"] != labels.count(1) or row["negative"] != labels.count(0) or
                    row["unknown"] != labels.count(-1) or row["infected_nodes"] != len(labels)):
                raise ValueError(f"Lineage summary mismatch: {key}")
            positive += row["positive"]
            negative += row["negative"]
            unknown += row["unknown"]
            verified += 1
    report = {"status": "verified_construction_lineage_not_reviewed_ground_truth",
              "variants": verified, "clean_graphs": len(manifest["records"]),
              "infected_graphs": verified, "positive_candidate_nodes": positive,
              "negative_candidate_nodes": negative, "unknown_nodes": unknown,
              "scope": "Development hosts only; no final-candidate host was generated"}
    (EVIDENCE / "graph_verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
