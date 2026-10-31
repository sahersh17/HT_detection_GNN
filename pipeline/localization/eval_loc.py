"""Node-level localization metrics. Scores are per-node suspicion (higher = more suspicious); gt is 0/1 per node.

Always compare against the random baseline: with |GT| Trojan nodes out of N, a random ranking has expected
precision@k = |GT|/N. Trojans are a tiny fraction of an ~8000-node graph, so absolute numbers can look
impressive or dismal without it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from metrics import auroc  # noqa: E402


def evaluate(scores, gt, ks=(1, 5, 10, 50)):
    n, pos = len(gt), sum(gt)
    if pos == 0:
        return None
    order = sorted(range(n), key=lambda i: -scores[i])
    res = {"n_nodes": n, "n_trojan_nodes": pos, "random_precision": pos / n,
           "node_auroc": auroc(gt, scores)}
    top_gt = set(order[:pos])
    inter = sum(gt[i] for i in top_gt)
    res["precision_at_|GT|"] = inter / pos
    res["iou_at_|GT|"] = inter / (2 * pos - inter)          # |top ∩ GT| / |top ∪ GT|, both of size pos
    for k in ks:
        top = order[:k]
        res[f"hit@{k}"] = int(any(gt[i] for i in top))
        res[f"precision@{k}"] = sum(gt[i] for i in top) / k
    res["first_trojan_rank"] = next(r for r, i in enumerate(order, 1) if gt[i])
    return res


def aggregate(per_design):
    """Mean over designs that have ground truth."""
    rows = [r for r in per_design if r]
    if not rows:
        return {}
    keys = [k for k in rows[0] if isinstance(rows[0][k], (int, float)) and rows[0][k] is not None]
    return {k: sum(r[k] for r in rows if r[k] is not None) / len(rows) for k in keys} | {"designs": len(rows)}
