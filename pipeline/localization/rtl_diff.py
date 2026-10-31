"""Find the Trojan's RTL lines by diffing a Trojan design against its paired clean design (Trust-HUB folders).

Usage: python rtl_diff.py <clean_dir> <trojan_dir> [out.json]
Output: {"lines": {file: [line numbers in the Trojan file]}, "new_identifiers": [...]}
Comment-only and whitespace-only changes are ignored. Testbenches are skipped.
"""
import difflib
import json
import re
import sys
from pathlib import Path

EXTS = {".v", ".sv", ".vh", ".svh"}
KEYWORDS = set("""module endmodule input output inout wire reg integer parameter localparam assign always initial begin end
if else case casez casex endcase default for while posedge negedge or and not xor nand nor xnor function endfunction
task endtask generate endgenerate genvar signed""".split())
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")


def is_testbench(p):
    n = p.name.lower()
    return n.startswith("test") or n.startswith("tb") or "_tb." in n or "testbench" in n


def design_files(root):
    return {p.relative_to(root).as_posix(): p
            for p in sorted(Path(root).rglob("*")) if p.is_file() and p.suffix.lower() in EXTS and not is_testbench(p)}


def normalize(line):
    line = re.sub(r"//.*", "", line)
    return re.sub(r"\s+", " ", line).strip()


def _read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def trojan_lines(clean_dir, trojan_dir):
    """Return ({file: sorted 1-based Trojan-side line numbers}, {file: [line text]})."""
    clean, troj = design_files(clean_dir), design_files(trojan_dir)
    by_name = {Path(k).name: v for k, v in clean.items()}
    lines, texts = {}, {}
    for rel, path in troj.items():
        t = _read(path)
        c = _read(by_name[Path(rel).name]) if Path(rel).name in by_name else []
        t_norm, c_norm = [normalize(x) for x in t], [normalize(x) for x in c]
        hits = set()
        for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, c_norm, t_norm, autojunk=False).get_opcodes():
            if tag in ("insert", "replace"):
                hits.update(j for j in range(j1, j2) if t_norm[j])
        if hits:
            lines[rel] = [j + 1 for j in sorted(hits)]
            texts[rel] = [t[j] for j in sorted(hits)]
    return lines, texts


def identifiers(text_lines):
    return {m for ln in text_lines for m in TOKEN.findall(re.sub(r"//.*", "", ln)) if m not in KEYWORDS}


def new_identifiers(clean_dir, trojan_dir, texts):
    """Identifiers that appear in Trojan-diff lines but nowhere in the clean source (e.g. trojan_counter)."""
    seen = set()
    for p in design_files(clean_dir).values():
        seen |= identifiers(_read(p))
    added = set()
    for t in texts.values():
        added |= identifiers(t)
    return sorted(added - seen)


def main(argv):
    clean_dir, trojan_dir = argv[0], argv[1]
    lines, texts = trojan_lines(clean_dir, trojan_dir)
    result = {"lines": lines, "new_identifiers": new_identifiers(clean_dir, trojan_dir, texts)}
    print(f"files changed: {len(lines)}  Trojan lines: {sum(map(len, lines.values()))}  "
          f"new identifiers: {len(result['new_identifiers'])}")
    if len(argv) > 2:
        Path(argv[2]).write_text(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
