"""Apply the frozen v2 intake gates without training a detector."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "data/independent_benchmark_v2"


def read(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = read("manifest.json")
    lineage = read("graph_lineage.json")["records"]
    verified = read("graph_verification.json")
    formal = {r["variant"]: r for r in read("formal_combinational.json")["records"]}
    traces = {f"{r['run_id']}/{r['source_path']}": r for r in read("sequential_trace.json")["records"]}
    shortcuts = read("shortcut_preflight.json")["controls"]
    protocol = json.loads((ROOT / "experiments/independent_benchmark_v2/protocol.json").read_text(encoding="utf-8"))
    if manifest["protocol_sha256"] != sha256(ROOT / "experiments/independent_benchmark_v2/protocol.json"):
        raise ValueError("Manifest/protocol hash mismatch")
    variants = {f"{r['run_id']}/{v['source_path']}" for r in manifest["records"] for v in r["records"]}
    if len(variants) != 16 or len(lineage) != 16 or verified["variants"] != 16:
        raise ValueError("Incomplete v2 development intake")
    if {r["variant"] for r in lineage} != variants:
        raise ValueError("Lineage/manifest variant mismatch")
    if any(r["host"] in protocol["host_split"]["sealed_final_candidate"] for r in manifest["records"]):
        raise ValueError("Sealed candidate used in development")
    for host in protocol["host_split"]["sealed_final_candidate"]:
        if list((ROOT / "runs/independent_benchmark_v2/runs").glob(host + "_*")):
            raise ValueError(f"Sealed candidate has generated output: {host}")
    rows = []
    for run in manifest["records"]:
        folder = ROOT / run["folder"]
        repeat = ROOT / "runs/independent_benchmark_v2/repeat" / run["run_id"]
        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        clean_name = Path(summary["netlist"]).stem + "_conv.v"
        if (sha256(folder / "summary.json") != run["summary_sha256"] or
                sha256(folder / "activation_vectors.json") != run["activation_vectors_sha256"] or
                sha256(folder / clean_name) != run["converted_clean_sha256"] or
                sha256(repeat / clean_name) != run["converted_clean_sha256"]):
            raise ValueError(f"Original/repeat clean source or manifest hash mismatch: {run['run_id']}")
        for variant in run["records"]:
            key = f"{run['run_id']}/{variant['source_path']}"
            if (sha256(folder / variant["source_path"]) != variant["source_sha256"] or
                    sha256(repeat / variant["source_path"]) != variant["source_sha256"]):
                raise ValueError(f"Original/repeat Trojan source hash mismatch: {key}")
            if key in formal:
                behavior = ("top_level_output_witness" if formal[key]["status"] ==
                            "independent_combinational_output_difference_witness" else
                            "no_defined_input_top_level_difference_in_sat_miter")
            elif key in traces:
                behavior = ("simplified_sequential_output_witness" if traces[key]["status"] ==
                            "independent_simplified_scan_trace_pass" else
                            "sequential_trace_failed")
            else:
                behavior = "upstream_only_unverified"
            rows.append({"host": run["host"], "mechanism": run["mechanism"],
                         "variant": key, "behavior": behavior,
                         "deterministic_repeat_match": run["deterministic_repeat_match"]})
    counts = Counter(r["behavior"] for r in rows)
    by_host = defaultdict(Counter)
    for row in rows:
        by_host[row["host"]][row["behavior"]] += 1
    graph_size = shortcuts["synthesized_graph_nodes"]
    gate_count = shortcuts["gate_instances"]
    decision = {
        "status": "no_go_for_model_claim_or_final_host_opening",
        "protocol_version": protocol["protocol_version"],
        "development_hosts": protocol["host_split"]["development"],
        "sealed_final_candidates": protocol["host_split"]["sealed_final_candidate"],
        "variants": len(rows),
        "behavior_counts": dict(counts),
        "behavior_by_host": {h: dict(c) for h, c in by_host.items()},
        "gates": {
            "independent_rerun_byte_identical": all(r["deterministic_repeat_match"] for r in rows),
            "graph_and_candidate_label_lineage_verified": verified["status"] == "verified_construction_lineage_not_reviewed_ground_truth",
            "every_variant_has_independent_top_output_witness": counts["top_level_output_witness"] + counts["simplified_sequential_output_witness"] == len(rows),
            "benign_decoys_equivalent_and_matched": False,
            "simple_gate_count_not_perfect": gate_count["trojan_higher"] < gate_count["pairs"],
            "simple_graph_size_not_perfect": graph_size["trojan_higher"] < graph_size["pairs"],
            "independent_second_insertion_source": False,
            "reviewed_node_labels": False,
            "paired_original_RTL": False,
        },
        "transparent_controls": {
            "gate_instance_count_trojan_higher": [gate_count["trojan_higher"], gate_count["pairs"]],
            "graph_node_count_trojan_higher": [graph_size["trojan_higher"], graph_size["pairs"]],
        },
        "interpretation": (
            "Reproducibility and graph lineage pass, but benchmark validity and shortcut controls fail. "
            "No trained detection or localization result on this cohort supports a method claim."
        ),
        "records": rows,
    }
    if all(decision["gates"].values()):
        raise ValueError("Unexpected all-gates pass; review protocol before opening final hosts")
    (EVIDENCE / "decision.json").write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: decision[k] for k in ("status", "behavior_counts", "gates",
                                                 "transparent_controls")}, indent=2))


if __name__ == "__main__":
    main()
