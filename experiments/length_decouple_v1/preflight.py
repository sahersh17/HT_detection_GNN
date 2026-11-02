"""Preflight a two-sided, length-matched, unused-RTL padding intervention.

This pilot tests whether a transparent rule can identify the class from the
amount of padding before spending compute on another CodeBERT model. It does
not certify every possible length-control design.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
from build import source_files, yosys_script  # noqa: E402
from embed_rtl import MODEL, MODEL_REVISION, MAX_LENGTH, STRIDE, assemble  # noqa: E402

OUT = ROOT / "runs/length_decouple_v1"
YOSYS = ROOT / "trusthub/venv/Scripts/yowasp-yosys.exe"
BENCHMARKS = ("AES-T100", "RS232-T2100")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts(files, tokenizer):
    text, _ = assemble(files)
    chunks = len(tokenizer(text, truncation=True, max_length=MAX_LENGTH, stride=STRIDE,
                           return_overflowing_tokens=True)["input_ids"])
    return {"chars": len(text), "lines": sum(len(p.read_text(encoding="utf-8", errors="replace").splitlines())
                                             for p in files), "chunks": chunks}


def module_text(lines, extra_terms=0, trailing_spaces=0):
    # One unused module on both sides. Its wires are syntactically valid but
    # cannot affect the selected top because this module is not instantiated.
    body = ["module audit_padding(input [7:0] x, output [7:0] y);"]
    for i in range(lines):
        src = "x" if i == 0 else f"w{i-1}"
        extra = " ^ 8'h5a" * (extra_terms // lines + int(i < extra_terms % lines))
        body.append(f"wire [7:0] w{i}; assign w{i} = {src} ^ 8'h3c{extra};")
    body.append(f"assign y = w{lines-1};")
    body.append("endmodule" + " " * trailing_spaces)
    return "\n".join(body) + "\n"


def render(path, lines, terms=0, spaces=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(module_text(lines, terms, spaces), encoding="utf-8", newline="\n")


def top_inventory(path, top):
    document = json.loads(path.read_text(encoding="utf-8"))
    if set(document["modules"]) != {top}:
        raise ValueError(f"Unused padding module survived hierarchy: {path}")
    module = document["modules"][top]
    # Auto cell names and numeric net IDs shift when the extra source is read.
    # This inventory is a preflight check, not an equivalence proof.
    return {"ports": {name: (port["direction"], len(port["bits"]))
                      for name, port in module["ports"].items()},
            "cell_types": dict(Counter(cell["type"] for cell in module["cells"].values()))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark", action="append", choices=BENCHMARKS)
    args = ap.parse_args()
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True)
    records = []
    for benchmark in args.benchmark or BENCHMARKS:
        sides = {}
        for side in ("clean", "trojan"):
            files, top = source_files(benchmark, side)
            sides[side] = {"files": files, "top": top, "original": counts(files, tokenizer)}
        target_lines = max(sides[s]["original"]["lines"] for s in sides) + 40
        for side in sides:
            row = sides[side]
            row["pad"] = OUT / benchmark / side / "audit_padding.v"
            row["pad_lines"] = target_lines - row["original"]["lines"] - 3
            if row["pad_lines"] < 1:
                raise ValueError("No room for padding module")
            render(row["pad"], row["pad_lines"])
        # Increase CodeBERT windows on the lower side, while preserving its
        # line count; never use these artifacts for a claimed semantic gain.
        for _ in range(40):
            current = {s: counts([*r["files"], r["pad"]], tokenizer)["chunks"] for s, r in sides.items()}
            if current["clean"] == current["trojan"]:
                break
            smaller = min(current, key=current.get)
            row = sides[smaller]
            row["extra_terms"] = row.get("extra_terms", 0) + max(1, row["pad_lines"] // 2)
            render(row["pad"], row["pad_lines"], row["extra_terms"])
        before_spaces = {s: counts([*r["files"], r["pad"]], tokenizer) for s, r in sides.items()}
        target_chars = max(r["chars"] for r in before_spaces.values()) + 256
        for side, row in sides.items():
            row["spaces"] = target_chars - before_spaces[side]["chars"]
            render(row["pad"], row["pad_lines"], row.get("extra_terms", 0), row["spaces"])
            row["final"] = counts([*row["files"], row["pad"]], tokenizer)
            row["pad_bytes"] = row["pad"].stat().st_size
            json_path = OUT / benchmark / side / "yosys.json"
            script = yosys_script([*row["files"], row["pad"]], row["top"], json_path)
            completed = subprocess.run([str(YOSYS), "-Q", "-T", "-q", "-p", script],
                                       cwd=ROOT, capture_output=True, text=True, timeout=300)
            if completed.returncode:
                raise RuntimeError(f"Yosys failed {benchmark}/{side}: {(completed.stderr + completed.stdout)[-1000:]}")
            original_json = ROOT / "runs/provenance_v1" / benchmark / side / "yosys.json"
            row["top_inventory_unchanged"] = top_inventory(json_path, row["top"]) == top_inventory(original_json, row["top"])
            records.append({"benchmark": benchmark, "side": side, "original": row["original"],
                            "final": row["final"], "padding_assignment_lines": row["pad_lines"],
                            "padding_extra_xor_terms": row.get("extra_terms", 0),
                            "padding_bytes": row["pad_bytes"],
                            "padding_sha256": sha256(row["pad"]),
                            "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in row["files"]},
                            "yosys_json_sha256": sha256(json_path),
                            "top_inventory_unchanged": row["top_inventory_unchanged"]})
            print(benchmark, side, row["original"], row["final"], flush=True)
    by_pair = {b: {r["side"]: r for r in records if r["benchmark"] == b}
               for b in sorted({r["benchmark"] for r in records})}
    matched = {b: (v["clean"]["final"] == v["trojan"]["final"]) for b, v in by_pair.items()}
    report = {"status": "preflight_not_a_valid_length_decoupling_result",
              "model_revision": MODEL_REVISION, "benchmark_pairs": len(by_pair), "records": records,
              "all_chars_lines_chunks_matched": all(matched.values()), "matched_by_pair": matched,
              "top_inventory_unchanged_sides": sum(r["top_inventory_unchanged"] for r in records),
              "transparent_rule": "more padding assignment lines implies clean",
              "rule_correct_pairs": sum(v["clean"]["padding_assignment_lines"] > v["trojan"]["padding_assignment_lines"]
                                        for v in by_pair.values()),
              "limits": ["Uninstantiated modules are removed by synthesis; only top port/cell inventory equality checked",
                         "No RTL detector trained because padding amount is a label shortcut"]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "preflight.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    evidence = ROOT / "data/length_decouple_v1"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "preflight.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("matched", matched, "padding shortcut", report["rule_correct_pairs"], "/", len(by_pair))


if __name__ == "__main__":
    main()
