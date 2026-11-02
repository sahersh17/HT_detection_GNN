"""Untrained node-ranking diagnostics on v2 construction-derived candidates."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import torch
from torch_geometric.data import Data
from torch_geometric.data.data import DataEdgeAttr, DataTensorAttr
from torch_geometric.data.storage import GlobalStorage

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "data/independent_benchmark_v2"
RUNS = ROOT / "runs/independent_benchmark_v2/runs"
sys.path.insert(0, str(ROOT / "pipeline/localization"))
from structural_controls import summarize  # noqa: E402


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    lineage = read_json(EVIDENCE / "graph_lineage.json")["records"]
    formal = {row["variant"]: row for row in read_json(EVIDENCE / "formal_combinational.json")["records"]}
    traces = {f"{row['run_id']}/{row['source_path']}": row
              for row in read_json(EVIDENCE / "sequential_trace.json")["records"]}
    rows = []
    for record in lineage:
        key = record["variant"]
        host = record["run_id"].split("_")[0]
        mechanism = record["run_id"].split("_")[1]
        if key in formal:
            evidence = formal[key]["status"]
            behavior_tier = "top_level_sat_witness" if evidence == "independent_combinational_output_difference_witness" else "failed_top_level_sat"
        elif key in traces:
            trace = traces[key]
            evidence = trace["status"]
            behavior_tier = ("simplified_sequential_trace" if evidence ==
                             "independent_simplified_scan_trace_pass" else
                             "no_independent_sequential_witness")
        else:
            evidence = "upstream_self_validation_only"
            behavior_tier = "unverified"
        source = RUNS / key
        folder = source.parent.parent / "graphs" / source.stem
        labels = read_json(folder / "node_labels.json")["labels"]
        with torch.serialization.safe_globals([Data, DataEdgeAttr, DataTensorAttr, GlobalStorage]):
            graph = torch.load(folder / "graph.pt", map_location="cpu", weights_only=True)
        if len(labels) != graph.num_nodes:
            raise ValueError(f"Label/graph node count mismatch: {key}")
        x = graph.x
        gate_class = x[:, :-4].argmax(1)
        class_count = torch.bincount(gate_class)
        scores = {
            "fanin": x[:, -4].tolist(),
            "fanout": x[:, -3].tolist(),
            "near_output": (-x[:, -1]).tolist(),
            "gate_class_rarity": (1 / class_count[gate_class].float()).tolist(),
            "fanout_over_output_distance": (x[:, -3] / (1 + x[:, -1])).tolist(),
        }
        rows.append({"variant": key, "host": host, "mechanism": mechanism,
                     "behavior_tier": behavior_tier, "behavior_evidence": evidence,
                     "label_status": "construction_derived_unreviewed",
                     "methods": {name: summarize(values, labels) for name, values in scores.items()}})
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["behavior_tier"]].append(row)
    summary = {tier: {"variants": len(members),
                      "positive_candidates": sum(r["methods"]["fanin"]["positives"] for r in members),
                      "mean_ap_by_method": {
                          name: sum(r["methods"][name]["ap"] for r in members) / len(members)
                          for name in rows[0]["methods"]}}
               for tier, members in grouped.items()}
    report = {"status": "exploratory_untrained_controls_on_unreviewed_candidate_labels",
              "summary_by_behavior_tier": summary, "variants": rows,
              "limits": ["No benign decoys; size and gate-count shortcuts fail the benchmark gate",
                         "Candidate labels are construction-derived and have not been independently reviewed",
                         "Sequential traces use a simplified scan FF evaluator, not full RTL equivalence",
                         "Do not use these numbers for a learned localization superiority claim"]}
    target = EVIDENCE / "localization_controls.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
