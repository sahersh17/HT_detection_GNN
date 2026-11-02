"""Check prepared typed graphs against the original verified cell graphs."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from train_cv import _safe_classes  # noqa: E402

OUT = ROOT / "runs/typed_fusion_v1"


def base_folder(benchmark: str, side: str) -> Path:
    name = ("provenance_v1" if benchmark.startswith(("AES-", "RS232-")) else
            "expansion_graphs" if benchmark.startswith("memctrl-") else "expansion_pic_graphs")
    return ROOT / "runs" / name / benchmark / side


def main() -> None:
    manifest = json.loads((OUT / "manifest.json").read_text())
    rows = manifest["records"]
    if len(rows) != 52:
        raise ValueError(f"Expected 52 records, got {len(rows)}")
    total_cells = total_links = total_edges = 0
    for row in rows:
        path = ROOT / row["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"Prepared hash mismatch: {path}")
        with torch.serialization.safe_globals(_safe_classes()):
            item = torch.load(path, map_location="cpu", weights_only=True)
            base = torch.load(base_folder(row["benchmark"], row["side"]) / "graph.pt",
                              map_location="cpu", weights_only=True)
        graph = item["graph"]
        if graph.n_cell != base.num_nodes or graph.graph_id != base.graph_id:
            raise ValueError(f"Cell order/graph ID changed: {path}")
        if graph.x.shape != (row["nodes"], manifest["node_dim"]) or graph.edge_attr.shape != (row["edges"], manifest["edge_dim"]):
            raise ValueError(f"Invalid typed tensor shape: {path}")
        if not torch.isfinite(graph.x).all() or not torch.isfinite(graph.edge_attr).all():
            raise ValueError(f"Nonfinite typed feature: {path}")
        if not torch.equal(graph.x[:graph.n_cell, :16], base.x[:, :16]):
            raise ValueError(f"Cell gate class changed: {path}")
        forward = graph.edge_attr[:, 0] == 1
        cell_edge = forward & (graph.edge_index[0] < graph.n_cell) & (graph.edge_index[1] < graph.n_cell)
        typed_pairs = set(map(tuple, graph.edge_index[:, cell_edge].T.tolist()))
        base_pairs = set(map(tuple, base.edge_index.T.tolist()))
        if typed_pairs != base_pairs:
            raise ValueError(f"Cell connectivity changed: missing={len(base_pairs - typed_pairs)}, extra={len(typed_pairs - base_pairs)} at {path}")
        links, weights = item["links"], item["weights"]
        if (links.shape[0] != 2 or links.shape[1] != len(weights) or
                (links.numel() and (links[0].max() >= len(item["rtl"]) or links[1].max() >= graph.n_cell)) or
                not torch.isfinite(weights).all() or (weights.numel() and (weights <= 0).any())):
            raise ValueError(f"Bad source alignment: {path}")
        if item["struct"].shape != (len(item["rtl"]), manifest["rtl_struct_dim"]):
            raise ValueError(f"RTL feature alignment changed: {path}")
        total_cells += graph.n_cell
        total_edges += graph.num_edges
        total_links += links.shape[1]
    result = {"status": "verified", "records": len(rows), "cells": total_cells,
              "typed_edges": total_edges, "gate_to_rtl_links": total_links,
              "checks": ["source and prepared hashes", "ordered gate classes", "all original cell edges",
                         "typed feature shapes", "finite features", "chunk/cell alignment ranges"]}
    (OUT / "verification.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
