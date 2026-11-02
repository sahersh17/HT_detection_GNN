"""Join paired graph and RTL manifests without treating variants as new hosts."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/audit_v1"
GRAPH = ROOT / "data/lofo_expanded_b19/protocol.json"
RTL = {
    "Verilog_early": ROOT / "runs/rtl_clean_v1/manifest.json",
    "Verilog_expansion": ROOT / "runs/rtl_expansion_v1/manifest.json",
    "VHDL_MC8051": ROOT / "runs/new_rtl_v1/manifest.json",
    "VHDL_b19": ROOT / "runs/b19_rtl_v1/manifest.json",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    by_family = defaultdict(lambda: defaultdict(set))
    by_benchmark = defaultdict(dict)
    for row in graph["samples"]:
        by_family[row["family"]][row["benchmark"]].add(row["side"])
        by_benchmark[row["benchmark"]][row["side"]] = row
    rtl = defaultdict(dict)
    manifest_hashes = {"graph": sha256(GRAPH)}
    for source, path in RTL.items():
        if not path.is_file():
            continue
        manifest_hashes[source] = sha256(path)
        for row in json.loads(path.read_text(encoding="utf-8"))["records"]:
            key = (row["benchmark"], row["side"])
            if key in rtl:
                raise ValueError(f"RTL sample duplicated across versions: {key}")
            rtl[key] = {"source_text_sha256": row["source_text_sha256"],
                        "embedding_sha256": row["embedding_sha256"],
                        "num_chunks": row["num_chunks"], "rtl_version": source}
    families = []
    for family, benchmarks in sorted(by_family.items()):
        paired = sorted(b for b, sides in benchmarks.items() if sides == {"clean", "trojan"})
        complete = [b for b in paired if (b, "clean") in rtl and (b, "trojan") in rtl]
        clean_hashes = {rtl[(b, "clean")]["source_text_sha256"] for b in complete}
        graph_versions = sorted({by_benchmark[b][side]["path"].split("/")[1]
                                 for b in paired for side in ("clean", "trojan")})
        rtl_versions = sorted({rtl[(b, side)]["rtl_version"] for b in complete
                               for side in ("clean", "trojan")})
        families.append({"family": family, "paired_variants": len(paired),
                         "paired_graphs": len(paired) * 2, "paired_with_rtl": len(complete),
                         "independent_clean_rtl_sources": len(clean_hashes),
                         "graph_versions": graph_versions, "rtl_versions": rtl_versions,
                         "rtl_complete_benchmarks": complete,
                         "not_rtl_complete": sorted(set(paired) - set(complete))})
    result = {"status": "inspected_development_hosts", "graph_protocol": GRAPH.relative_to(ROOT).as_posix(),
              "input_manifest_sha256": manifest_hashes,
              "paired_graph_host_families": len(families),
              "paired_graph_and_rtl_host_families": sum(r["paired_with_rtl"] > 0 for r in families),
              "independent_clean_rtl_sources": sum(r["independent_clean_rtl_sources"] for r in families),
              "limitations": ["All listed Trust-Hub hosts have already been inspected",
                              "RTL modalities mix Verilog and VHDL and different window boundaries",
                              "Graph modalities mix synthesis and mapped-netlist domains",
                              "No reviewed real Trojan gate labels"],
              "families": families}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "host_inventory.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for row in families:
        print(row["family"], row["paired_variants"], row["paired_with_rtl"],
              row["independent_clean_rtl_sources"])
    print("RTL-capable hosts", result["paired_graph_and_rtl_host_families"])


if __name__ == "__main__":
    main()
