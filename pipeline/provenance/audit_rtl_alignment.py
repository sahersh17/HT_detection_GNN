"""Check whether packaged CodeBERT RTL text matches the newly synthesized RTL.

Run before interpreting a fusion experiment. Extra testbench sections are reported
because they are not part of the synthesized hardware design.
"""
import json
import re
import zipfile
from pathlib import Path

from build import ROOT, source_files

MARKER = re.compile(r"(?m)^// ===== FILE: (.*?) =====\r?$")


def sections(text):
    markers = list(MARKER.finditer(text))
    result = {}
    for i, match in enumerate(markers):
        name = match.group(1)
        if name in result:
            raise ValueError(f"Duplicate section: {name}")
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        result[name] = text[match.end():end].replace("\r\n", "\n").strip()
    return result


def main():
    samples = json.loads((ROOT / "data" / "integrated" / "paired_manifest.json").read_text(encoding="utf-8"))["samples"]
    references = {row["benchmark"]: row for row in json.loads((ROOT / "data" / "localization_reference" / "manifest.json").read_text(encoding="utf-8"))}
    rows = []
    with zipfile.ZipFile(ROOT / "data" / "HT_data_2026-10-31_b40cc08.zip") as archive:
        for sample in samples:
            benchmark, side = sample["benchmark"], sample["class_name"]
            archive_path = f"results/llm/rtl/{benchmark}_{side}_rtl.v"
            packed = sections(archive.read(archive_path).decode("utf-8", errors="replace"))
            synth_files, _ = source_files(benchmark, side)
            original = ROOT / references[benchmark]["clean_source" if side == "clean" else "trojan_source"]
            synth_names = {p.name for p in synth_files}
            original_files = {p.name: p for p in original.glob("*.v")}
            normalized = lambda p: p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").strip()
            row = {"benchmark": benchmark, "side": side, "packaged_sections": len(packed),
                   "synthesized_files": len(synth_files),
                   "missing_synthesized_sections": sorted(synth_names - packed.keys()),
                   "changed_vs_synthesized": sorted(p.name for p in synth_files if p.name in packed and packed[p.name] != normalized(p)),
                   "changed_vs_original": sorted(name for name, p in original_files.items() if name in packed and packed[name] != normalized(p)),
                   "extra_packaged_sections": sorted(packed.keys() - synth_names),
                   "includes_testbench": any(name.lower().startswith(("test", "tb")) for name in packed)}
            rows.append(row)
    summary = {"samples": len(rows),
               "samples_with_missing_synthesized_files": sum(bool(r["missing_synthesized_sections"]) for r in rows),
               "samples_with_changed_synthesized_files": sum(bool(r["changed_vs_synthesized"]) for r in rows),
               "samples_with_changed_original_files": sum(bool(r["changed_vs_original"]) for r in rows),
               "samples_embedding_testbenches": sum(r["includes_testbench"] for r in rows),
               "rows": rows}
    output = ROOT / "runs" / "provenance_v1" / "rtl_alignment.json"
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
