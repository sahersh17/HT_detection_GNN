"""Embed the original VHDL source for newly extracted MC8051/BasicRSA cases.

Gate-netlist-only B15/s38584 archives have no original RTL view and are kept
out of this fusion modality. Embeddings are a separate VHDL dataset version;
they are not mixed with the earlier Verilog CodeBERT pilot by default.
"""
import hashlib
import json
import os
from importlib.metadata import version
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

from build import ROOT
from embed_rtl import MODEL, MODEL_REVISION, MAX_LENGTH, STRIDE, assemble, line_spans
from synth_vhdl import DEFAULT_GHDL, DEFAULT_OUT, mc8051_core_names

SOURCE = ROOT / "runs" / "new_trusthub"
OUT = ROOT / "runs" / "new_rtl_v1"


def cached_embed(text, tokenizer, model, windows, existing=None):
    encoded = tokenizer(text, truncation=True, max_length=MAX_LENGTH, stride=STRIDE,
                        return_overflowing_tokens=True, padding="max_length",
                        return_attention_mask=True, return_offsets_mapping=True)
    ids, masks = encoded["input_ids"], encoded["attention_mask"]
    keys = [hashlib.sha256(json.dumps([a, b]).encode()).hexdigest() for a, b in zip(ids, masks)]
    if existing is not None:
        for key, vector in zip(keys, existing[0]):
            windows[key] = vector.clone()
        return existing
    missing = list(dict.fromkeys(k for k in keys if k not in windows))
    positions = {key: i for i, key in enumerate(keys)}
    with torch.inference_mode():
        for start in range(0, len(missing), 8):
            batch = missing[start:start + 8]
            selected = [positions[k] for k in batch]
            inputs = torch.tensor([ids[i] for i in selected], dtype=torch.long)
            mask = torch.tensor([masks[i] for i in selected], dtype=torch.long)
            hidden = model(input_ids=inputs, attention_mask=mask).last_hidden_state
            weight = mask.unsqueeze(-1).to(hidden.dtype)
            vectors = ((hidden * weight).sum(1) / weight.sum(1).clamp(min=1)).cpu().float()
            windows.update({k: v.clone() for k, v in zip(batch, vectors)})
    return torch.stack([windows[k] for k in keys]), encoded["offset_mapping"], [sum(m) for m in masks]


def selections():
    names = mc8051_core_names(DEFAULT_OUT, DEFAULT_GHDL)
    for folder in sorted(SOURCE.glob("MC8051-T*")):
        for side in ("clean", "trojan"):
            files = [folder / side / name for name in names]
            if any(not path.is_file() for path in files):
                raise FileNotFoundError(f"MC8051 core VHDL source is missing: {folder}/{side}")
            yield folder.name, side, files
    for folder in sorted(SOURCE.glob("BasicRSA-T*")):
        files = [folder / "trojan" / name for name in ("modmult.vhd", "rsacypher.vhd")]
        if any(not path.is_file() for path in files):
            raise FileNotFoundError(f"BasicRSA VHDL source is missing: {folder}")
        yield folder.name, "trojan", files


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True)
    model = AutoModel.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True).eval()
    if not tokenizer.is_fast or model.config.hidden_size != 768:
        raise ValueError("Expected fast tokenizer and 768-dimensional CodeBERT")
    cache, records, texts = {}, [], set()
    cache_dir = OUT / "file_cache"
    cache_dir.mkdir(exist_ok=True)
    windows = {}
    for benchmark, side, files in selections():
        source_text, locations = assemble(files)
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        texts.add(text_hash)
        tensors, spans = [], []
        for file in files:
            file_text, file_locations = assemble([file])
            key = hashlib.sha256((MODEL_REVISION + file_text).encode()).hexdigest()
            cached = cache_dir / f"{key}.pt"
            if key not in cache:
                if cached.exists():
                    cache[key] = cached_embed(file_text, tokenizer, model, windows,
                                              torch.load(cached, weights_only=True))
                else:
                    print(f"Encoding {file.name} ({len(file_text)} characters)", flush=True)
                    cache[key] = cached_embed(file_text, tokenizer, model, windows)
                    torch.save(cache[key], cached)
            part, offsets, token_counts = cache[key]
            tensors.append(part)
            for i in range(len(offsets)):
                spans.append({"chunk": len(spans), "token_count": token_counts[i],
                              "source_spans": line_spans(offsets[i], file_locations)})
        tensor = torch.cat(tensors, dim=0)
        if any(not chunk["source_spans"] for chunk in spans):
            raise ValueError(f"Missing VHDL source span: {benchmark}/{side}")
        target = OUT / f"{benchmark}_{side}.pt"
        torch.save(tensor, target)
        graph_status_path = DEFAULT_OUT / benchmark / side / "synthesis_status.json"
        graph_status = (json.loads(graph_status_path.read_text(encoding="utf-8"))["status"]
                        if graph_status_path.is_file() else "not_attempted")
        records.append({"benchmark": benchmark, "side": side, "label": int(side == "trojan"),
                        "source_language": "VHDL", "graph_status": graph_status,
                        "source_text_sha256": text_hash, "embedding_file": target.name,
                        "embedding_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                        "num_chunks": int(tensor.shape[0]), "embedding_dim": int(tensor.shape[1]),
                        "sources": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in files}, "chunks": spans})
        print(f"{benchmark}/{side}: {tensor.shape[0]} chunks ({graph_status})", flush=True)
    manifest = {"status": "generated_unreviewed", "model": MODEL, "model_revision": MODEL_REVISION,
                "transformers_version": version("transformers"), "source_language": "VHDL",
                "max_length": MAX_LENGTH, "stride": STRIDE, "pooling": "masked_mean_last_hidden_state",
                "window_boundary": "each source file; no cross-file windows",
                "testbenches_included": False, "samples": len(records), "unique_source_texts": len(texts),
                "records": records,
                "excluded_families": {"b15": "layout-stage mapped gate netlists, no original RTL",
                                      "s38584": "mapped gate netlists, no original RTL",
                                      "PIC16F84": "byte-identical archives already embedded in rtl_expansion_v1"}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"samples": len(records), "unique_source_texts": len(texts)}, indent=2))


if __name__ == "__main__":
    main()
