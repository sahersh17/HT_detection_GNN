"""Build an auditable RTL change and benchmark-description reference set.

These are candidate RTL change labels, not validated gate labels. The source
package must be inspected before using them as scoring ground truth.
"""
import json
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402
from rtl_diff import design_files, new_identifiers, trojan_lines  # noqa: E402


SOURCE = C.ROOT / "trusthub" / "AES_unzipped"
OUT = C.DATA / "localization_reference"


def description(base):
    for name in ("Readme.txt", "README.txt", "README.md"):
        path = base / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            start = text.lower().find("trojan description")
            if start < 0:
                return {"path": path.relative_to(C.ROOT).as_posix(),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "description": None}
            tail = text[start + len("trojan description"):]
            end = tail.lower().find("trojan taxonomy")
            return {"path": path.relative_to(C.ROOT).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "description": (tail[:end] if end >= 0 else tail).strip() or None}
    return {"path": None, "description": None}


def build(benchmark):
    base = SOURCE / benchmark / benchmark
    clean, trojan = base / "src" / "TjFree", base / "src" / "TjIn"
    if not clean.is_dir() or not trojan.is_dir():
        return {"benchmark": benchmark, "status": "missing_original_rtl"}
    clean_files, trojan_files = design_files(clean), design_files(trojan)
    lines, texts = trojan_lines(clean, trojan)
    identifiers = new_identifiers(clean, trojan, texts)
    return {
        "benchmark": benchmark,
        "status": "candidate_rtl_diff_requires_review" if lines else "no_rtl_change_found",
        "clean_source": clean.relative_to(C.ROOT).as_posix(),
        "trojan_source": trojan.relative_to(C.ROOT).as_posix(),
        "clean_files": sorted(clean_files), "trojan_files": sorted(trojan_files),
        "clean_sha256": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in clean_files.items()},
        "trojan_sha256": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in trojan_files.items()},
        "changed_lines": lines,
        "changed_line_text": texts,
        "new_identifiers": identifiers,
        "description": description(base),
        "num_changed_lines": sum(map(len, lines.values())),
        "num_changed_files": len(lines),
        "gate_ground_truth": "unavailable: new graph package has no node-name/source mapping",
    }


def main():
    samples = json.loads(C.PAIRED_MANIFEST.read_text(encoding="utf-8"))["samples"]
    benchmarks = sorted({s["benchmark"] for s in samples})
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [build(b) for b in benchmarks]
    (OUT / "manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"benchmarks={len(rows)} original_RTL={sum(r['status'] != 'missing_original_rtl' for r in rows)} "
          f"with_changes={sum(r.get('num_changed_lines', 0) > 0 for r in rows)} "
          f"with_description={sum(bool(r.get('description', {}).get('description')) for r in rows)}")
    for row in rows:
        print(row["benchmark"], row["status"], row.get("num_changed_lines", 0),
              bool(row.get("description", {}).get("description")))


if __name__ == "__main__":
    main()
