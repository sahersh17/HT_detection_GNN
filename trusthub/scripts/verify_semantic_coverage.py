"""
Cross-checks the structural feature manifest (from 05_feature_extractor.py)
against the semantic RTL embeddings produced in 06_llm_semantic_features.ipynb,
to find any benchmark/variant that's missing a semantic embedding.

Run this wherever both exist together on disk — most likely in the Colab
environment / cloned repo, since that's where trusthub/features/data/<family>/
was written to by the notebook. Adjust FEATURES_ROOT below if needed.

Usage:
    python verify_semantic_coverage.py
"""

import json
import re
from pathlib import Path

# ==========================================================
# CONFIG — adjust to wherever the repo is checked out
# ==========================================================
# Anchored to this script's location (trusthub/scripts/) rather than the
# current working directory, so it works no matter where you run it from.
FEATURES_ROOT = Path(__file__).resolve().parent.parent / "features"   # contains manifest.json, data/AES, data/RS232
MANIFEST_PATH = FEATURES_ROOT / "manifest.json"
FAMILIES = ["AES", "RS232"]

STATUS_TAGS = {
    "clean": ["tjfree"],
    "trojan": ["tjin", "tnin"],
}


def infer_family(graph_id: str):
    for fam in FAMILIES:
        if graph_id.upper().startswith(fam):
            return fam
    return None


def infer_benchmark(graph_id: str, family: str):
    """
    graph_id looks like '<family>/<benchmark>/<...>' — pull out the
    benchmark folder name (e.g. 'AES-T1400').
    """
    parts = graph_id.split("/")
    for p in parts:
        if p.upper().startswith(family) and "-" in p:
            return p
    # fallback: second path component
    return parts[1] if len(parts) > 1 else parts[0]


def infer_status(graph_id: str, label) -> str:
    gid_lower = graph_id.lower()
    for status, tags in STATUS_TAGS.items():
        if any(tag in gid_lower for tag in tags):
            return status
    # fallback to the label field if tags aren't in the path
    if label in (0, "0", "clean", False):
        return "clean"
    if label in (1, "1", "trojan", True):
        return "trojan"
    return "unknown"


def main():
    if not MANIFEST_PATH.exists():
        print(f"Manifest not found at {MANIFEST_PATH.resolve()}")
        print("Update FEATURES_ROOT at the top of this script and re-run.")
        return

    manifest = json.loads(MANIFEST_PATH.read_text())
    print(f"Loaded {len(manifest)} structural graph entries from manifest.json\n")

    # Build the set of (family, benchmark, status) we STRUCTURALLY have
    expected = {}
    unparsed = []
    unknown_status = []
    for entry in manifest:
        gid = entry["graph_id"]
        family = infer_family(gid)
        if family is None:
            unparsed.append(gid)
            continue
        benchmark = infer_benchmark(gid, family)
        status = infer_status(gid, entry.get("label"))
        if status == "unknown":
            unknown_status.append((gid, entry.get("label")))
        expected.setdefault(family, {}).setdefault(benchmark, set()).add(status)

    if unknown_status:
        print(f"Could not determine clean/trojan status for {len(unknown_status)} graph(s):")
        for gid, label in unknown_status:
            print(f"   {gid}  (label={label!r})")
        print()

    if unparsed:
        print(f"Could not classify {len(unparsed)} graph_ids into a known family:")
        for g in unparsed[:10]:
            print(f"   {g}")
        print()

    # Now check what semantic embeddings actually exist on disk
    missing = []
    found = 0
    total_expected = 0

    for family, benchmarks in sorted(expected.items()):
        fam_dir = FEATURES_ROOT / "data" / family
        for benchmark, statuses in sorted(benchmarks.items()):
            bench_dir = fam_dir / benchmark
            for status in statuses:
                if status == "unknown":
                    continue
                total_expected += 1
                emb_path = bench_dir / f"{status}_rtl_embedding.pt"
                if emb_path.exists():
                    found += 1
                else:
                    missing.append((family, benchmark, status, str(emb_path)))

    print("=" * 70)
    print(f"Expected semantic embeddings : {total_expected}")
    print(f"Found                        : {found}")
    print(f"Missing                      : {len(missing)}")
    print("=" * 70)

    if missing:
        print("\nMissing embeddings:")
        for family, benchmark, status, path in missing:
            print(f"  [{family}] {benchmark} ({status}) -> expected at {path}")
    else:
        print("\nAll structurally-featured graphs have a matching semantic embedding.")

    # Bonus: flag any benchmark folders that HAVE embeddings but never showed
    # up in the structural manifest at all (orphaned on the semantic side)
    print("\nChecking for embeddings with no structural counterpart...")
    orphans = []
    for family in FAMILIES:
        fam_dir = FEATURES_ROOT / "data" / family
        if not fam_dir.exists():
            continue
        for bench_dir in sorted(fam_dir.iterdir()):
            if not bench_dir.is_dir():
                continue
            benchmark = bench_dir.name
            known_statuses = expected.get(family, {}).get(benchmark, set())
            for emb_file in bench_dir.glob("*_rtl_embedding.pt"):
                status = emb_file.stem.replace("_rtl_embedding", "")
                if status not in known_statuses:
                    orphans.append((family, benchmark, status, str(emb_file)))

    if orphans:
        for family, benchmark, status, path in orphans:
            print(f"  [{family}] {benchmark} ({status}) has embedding but no structural entry: {path}")
    else:
        print("  None found.")


if __name__ == "__main__":
    main()