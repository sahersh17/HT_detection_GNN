"""Transparent source-size and gate-count probes before any learned model."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data/independent_benchmark_v2/manifest.json"
GRAPH_REPORT = ROOT / "data/independent_benchmark_v2/graph_lineage.json"
OUT = ROOT / "data/independent_benchmark_v2/shortcut_preflight.json"
CELL = re.compile(r"^\s*(and|or|nand|nor|not|xor|xnor|buf|sdff|sdffr)\s+\S+\s*\(", re.I | re.M)


def counts(path):
    content = path.read_text(encoding="utf-8", errors="replace")
    kinds = Counter(kind.lower() for kind in CELL.findall(content))
    return {"characters": len(content), "lines": len(content.splitlines()),
            "gate_instances": sum(kinds.values()), "xor_instances": kinds["xor"],
            "flip_flops": kinds["sdff"] + kinds["sdffr"], "gate_types": dict(kinds)}


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    graph_rows = (json.loads(GRAPH_REPORT.read_text(encoding="utf-8"))["records"]
                  if GRAPH_REPORT.exists() else [])
    graph = {row["variant"]: row for row in graph_rows}
    records = []
    for run in manifest["records"]:
        folder = ROOT / run["folder"]
        source = json.loads((folder / "summary.json").read_text(encoding="utf-8"))["netlist"]
        clean = counts(folder / (Path(source).stem + "_conv.v"))
        for variant in run["records"]:
            infected = counts(folder / variant["source_path"])
            key = f"{run['run_id']}/{variant['source_path']}"
            g = graph.get(key)
            delta = {name: infected[name] - clean[name]
                     for name in ("characters", "lines", "gate_instances", "xor_instances", "flip_flops")}
            if g:
                delta["synthesized_graph_nodes"] = g["infected_nodes"] - g["clean_nodes"]
            records.append({"host": run["host"], "mechanism": run["mechanism"],
                            "run_id": run["run_id"], "variant": variant["source_path"],
                            "clean": clean, "infected": infected, "delta": delta})
    by_host = defaultdict(list)
    for row in records:
        by_host[row["host"]].append(row)
    controls = {}
    for name in ("characters", "lines", "gate_instances", "xor_instances", "flip_flops", "synthesized_graph_nodes"):
        available = [r for r in records if name in r["delta"]]
        if not available:
            continue
        controls[name] = {"pairs": len(available),
                          "trojan_higher": sum(r["delta"][name] > 0 for r in available),
                          "ties": sum(r["delta"][name] == 0 for r in available),
                          "trojan_lower": sum(r["delta"][name] < 0 for r in available),
                          "paired_win_rate_half_ties": sum((1 if r["delta"][name] > 0 else
                                                              .5 if r["delta"][name] == 0 else 0)
                                                             for r in available) / len(available),
                          "host_win_rate": {host: sum((1 if r["delta"][name] > 0 else
                                                      .5 if r["delta"][name] == 0 else 0)
                                                     for r in rows if name in r["delta"]) /
                                            sum(name in r["delta"] for r in rows)
                                            for host, rows in by_host.items()
                                            if any(name in r["delta"] for r in rows)}}
    report = {"status": "development_transparent_preflight_no_decoys_or_model",
              "evaluation": "within-host clean/Trojan pair ranking; each score is a standalone source or graph count",
              "controls": controls, "records": records,
              "limits": ["This is gate-level Verilog, not original paired RTL",
                         "Paired rank is a diagnostic; deployment has no clean twin",
                         "No benign decoys or second generator", "Four development hosts only; two sealed hosts ungenerated"]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, result in controls.items():
        print(name, result["paired_win_rate_half_ties"], result["trojan_higher"], "/", result["pairs"])


if __name__ == "__main__":
    main()
