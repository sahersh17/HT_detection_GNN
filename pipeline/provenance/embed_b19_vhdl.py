"""Embed the three complete paired b19 VHDL variants as a separate modality version."""
import hashlib
import json
import os
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

from build import ROOT
from embed_rtl import MODEL, MODEL_REVISION, MAX_LENGTH, STRIDE, assemble, line_spans
from embed_new_vhdl import cached_embed

SOURCE = ROOT / "runs/new_trusthub"
OUT = ROOT / "runs/b19_rtl_v1"
INVENTORY = ROOT / "runs/new_trusthub/b19_complete_inventory.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    if len(inventory) != 3 or any(row["family"] != "b19" for row in inventory):
        raise ValueError("Expected the three complete b19 archives")
    expected = {(row["benchmark"], side): row["sources"][side]["b19.vhd"]["sha256"]
                for row in inventory for side in ("clean", "trojan")}
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True)
    model = AutoModel.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True).eval()
    if not tokenizer.is_fast or model.config.hidden_size != 768:
        raise ValueError("Unexpected CodeBERT encoder")
    cache, windows, records = {}, {}, []
    for benchmark, side in sorted(expected):
        source = SOURCE / benchmark / side / "b19.vhd"
        if sha256(source) != expected[(benchmark, side)]:
            raise ValueError(f"b19 source hash mismatch: {source}")
        graph_status = ROOT / "runs/new_vhdl_v1" / benchmark / side / "synthesis_status.json"
        if json.loads(graph_status.read_text(encoding="utf-8"))["status"] != "graph_built_unreviewed":
            raise ValueError(f"b19 graph unavailable: {benchmark}/{side}")
        content, locations = assemble([source])
        key = hashlib.sha256((MODEL_REVISION + content).encode()).hexdigest()
        cache_path = OUT / "file_cache" / f"{key}.pt"
        if key not in cache:
            if cache_path.exists():
                cache[key] = cached_embed(content, tokenizer, model, windows,
                                          torch.load(cache_path, map_location="cpu", weights_only=True))
            else:
                print(f"Encoding {benchmark}/{side}: {len(content)} characters", flush=True)
                cache[key] = cached_embed(content, tokenizer, model, windows)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                torch.save(cache[key], cache_path)
        tensor, offsets, token_counts = cache[key]
        spans = [{"chunk": i, "token_count": token_counts[i],
                  "source_spans": line_spans(offsets[i], locations)} for i in range(len(offsets))]
        if any(not item["source_spans"] for item in spans):
            raise ValueError("Unmapped VHDL chunk")
        target = OUT / f"{benchmark}_{side}.pt"
        torch.save(tensor, target)
        records.append({"benchmark": benchmark, "side": side, "label": int(side == "trojan"),
                        "source_language": "VHDL", "source_text_sha256": hashlib.sha256(content.encode()).hexdigest(),
                        "source_sha256": sha256(source), "source": source.relative_to(ROOT).as_posix(),
                        "embedding_file": target.name, "embedding_sha256": sha256(target),
                        "num_chunks": int(tensor.shape[0]), "embedding_dim": int(tensor.shape[1]),
                        "chunks": spans})
        (OUT / "progress.json").write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")
        print(f"{benchmark}/{side}: {tensor.shape[0]} chunks", flush=True)
    manifest = {"status": "generated_unreviewed", "model": MODEL,
                "model_revision": MODEL_REVISION, "max_length": MAX_LENGTH, "stride": STRIDE,
                "source_language": "VHDL", "window_boundary": "one original VHDL source file",
                "testbenches_included": False, "inventory_sha256": sha256(INVENTORY),
                "samples": len(records), "independent_clean_sources":
                len({r["source_text_sha256"] for r in records if r["side"] == "clean"}),
                "records": records}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
