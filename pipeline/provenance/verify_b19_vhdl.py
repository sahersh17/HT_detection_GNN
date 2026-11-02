"""Check b19 source, graph, embedding, and VHDL chunk provenance."""
import hashlib
import json
from pathlib import Path

import torch

from build import ROOT
from embed_rtl import assemble

RUN = ROOT / "runs/b19_rtl_v1"
GRAPH_PROTOCOL = ROOT / "data/lofo_expanded_b19/protocol.json"
OUT = ROOT / "data/audit_v1/b19_embedding_audit.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = RUN / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    graph = json.loads(GRAPH_PROTOCOL.read_text(encoding="utf-8"))
    graph_rows = {(r["benchmark"], r["side"]): r for r in graph["samples"] if r["family"] == "b19"}
    if manifest["samples"] != 6 or len(graph_rows) != 6 or len(manifest["records"]) != 6:
        raise ValueError("Incomplete b19 paired cohort")
    chunks = 0
    unique_clean = set()
    for row in manifest["records"]:
        key = row["benchmark"], row["side"]
        if key not in graph_rows:
            raise ValueError(f"Embedding has no graph: {key}")
        source = ROOT / row["source"]
        if sha256(source) != row["source_sha256"]:
            raise ValueError(f"Source hash mismatch: {key}")
        content, _ = assemble([source])
        if hashlib.sha256(content.encode()).hexdigest() != row["source_text_sha256"]:
            raise ValueError(f"Source text hash mismatch: {key}")
        embedding = RUN / row["embedding_file"]
        if sha256(embedding) != row["embedding_sha256"]:
            raise ValueError(f"Embedding hash mismatch: {key}")
        tensor = torch.load(embedding, map_location="cpu", weights_only=True)
        if tensor.shape != (row["num_chunks"], 768) or not torch.isfinite(tensor).all():
            raise ValueError(f"Embedding shape/value mismatch: {key}")
        if len(row["chunks"]) != row["num_chunks"]:
            raise ValueError(f"Chunk count mismatch: {key}")
        line_limit = len(content.splitlines())
        for i, item in enumerate(row["chunks"]):
            if item["chunk"] != i or not item["source_spans"]:
                raise ValueError(f"Unmapped chunk: {key}/{i}")
            if any(span["file"] != row["source"] or span["start_line"] < 1 or
                   span["end_line"] > line_limit or span["start_line"] > span["end_line"]
                   for span in item["source_spans"]):
                raise ValueError(f"Invalid VHDL span: {key}/{i}")
        graph_row = graph_rows[key]
        if sha256(ROOT / graph_row["path"]) != graph_row["sha256"]:
            raise ValueError(f"Graph hash mismatch: {key}")
        if row["side"] == "clean":
            unique_clean.add(row["source_text_sha256"])
        chunks += row["num_chunks"]
    if len(unique_clean) != manifest["independent_clean_sources"]:
        raise ValueError("Clean source group count mismatch")
    audit = {"status": "hash_shape_span_verified_not_model_evaluation",
             "manifest_sha256": sha256(manifest_path), "graph_protocol_sha256": sha256(GRAPH_PROTOCOL),
             "paired_variants": 3, "samples": 6, "independent_clean_sources": len(unique_clean),
             "total_chunks": chunks, "source_language": "VHDL"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
