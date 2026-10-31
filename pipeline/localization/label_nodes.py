"""Turn Trojan RTL lines into per-node ground truth for a netlist graph.

Two evidence sources, reported separately so you can see what was actually covered:
  1. src   - Yosys write_json cells carry attributes.src = "file.v:12.3-14.5" (kept only if synthesis does not strip
             attributes and the cell survived techmap/abc with its provenance).
  2. name  - node/cell/wire names that contain an identifier that exists only in the Trojan (e.g. trojan_counter).

Usage: python label_nodes.py <yosys.json> <rtl_diff.json> <out.json> [--top MODULE]
Output: {"nodes": {cell_name: 0/1}, "coverage": {...}}. Check coverage before trusting any localization number.
"""
import json
import re
import sys
from pathlib import Path

SRC = re.compile(r"([^\s|:]+):(\d+)\.\d+-(\d+)\.\d+")


def src_ranges(src):
    """'a.v:12.3-14.5|b.v:7.1-7.9' -> [(basename, 12, 14), (basename, 7, 7)]"""
    return [(Path(f).name, int(a), int(b)) for f, a, b in SRC.findall(src or "")]


def overlaps(ranges, trojan_lines_by_file):
    wanted = {Path(k).name: set(v) for k, v in trojan_lines_by_file.items()}
    return any(f in wanted and any(a <= ln <= b for ln in wanted[f]) for f, a, b in ranges)


def label(yosys_json, diff, top=None):
    mods = yosys_json["modules"]
    top = top or next((n for n, m in mods.items() if m.get("attributes", {}).get("top")), None) or next(iter(mods))
    cells = mods[top]["cells"]
    idents = [i.lower() for i in diff["new_identifiers"]]
    nodes, by_src, by_name, with_src = {}, 0, 0, 0
    for name, cell in cells.items():
        ranges = src_ranges(cell.get("attributes", {}).get("src", ""))
        with_src += bool(ranges)
        hit_src = overlaps(ranges, diff["lines"])
        hit_name = any(i in name.lower() for i in idents)
        by_src += hit_src
        by_name += (hit_name and not hit_src)
        nodes[name] = int(hit_src or hit_name)
    n = len(cells)
    return {"top": top, "nodes": nodes,
            "coverage": {"cells": n, "cells_with_src": with_src, "src_coverage": with_src / n if n else 0,
                         "trojan_by_src": by_src, "trojan_by_name_only": by_name,
                         "trojan_total": sum(nodes.values())}}


def main(argv):
    top = argv[argv.index("--top") + 1] if "--top" in argv else None
    out = label(json.loads(Path(argv[0]).read_text()), json.loads(Path(argv[1]).read_text()), top)
    Path(argv[2]).write_text(json.dumps(out, indent=2))
    c = out["coverage"]
    print(c)
    if c["trojan_total"] == 0:
        print("WARNING: no Trojan nodes found. Synthesis probably stripped src attributes; "
              "resynthesize keeping them (no -noattr, flatten keeps src) or use name-based evidence.")
    elif c["src_coverage"] < 0.5:
        print("WARNING: <50% of cells carry src; ground truth is likely incomplete.")


if __name__ == "__main__":
    main(sys.argv[1:])
