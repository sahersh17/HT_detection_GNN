"""Map earlier graph gates to RTL-diff lines through Yosys wire attributes.

Produces unreviewed candidates only. The mapping is partial and belongs to
trusthub/features, never to the newer 2026-10-31 archive.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402
from label_nodes import overlaps, src_ranges  # noqa: E402

SRC = re.compile(r'^\s*\(\* src = "(.*?)" \*\)')
WIRE = re.compile(r'^\s*wire(?:\s+\[[^]]+\])?\s+(.+?)\s*;')
OUTPUT_PORTS = {"Y", "Q", "QN", "Z", "ZN", "OUT", "O"}
OUT = C.DATA / "localization_reference" / "legacy_gate_candidates"


def base_signal(signal):
    return re.sub(r"\s+\[\d+\]$", "", signal.strip().lstrip("\\"))


def wire_sources(netlist):
    """Collect Yosys `src` on wire declarations, keyed by wire name."""
    result = {}
    source = None
    for line in Path(netlist).read_text(encoding="utf-8", errors="replace").splitlines():
        attr = SRC.match(line)
        if attr:
            source = attr.group(1).replace("\\\\", "\\")
            continue
        wire = WIRE.match(line)
        if wire:
            if source:
                result[base_signal(wire.group(1))] = source
            source = None
        elif not line.lstrip().startswith("(*"):
            source = None
    return result


def build(reference):
    benchmark = reference["benchmark"]
    family = benchmark.split("-")[0]
    side = "trojan" if family == "AES" else "tjin"
    netlist = C.ROOT / "trusthub" / "netlists" / family / benchmark / f"{side}_netlist.v"
    meta_file = C.ROOT / "trusthub" / "features" / "metadata" / family / benchmark / f"{side}_netlist.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    sources = wire_sources(netlist)
    labels, source_ranges = [], []
    for ports in meta["node_ports"]:
        output_signals = [base_signal(value) for port, value in ports.items() if port.upper() in OUTPUT_PORTS]
        ranges = [r for signal in output_signals for r in src_ranges(sources.get(signal, ""))]
        source_ranges.append(ranges)
        labels.append(int(overlaps(ranges, reference["changed_lines"])) if ranges else -1)
    return {
        "graph_id": meta["graph_id"], "node_names": meta["node_names"],
        "labels": labels, "source_ranges": source_ranges,
        "reviewed": False,
        "source": "Yosys output-wire src attributes intersecting unreviewed RTL diff",
        "version": "earlier trusthub/features graph; NOT 2026-10-31 archive",
        "coverage": {"nodes": len(labels), "known": sum(v >= 0 for v in labels),
                     "candidate_trojan": sum(v == 1 for v in labels),
                     "unknown": sum(v == -1 for v in labels)},
    }


def main():
    refs = json.loads((C.DATA / "localization_reference" / "manifest.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    for ref in refs:
        row = build(ref)
        path = OUT / f"{ref['benchmark']}.json"
        path.write_text(json.dumps(row, indent=2), encoding="utf-8")
        summaries.append({"benchmark": ref["benchmark"], **row["coverage"]})
        print(ref["benchmark"], row["coverage"])
    (OUT / "summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
