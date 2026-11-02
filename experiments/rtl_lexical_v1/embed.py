"""Embed versioned RTL controls with the same pinned CodeBERT encoder as the baseline."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
from embed_rtl import MODEL, MODEL_REVISION, assemble, embed  # noqa: E402

OUT = ROOT / "runs/rtl_lexical_v1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", action="append", choices=["comments", "names", "both"])
    ap.add_argument("--benchmark", action="append")
    args = ap.parse_args()
    preparation = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    if preparation["status"] != "generated_unverified":
        raise ValueError("Unexpected preparation manifest")
    records = [r for r in preparation["records"]
               if (not args.arm or r["arm"] in args.arm)
               and (not args.benchmark or r["benchmark"] in args.benchmark)]
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True)
    model = AutoModel.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True).eval()
    if not tokenizer.is_fast or model.config.hidden_size != 768:
        raise ValueError("CodeBERT encoder mismatch")
    cache_dir = OUT / "embedding_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for r in records:
        files = [ROOT / x["transformed"] for x in r["files"]]
        for path, entry in zip(files, r["files"]):
            if digest(path.read_text(encoding="utf-8").encode("utf-8")) != entry["transformed_sha256"]:
                raise ValueError(f"Source changed: {path}")
        content, _ = assemble(files)
        input_hash = digest(content.encode("utf-8"))
        cached = cache_dir / f"{input_hash}.pt"
        if not cached.exists():
            tensor, _, _ = embed(content, tokenizer, model)
            torch.save(tensor, cached)
        else:
            tensor = torch.load(cached, map_location="cpu", weights_only=True)
        target = OUT / "embeddings" / r["arm"] / f"{r['benchmark']}_{r['side']}.pt"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or digest(target.read_bytes()) != digest(cached.read_bytes()):
            target.write_bytes(cached.read_bytes())
        item = {"benchmark": r["benchmark"], "side": r["side"], "arm": r["arm"],
                "input_sha256": input_hash, "embedding": target.relative_to(ROOT).as_posix(),
                "embedding_sha256": digest(target.read_bytes()), "chunks": int(tensor.shape[0])}
        results.append(item)
        # Checkpoint each record so an interrupted CPU run remains auditable.
        (OUT / "embedding_progress.json").write_text(json.dumps({"model": MODEL,
            "model_revision": MODEL_REVISION, "records": results}, indent=2), encoding="utf-8")
        print(f"{r['arm']} {r['benchmark']}/{r['side']}: {tensor.shape[0]} chunks", flush=True)
    print(f"Embedded {len(results)} records", flush=True)


if __name__ == "__main__":
    main()
