"""Dependency-free metrics so every model is scored by identical code."""
from collections import defaultdict


def confusion(y, p):
    tn = fp = fn = tp = 0
    for t, q in zip(y, p):
        if t == 0 and q == 0: tn += 1
        elif t == 0 and q == 1: fp += 1
        elif t == 1 and q == 0: fn += 1
        else: tp += 1
    return tn, fp, fn, tp


def _div(a, b):
    return a / b if b else 0.0


def auroc(y, score):
    if len(y) != len(score):
        raise ValueError("labels and scores must have equal length")
    n_pos = sum(t == 1 for t in y)
    n_neg = sum(t == 0 for t in y)
    if not n_pos or not n_neg:
        return None
    # Rank-based Mann–Whitney statistic: O(N log N), including tied scores.
    pairs = sorted(zip(score, y), key=lambda pair: pair[0])
    rank_sum = 0.0
    i = 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        average_rank = (i + 1 + j) / 2
        rank_sum += average_rank * sum(label == 1 for _, label in pairs[i:j])
        i = j
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def summarize(y, p, prob=None):
    tn, fp, fn, tp = confusion(y, p)
    rec1, rec0 = _div(tp, tp + fn), _div(tn, tn + fp)
    prec1, prec0 = _div(tp, tp + fp), _div(tn, tn + fn)
    f1_1 = _div(2 * prec1 * rec1, prec1 + rec1)
    f1_0 = _div(2 * prec0 * rec0, prec0 + rec0)
    return {
        "n": len(y), "tn": tn, "fp": fp, "fn": fn, "tp": tp,
        "accuracy": _div(tp + tn, len(y)),
        "balanced_accuracy": (rec1 + rec0) / 2,
        "precision": prec1, "recall": rec1, "fpr": _div(fp, fp + tn),
        "macro_f1": (f1_0 + f1_1) / 2,
        "auroc": auroc(y, prob) if prob is not None else None,
    }


def summarize_predictions(rows):
    """rows: [{fold, benchmark, true_label, predicted_label, prob_trojan?}] -> {'pooled':..., 'fold_1':...}"""
    out = {}
    by_fold = defaultdict(list)
    for r in rows:
        by_fold[r["fold"]].append(r)
    groups = {"pooled": rows, **{f"fold_{k}": v for k, v in sorted(by_fold.items())}}
    for name, g in groups.items():
        prob = [r["prob_trojan"] for r in g] if all("prob_trojan" in r for r in g) else None
        out[name] = summarize([r["true_label"] for r in g], [r["predicted_label"] for r in g], prob)
    return out
