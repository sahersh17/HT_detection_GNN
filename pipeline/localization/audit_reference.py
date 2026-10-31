"""Audit the evidence needed for reproducible gate/RTL localization claims."""
import json
import zipfile
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402


def main():
    root = C.DATA / "localization_reference"
    rows = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    samples = json.loads(C.PAIRED_MANIFEST.read_text(encoding="utf-8"))["samples"]
    old = {r["graph_id"]: r for r in json.loads(
        (C.ROOT / "trusthub" / "features" / "manifest.json").read_text(encoding="utf-8"))}
    with zipfile.ZipFile(C.GRAPH_ZIP) as z:
        archive_names = set(z.namelist())
    count_matches = 0
    for s in samples:
        graph_id = s["graph_archive_path"].removeprefix("results/gnn/features/data/").removesuffix(".pt")
        if graph_id in old and old[graph_id]["num_nodes"] == s["num_nodes"]:
            count_matches += 1
    report = {
        "paired_benchmarks": len(rows),
        "paired_samples": len(samples),
        "families": dict(Counter(r["benchmark"].split("-")[0] for r in rows)),
        "original_rtl_pairs": sum(r["status"] != "missing_original_rtl" for r in rows),
        "rtl_diff_candidates": sum(r.get("num_changed_lines", 0) > 0 for r in rows),
        "benchmark_descriptions": sum(bool(r.get("description", {}).get("description")) for r in rows),
        "new_archive_node_metadata_files": sum("/metadata/" in n for n in archive_names),
        "old_new_matching_node_counts": count_matches,
        "gate_labels_verified": 0,
        "gate_localization_evaluation_ready": False,
        "reason": "The packaged PyG graphs have no node-name/source-location metadata; old metadata cannot be mapped to them by index.",
    }
    (root / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
