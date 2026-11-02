"""Build a separate, source-aligned typed view of the 52 Verilog graphs.

The original graph tensors and CodeBERT embeddings are never changed. This
experiment uses saved, verified Yosys JSON and exact source-line manifests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import torch
from torch_geometric.data import Data

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from train_cv import _safe_classes  # noqa: E402

OUT = ROOT / "runs" / "typed_fusion_v1"
ROLES = ("cell", "primary_input", "real_output", "const_zero", "const_one")
PINS = ("data", "clock", "reset", "enable", "select", "output", "other")
NODE_DIM = 16 + 4 + len(ROLES) + 11
EDGE_DIM = 2 + len(PINS) + 1
RTL_DIM = 16
EXCLUDED = {"$scopeinfo", "$print", "$display"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin_role(cell_type: str, port: str) -> str:
    name = port.upper().strip("\\")
    sequential = bool(re.search(r"DFF|LATCH|FF", cell_type.upper()))
    if sequential and name in {"C", "CLK", "CK", "CLOCK", "G"}:
        return "clock"
    if sequential and ("RST" in name or "RESET" in name or name in {"R", "RN", "CLR", "PRE", "S"}):
        return "reset"
    if sequential and name in {"E", "EN", "CE", "ENABLE"}:
        return "enable"
    if name in {"S", "SEL", "SELECT"}:
        return "select"
    return "data"


def graph_view(document: dict, metadata: dict, base: Data) -> Data:
    """Add bit-level boundary nodes and pin-typed, directed cell connections."""
    module = document["modules"][metadata["top"]]
    cells = {n: c for n, c in module["cells"].items() if c["type"].lower() not in EXCLUDED}
    names = metadata["node_names"]
    if set(names) != set(cells) or len(names) != base.num_nodes:
        raise ValueError("Saved graph and Yosys cell order differ")
    ncell = len(names)
    input_bits, output_bits = {}, {}
    boundary = []
    for port_ordinal, (_, port) in enumerate(module.get("ports", {}).items()):
        bits = port["bits"]
        if port["direction"] in ("input", "inout"):
            for bit_ordinal, bit in enumerate(bits):
                if isinstance(bit, int):
                    idx = ncell + len(boundary)
                    input_bits.setdefault(bit, idx)
                    boundary.append(("primary_input", port_ordinal, bit_ordinal, len(bits)))
        if port["direction"] in ("output", "inout"):
            for bit_ordinal, bit in enumerate(bits):
                if isinstance(bit, int):
                    idx = ncell + len(boundary)
                    output_bits.setdefault(bit, []).append(idx)
                    boundary.append(("real_output", port_ordinal, bit_ordinal, len(bits)))
    zero = ncell + len(boundary)
    boundary.append(("const_zero", 0, 0, 1))
    one = ncell + len(boundary)
    boundary.append(("const_one", 0, 0, 1))
    x = torch.zeros((ncell + len(boundary), NODE_DIM), dtype=torch.float32)
    x[:ncell, :16] = base.x[:, :16].float()
    x[:ncell, 16:20] = torch.log1p(base.x[:, 16:20].float().clamp(min=0))
    x[:ncell, 20] = 1
    for offset, (role, port_ord, bit_ord, width) in enumerate(boundary):
        idx = ncell + offset
        x[idx, 20 + ROLES.index(role)] = 1
        x[idx, 25 + 9] = port_ord / max(1, len(module.get("ports", {})) - 1)
        x[idx, 25 + 10] = bit_ord / max(1, width - 1)

    index = {name: i for i, name in enumerate(names)}
    drivers = {}
    for name, c in cells.items():
        for port, direction in c["port_directions"].items():
            if direction == "output":
                for bit in c["connections"][port]:
                    if isinstance(bit, int):
                        old = drivers.setdefault(bit, index[name])
                        if old != index[name]:
                            raise ValueError(f"Multiple drivers for bit {bit}")
    primary_node_ids = set(input_bits.values())
    src, dst, attrs = [], [], []
    counts = torch.zeros((ncell, 9), dtype=torch.float32)

    def add(a: int, b: int, role: str, bit_fraction: float) -> None:
        pin = PINS.index(role)
        forward = [1.0, 0.0] + [float(i == pin) for i in range(len(PINS))] + [bit_fraction]
        reverse = [0.0, 1.0] + [float(i == pin) for i in range(len(PINS))] + [bit_fraction]
        src.extend((a, b)); dst.extend((b, a)); attrs.extend((forward, reverse))

    for name in names:
        c = cells[name]
        target = index[name]
        total = 0
        for port, direction in c["port_directions"].items():
            bits = c["connections"][port]
            if direction == "input":
                role = pin_role(c["type"], port)
                for pos, bit in enumerate(bits):
                    total += 1
                    if isinstance(bit, int):
                        source = drivers.get(bit, input_bits.get(bit))
                        if source is None:
                            continue
                        if source in primary_node_ids:
                            counts[target, 0] += 1
                    elif str(bit) in ("0", "1"):
                        source = zero if str(bit) == "0" else one
                        counts[target, 1 if source == zero else 2] += 1
                    else:
                        continue
                    if source != target:
                        add(source, target, role, pos / max(1, len(bits) - 1))
                    if role == "clock": counts[target, 4] += 1
                    if role == "reset": counts[target, 5] += 1
                    if role == "enable": counts[target, 6] += 1
            elif direction == "output":
                counts[target, 8] += len(bits)
        counts[target, 7] = total
    for bit, targets in output_bits.items():
        source = drivers.get(bit, input_bits.get(bit))
        if source is None:
            source = zero if str(bit) == "0" else one if str(bit) == "1" else None
        if source is not None:
            for target in targets:
                add(source, target, "output", 0.0)
                if source < ncell: counts[source, 3] += 1
    denom = counts[:, 7].clamp(min=1)
    x[:ncell, 25:28] = counts[:, :3] / denom[:, None]
    x[:ncell, 28] = counts[:, 3] / counts[:, 8].clamp(min=1)
    x[:ncell, 29:32] = counts[:, 4:7] / denom[:, None]
    x[:ncell, 32] = torch.log1p(counts[:, 7])
    x[:ncell, 33] = torch.log1p(counts[:, 8])
    edge_index = torch.tensor([src, dst], dtype=torch.long)
    edge_attr = torch.tensor(attrs, dtype=torch.float32)
    out = Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=base.y.clone())
    out.graph_id = metadata["graph_id"]
    out.n_cell = ncell
    return out


COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
TOKENS = re.compile(r"\d+'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+|\d+|[A-Za-z_$][\w$]*|===|!==|==|!=|<=|>=|&&|\|\||<<|>>|\S")


def rtl_features(text: str) -> torch.Tensor:
    """Comment/identifier-insensitive operator and control-flow proportions."""
    tokens = TOKENS.findall(COMMENTS.sub(" ", text))
    if not tokens:
        return torch.zeros(RTL_DIM)
    lower = [t.lower() for t in tokens]
    n = max(1, len(tokens))
    groups = [
        {"if"}, {"case", "casex", "casez"}, {"always", "always_ff", "always_comb"},
        {"posedge", "negedge"}, {"assign"}, {"==", "!=", "===", "!=="},
        {"<", ">", "<=", ">="}, {"&&", "||", "!"}, {"&", "|", "^", "~"},
        {"?", ":"}, {"+", "-", "*", "/"}, {"<<", ">>"},
        {"begin", "end"}, {"reg", "logic"}, {"{", "}"},
    ]
    vals = [sum(t in group for t in lower) / n for group in groups]
    vals.append(sum(bool(re.match(r"\d", t)) for t in tokens) / n)
    return torch.tensor(vals, dtype=torch.float32)


def chunk_features(record: dict) -> torch.Tensor:
    file_text = {Path(p).name: (ROOT / p).read_text(encoding="utf-8", errors="replace").splitlines()
                 for p in record["sources"]}
    rows = []
    for chunk in record["chunks"]:
        parts = []
        for span in chunk["source_spans"]:
            lines = file_text[Path(span["file"]).name]
            parts.append("\n".join(lines[span["start_line"] - 1:span["end_line"]]))
        rows.append(rtl_features("\n".join(parts)))
    return torch.stack(rows)


def alignment(metadata: dict, record: dict) -> tuple[torch.Tensor, torch.Tensor]:
    by_file = defaultdict(list)
    for chunk in record["chunks"]:
        for span in chunk["source_spans"]:
            by_file[Path(span["file"]).name].append((chunk["chunk"], span["start_line"], span["end_line"]))
    pairs, weights = [], []
    for node, spans in enumerate(metadata["source_ranges"]):
        hits = defaultdict(float)
        for filename, start, end in spans:
            for chunk, a, b in by_file.get(Path(filename).name, []):
                overlap = max(0, min(end, b) - max(start, a) + 1)
                if overlap:
                    hits[chunk] += overlap / max(end - start + 1, b - a + 1)
        for chunk, value in sorted(hits.items(), key=lambda row: (-row[1], row[0]))[:3]:
            pairs.append((chunk, node)); weights.append(min(1.0, value))
    if not pairs:
        return torch.empty((2, 0), dtype=torch.long), torch.empty((0,), dtype=torch.float32)
    return torch.tensor(pairs, dtype=torch.long).T.contiguous(), torch.tensor(weights, dtype=torch.float32)


def build_one(benchmark: str, side: str, source_root: Path, record: dict, target: Path) -> dict:
    folder = source_root / benchmark / side
    metadata_path, yosys_path, graph_path = (folder / n for n in ("metadata.json", "yosys.json", "graph.pt"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if digest(yosys_path) != metadata["yosys_json_sha256"]:
        raise ValueError(f"Yosys hash mismatch: {folder}")
    for path, expected in metadata["sources"].items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Source hash mismatch: {path}")
    for path, expected in record["sources"].items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"RTL source hash mismatch: {path}")
    with torch.serialization.safe_globals(_safe_classes()):
        base = torch.load(graph_path, map_location="cpu", weights_only=True)
    if base.graph_id != metadata["graph_id"] or int(base.y.item()) != int(side == "trojan"):
        raise ValueError(f"Graph identity/label mismatch: {folder}")
    document = json.loads(yosys_path.read_text(encoding="utf-8"))
    graph = graph_view(document, metadata, base)
    embedding_path = ROOT / "runs" / ("rtl_clean_v1" if source_root.name == "provenance_v1" else "rtl_expansion_v1") / record["embedding_file"]
    if digest(embedding_path) != record["embedding_sha256"]:
        raise ValueError(f"CodeBERT embedding hash mismatch: {embedding_path}")
    rtl = torch.load(embedding_path, map_location="cpu", weights_only=True).float()
    if rtl.shape != (record["num_chunks"], 768):
        raise ValueError("RTL embedding shape mismatch")
    struct = chunk_features(record)
    links, weights = alignment(metadata, record)
    item = {"graph": graph, "rtl": rtl, "struct": struct, "links": links, "weights": weights,
            "benchmark": benchmark, "side": side, "label": int(side == "trojan")}
    target.parent.mkdir(parents=True, exist_ok=True)
    torch.save(item, target)
    return {"benchmark": benchmark, "side": side, "file": target.relative_to(ROOT).as_posix(),
            "sha256": digest(target), "cells": graph.n_cell, "nodes": graph.num_nodes,
            "edges": graph.num_edges, "chunks": rtl.shape[0], "links": links.shape[1],
            "aligned_cells": int(torch.unique(links[1]).numel()) if links.numel() else 0,
            "source_graph_sha256": digest(graph_path), "source_rtl_sha256": digest(embedding_path)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark", action="append")
    args = ap.parse_args()
    dev = json.loads((ROOT / "runs/rtl_clean_v1/manifest.json").read_text())["records"]
    ext = json.loads((ROOT / "runs/rtl_expansion_v1/manifest.json").read_text())["records"]
    selected = set(args.benchmark or [])
    rows = []
    for record in dev + ext:
        benchmark, side = record["benchmark"], record["side"]
        if selected and benchmark not in selected:
            continue
        graph_root = (ROOT / "runs" / ("provenance_v1" if record in dev else
                      "expansion_graphs" if benchmark.startswith("memctrl-") else "expansion_pic_graphs"))
        target = OUT / "prepared" / benchmark / f"{side}.pt"
        rows.append(build_one(benchmark, side, graph_root, record, target))
        print(f"{benchmark}/{side}: {rows[-1]['nodes']} nodes, {rows[-1]['links']} links", flush=True)
    manifest = {"status": "prepared", "node_dim": NODE_DIM, "edge_dim": EDGE_DIM, "rtl_struct_dim": RTL_DIM,
                "scope": "source-aligned, weakly supervised experimental view; no reviewed gate labels",
                "records": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"records": len(rows), "nodes": sum(r["nodes"] for r in rows),
                      "links": sum(r["links"] for r in rows)}, indent=2))


if __name__ == "__main__":
    main()
