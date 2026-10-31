"""Embed only synthesized RTL and save CodeBERT chunk-to-source-line spans.

Usage: python pipeline/provenance/embed_rtl.py [--benchmark RS232-T2100]
The model is loaded from the local Hugging Face cache; no testbenches, file
names, benchmark IDs, or class labels are inserted into model input text.
"""
import argparse
import hashlib
import json
import os
from importlib.metadata import version
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

from build import ROOT, source_files

MODEL = "microsoft/codebert-base"
MODEL_REVISION = "3b0952feddeffad0063f274080e3c23d75e7eb39"
MAX_LENGTH = 512
STRIDE = 50
BATCH_SIZE = 8


def assemble(files):
    pieces, locations, cursor = [], [], 0
    for path in files:
        content = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        if pieces:
            pieces.append("\n\n")
            cursor += 2
        start = cursor
        pieces.append(content)
        cursor += len(content)
        locations.append({"file": path.relative_to(ROOT).as_posix(), "start": start, "end": cursor,
                          "content": content})
    return "".join(pieces), locations


def line_spans(offsets, locations):
    real = [(int(a), int(b)) for a, b in offsets if int(b) > int(a)]
    if not real:
        return []
    first, last = min(a for a, _ in real), max(b for _, b in real)
    result = []
    for source in locations:
        a, b = max(first, source["start"]), min(last, source["end"])
        if b <= a:
            continue
        local_a, local_b = a - source["start"], b - source["start"]
        content = source["content"]
        result.append({"file": source["file"], "start_line": content.count("\n", 0, local_a) + 1,
                       "end_line": content.count("\n", 0, max(local_a, local_b - 1)) + 1})
    return result


def embed(text, tokenizer, model):
    encoded = tokenizer(text, truncation=True, max_length=MAX_LENGTH, stride=STRIDE,
                        return_overflowing_tokens=True, padding="max_length",
                        return_attention_mask=True, return_offsets_mapping=True)
    ids, masks, offsets = encoded["input_ids"], encoded["attention_mask"], encoded["offset_mapping"]
    chunks = []
    with torch.inference_mode():
        for start in range(0, len(ids), BATCH_SIZE):
            input_ids = torch.tensor(ids[start:start + BATCH_SIZE], dtype=torch.long)
            mask = torch.tensor(masks[start:start + BATCH_SIZE], dtype=torch.long)
            hidden = model(input_ids=input_ids, attention_mask=mask).last_hidden_state
            weight = mask.unsqueeze(-1).to(hidden.dtype)
            chunks.append(((hidden * weight).sum(dim=1) / weight.sum(dim=1).clamp(min=1)).cpu().float())
    if not chunks:
        raise ValueError("Tokenizer produced no chunks")
    return torch.cat(chunks, dim=0).contiguous(), offsets, [int(sum(mask)) for mask in masks]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", action="append", help="Limit to one or more paired benchmarks for a smoke run")
    parser.add_argument("--expansion-only", action="store_true", help="Embed the five reserved memctrl/PIC pairs")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True)
    model = AutoModel.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True).eval()
    if not tokenizer.is_fast or model.config.hidden_size != 768:
        raise ValueError("Expected fast tokenizer and 768-dimensional CodeBERT")
    if args.expansion_only:
        benchmarks = ["memctrl-T100", *(f"PIC16F84-T{n}" for n in (100, 200, 300, 400))]
        samples = [{"benchmark": benchmark, "class_name": side, "label": int(side == "trojan")}
                   for benchmark in benchmarks for side in ("clean", "trojan")]
    else:
        samples = json.loads((ROOT / "data" / "integrated" / "paired_manifest.json").read_text(encoding="utf-8"))["samples"]
    if args.benchmark:
        samples = [s for s in samples if s["benchmark"] in set(args.benchmark)]
    if not samples:
        parser.error("No paired samples selected")
    out = (args.out or ROOT / "runs" / ("rtl_expansion_v1" if args.expansion_only else "rtl_clean_v1")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache, records = {}, []
    for sample in samples:
        benchmark, side = sample["benchmark"], sample["class_name"]
        files, _ = source_files(benchmark, side)
        source_text, locations = assemble(files)
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        if text_hash not in cache:
            cache[text_hash] = embed(source_text, tokenizer, model)
        tensor, offsets, token_counts = cache[text_hash]
        spans = [{"chunk": i, "token_count": token_counts[i], "source_spans": line_spans(offsets[i], locations)}
                 for i in range(len(offsets))]
        if any(not chunk["source_spans"] for chunk in spans):
            raise ValueError(f"At least one chunk lacks a source-line span: {benchmark}/{side}")
        target = out / f"{benchmark}_{side}.pt"
        torch.save(tensor, target)
        record = {"benchmark": benchmark, "side": side, "label": sample["label"],
                  "source_text_sha256": text_hash, "embedding_file": target.name,
                  "embedding_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                  "num_chunks": int(tensor.shape[0]), "embedding_dim": int(tensor.shape[1]),
                  "sources": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  "chunks": spans}
        records.append(record)
        print(f"{benchmark}/{side}: {tensor.shape[0]} chunks", flush=True)
    manifest = {"status": "generated_unreviewed", "model": MODEL, "model_revision": MODEL_REVISION,
                "transformers_version": version("transformers"),
                "max_length": MAX_LENGTH, "stride": STRIDE, "pooling": "masked_mean_last_hidden_state",
                "testbenches_included": False, "samples": len(records), "unique_source_texts": len(cache), "records": records}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"samples": len(records), "unique_source_texts": len(cache)}, indent=2))


if __name__ == "__main__":
    main()
