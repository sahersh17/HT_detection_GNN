"""Paired graph/cell-count diagnostic on the frozen 80-record LOFO cohort."""
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/lofo_detection"


def main():
    protocol = json.loads((DATA / "protocol.json").read_text(encoding="utf-8"))
    preds = json.loads((DATA / "gnn_predictions.json").read_text(encoding="utf-8"))
    scores = {(p["benchmark"], p["side"]): p["prob_trojan"] for p in preds}
    paired = defaultdict(dict)
    for record in protocol["samples"]:
        graph_path = ROOT / record["path"]
        if hashlib.sha256(graph_path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Graph hash mismatch: {graph_path}")
        metadata = json.loads(graph_path.with_name("metadata.json").read_text(encoding="utf-8"))
        if metadata["num_nodes"] != len(metadata["node_types"]):
            raise ValueError(f"Cell metadata mismatch: {graph_path}")
        paired[record["benchmark"]][record["side"]] = {
            "family": record["family"], "nodes": metadata["num_nodes"],
            "edges": metadata["num_edges"], "cell_types": Counter(metadata["node_types"]),
            "score": scores[record["benchmark"], record["side"]]}
    rows = []
    for benchmark, sides in sorted(paired.items()):
        if set(sides) != {"clean", "trojan"}:
            raise ValueError(f"Unpaired: {benchmark}")
        c, t = sides["clean"], sides["trojan"]
        delta = t["cell_types"] - c["cell_types"]
        removed = c["cell_types"] - t["cell_types"]
        rows.append({"benchmark": benchmark, "family": c["family"],
                     "clean_nodes": c["nodes"], "trojan_nodes": t["nodes"],
                     "node_delta": t["nodes"]-c["nodes"], "edge_delta": t["edges"]-c["edges"],
                     "cell_type_additions": dict(delta), "cell_type_removals": dict(removed),
                     "gnn_score_delta": t["score"]-c["score"],
                     "larger_is_trojan": int(t["nodes"]>c["nodes"]),
                     "gnn_ranks_trojan_higher": int(t["score"]>c["score"])})
    families = sorted({r["family"] for r in rows})
    by_family = {family: {"pairs": len(group),
                          "larger_correct": sum(r["larger_is_trojan"] for r in group),
                          "gnn_correct": sum(r["gnn_ranks_trojan_higher"] for r in group),
                          "signs": sorted(set((r["node_delta"]>0)-(r["node_delta"]<0) for r in group))}
                 for family in families if (group := [r for r in rows if r["family"] == family])}
    family_rates = [by_family[f]["gnn_correct"]/by_family[f]["pairs"] for f in families]
    rng = random.Random(42)
    boot = sorted(sum(rng.choice(family_rates) for _ in families)/len(families) for _ in range(10000))
    output = {"protocol": "data/lofo_detection/protocol.json", "seed": 42, "pairs": rows,
              "summary": {"n_pairs": len(rows), "n_families": len(families),
                          "larger_correct": sum(r["larger_is_trojan"] for r in rows),
                          "gnn_correct": sum(r["gnn_ranks_trojan_higher"] for r in rows),
                          "rule_agreement": sum(r["larger_is_trojan"] == r["gnn_ranks_trojan_higher"] for r in rows),
                          "equal_family_gnn_pair_mean": sum(family_rates)/len(families),
                          "family_bootstrap_95_percentile": [boot[250], boot[9749]],
                          "bootstrap_note": "Only seven heterogeneous host families; interval is descriptive, not proof of generalization."},
              "by_family": by_family}
    (DATA / "size_delta_diagnostic.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"summary": output["summary"], "by_family": by_family}, indent=2))


if __name__ == "__main__":
    main()
