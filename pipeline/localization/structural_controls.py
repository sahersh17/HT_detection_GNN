"""Tie-aware, untrained node controls on unreviewed mapped-netlist labels."""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import auroc  # noqa: E402
from extended_lofo import average_precision  # noqa: E402
from train_cv import _safe_classes  # noqa: E402


def no_hit_probability(negative, total, draws):
    if draws > negative:
        return 0.0
    prob = 1.0
    for i in range(draws):
        prob *= (negative-i)/(total-i)
    return prob


def summarize(scores, labels, ks=(10, 50, 100)):
    known = [(float(s), int(y)) for s, y in zip(scores, labels) if y >= 0]
    n = len(known); positives = sum(y for _, y in known)
    groups = defaultdict(list)
    for score, label in known:
        groups[score].append(label)
    highest_positive = max(score for score, y in known if y)
    higher = sum(len(group) for score, group in groups.items() if score > highest_positive)
    tie = groups[highest_positive]
    rank_interval = [higher+1, higher+len(tie)-sum(tie)+1]
    result = {"known_nodes": n, "positives": positives, "unknown": len(labels)-n,
              "auroc": auroc([y for _, y in known], [s for s, _ in known]),
              "ap": average_precision([y for _, y in known], [s for s, _ in known]),
              "first_positive_rank_bounds": rank_interval}
    for k in ks:
        budget = min(k, n)
        remaining = budget; expected_hits = 0.0; prob_no_hit = 1.0
        for score in sorted(groups, reverse=True):
            group = groups[score]
            take = min(remaining, len(group))
            if take <= 0:
                break
            p = sum(group)
            expected_hits += take*p/len(group)
            prob_no_hit *= no_hit_probability(len(group)-p, len(group), take)
            remaining -= take
        result[f"expected_hit@{k}"] = 1-prob_no_hit
        result[f"expected_recall@{k}"] = expected_hits/positives
        result[f"random_hit@{k}"] = 1-no_hit_probability(n-positives,n,budget)
    return result


def main():
    rows = []
    for path in sorted((ROOT / "data/localization_gate_audit").glob("*_candidate_labels.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        audit = record["audit"]
        if audit["label_status"] != "mechanical_candidate_unreviewed" or audit["family"] == "b15":
            continue
        with torch.serialization.safe_globals(_safe_classes()):
            graph = torch.load(ROOT / "runs" / record["graph_id"] / "graph.pt", weights_only=True, map_location="cpu")
        if graph.num_nodes != len(record["labels"]):
            raise ValueError(f"Node alignment failed: {record['graph_id']}")
        x = graph.x
        gate_class = x[:, :-4].argmax(1)
        counts = torch.bincount(gate_class)
        methods = {"fanin": x[:, -4].tolist(), "fanout": x[:, -3].tolist(),
                   "near_output": (-x[:, -1]).tolist(),
                   "gate_class_rarity": (1/counts[gate_class].float()).tolist(),
                   "fanout_over_output_distance": (x[:, -3]/(1+x[:, -1])).tolist()}
        rows.append({"graph_id": record["graph_id"], "family": audit["family"],
                     "label_status": audit["label_status"],
                     "methods": {name: summarize(scores, record["labels"]) for name, scores in methods.items()}})
        print(record["graph_id"], len(rows), flush=True)
    target = ROOT / "data/localization_gate_audit/structural_controls.json"
    target.write_text(json.dumps({"status": "exploratory_unreviewed_candidates", "designs": rows}, indent=2), encoding="utf-8")
    print(f"{len(rows)} designs, {len({r['family'] for r in rows})} hosts")


if __name__ == "__main__":
    main()
