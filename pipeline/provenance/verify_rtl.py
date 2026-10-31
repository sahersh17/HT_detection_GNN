"""Verify testbench-free CodeBERT tensors, source hashes, chunk spans, and folds.

Usage: python pipeline/provenance/verify_rtl.py
"""
import hashlib
import argparse
import json
from pathlib import Path

import torch

from build import ROOT


def verify(root=ROOT / "runs" / "rtl_clean_v1", expansion=False):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if expansion:
        benchmarks = ["memctrl-T100", *(f"PIC16F84-T{n}" for n in (100, 200, 300, 400))]
        expected = {(benchmark, side) for benchmark in benchmarks for side in ("clean", "trojan")}
        folds = []
    else:
        samples = json.loads((ROOT / "data" / "integrated" / "paired_manifest.json").read_text(encoding="utf-8"))["samples"]
        expected = {(s["benchmark"], s["class_name"]) for s in samples}
        folds = json.loads((ROOT / "data" / "integrated" / "group_folds.json").read_text(encoding="utf-8"))["folds"]
    records = {(r["benchmark"], r["side"]): r for r in manifest["records"]}
    if len(records) != len(manifest["records"]) or set(records) != expected or manifest["testbenches_included"]:
        raise ValueError("Embedding manifest is incomplete, duplicated, or includes testbenches")
    for record in manifest["records"]:
        path = root / record["embedding_file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["embedding_sha256"]:
            raise ValueError(f"Embedding hash differs: {path}")
        tensor = torch.load(path, map_location="cpu", weights_only=True)
        if tensor.ndim != 2 or tuple(tensor.shape) != (record["num_chunks"], 768) or not torch.isfinite(tensor).all():
            raise ValueError(f"Embedding tensor invalid: {path}")
        if len(record["chunks"]) != record["num_chunks"]:
            raise ValueError(f"Chunk count differs: {path}")
        line_counts = {}
        source_texts = []
        for relative, expected_hash in record["sources"].items():
            source = ROOT / relative
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected_hash:
                raise ValueError(f"Source hash differs: {relative}")
            if source.name.lower().startswith(("test", "tb")) or "testbench" in source.name.lower():
                raise ValueError(f"Testbench in embedding: {relative}")
            source_text = source.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
            source_texts.append(source_text)
            line_counts[relative] = len(source_text.splitlines())
        if hashlib.sha256("\n\n".join(source_texts).encode("utf-8")).hexdigest() != record["source_text_sha256"]:
            raise ValueError(f"Combined RTL text hash differs: {path}")
        for chunk in record["chunks"]:
            if not chunk["source_spans"]:
                raise ValueError(f"Missing source span: {path}")
            for span in chunk["source_spans"]:
                if span["file"] not in line_counts or not 1 <= span["start_line"] <= span["end_line"] <= line_counts[span["file"]]:
                    raise ValueError(f"Invalid chunk source span: {path}")
    clean_hash = {r["benchmark"]: r["source_text_sha256"] for r in manifest["records"] if r["side"] == "clean"}
    for fold in folds:
        train = {clean_hash[b] for b in fold["train_benchmarks"]}
        test = {clean_hash[b] for b in fold["test_benchmarks"]}
        if train & test:
            raise ValueError(f"Clean RTL leakage in fold {fold['fold']}")
    summary = {"status": "verified", "samples": len(records), "unique_source_texts": manifest["unique_source_texts"],
               "independent_clean_source_groups": len(set(clean_hash.values())),
               "total_chunks": sum(r["num_chunks"] for r in manifest["records"]),
               "testbenches_included": False, "chunks_with_source_spans": True}
    (root / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expansion", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "runs" / ("rtl_expansion_v1" if args.expansion else "rtl_clean_v1")
    print(json.dumps(verify(folder, args.expansion), indent=2))
