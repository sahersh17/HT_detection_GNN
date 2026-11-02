"""Verify both versioned expanded LOFO manifests without loading graph tensors."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(name, expected_graphs, expected_hosts):
    manifest = json.loads((ROOT / f"data/{name}/protocol.json").read_text(encoding="utf-8"))
    records = manifest["samples"]
    if len(records) != expected_graphs or len({r["family"] for r in records}) != expected_hosts:
        raise ValueError(f"Unexpected cohort size: {name}")
    sides = Counter((r["benchmark"], r["side"]) for r in records)
    if any(value != 1 for value in sides.values()):
        raise ValueError(f"Duplicate sample: {name}")
    for record in records:
        path = ROOT / record["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Graph hash mismatch: {path}")
        meta = json.loads(path.with_name("metadata.json").read_text(encoding="utf-8"))
        if meta["label"] != record["label"] or meta["benchmark"] != record["benchmark"]:
            raise ValueError(f"Metadata mismatch: {path}")
        for source, digest in meta["sources"].items():
            if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Source hash mismatch: {source}")
        opposite = "trojan" if record["side"] == "clean" else "clean"
        if (record["benchmark"], opposite) not in sides:
            raise ValueError(f"Unpaired graph: {path}")
    return {"cohort": name, "graphs": len(records), "pairs": len(records)//2, "hosts": expected_hosts,
            "status": "hash_and_pair_verified"}


def main():
    result = [verify("lofo_expanded", 94, 10), verify("lofo_expanded_b19", 100, 11)]
    target = ROOT / "data/lofo_expanded_b19/verification.json"
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
