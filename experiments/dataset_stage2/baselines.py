"""Frozen-fold CPU controls for synthetic circuit edit/fault detection."""
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/dataset_stage2"
torch.set_num_threads(1)


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def graph_features(graph):
    x = graph.x.float().numpy()
    gate = x[:, :16]
    numeric = x[:, 16:]
    pieces = [gate.mean(axis=0), (gate.sum(axis=0) > 0).astype(float)]
    for c in range(4):
        z = numeric[:, c]
        pieces.append(np.array([z.mean(), z.std(), z.max(), *np.quantile(z, [.5, .9, .99])]))
    return np.concatenate(pieces)


def auc(y, score):
    y = np.asarray(y)
    score = np.asarray(score)
    pos = score[y == 1]
    neg = score[y == 0]
    if not len(pos) or not len(neg):
        return None
    return float(((pos[:, None] > neg).sum() + .5 * (pos[:, None] == neg).sum()) / (len(pos) * len(neg)))


def metrics(rows, probs):
    y = np.array([r["label"] for r in rows])
    p = np.clip(np.asarray(probs, float), 1e-8, 1 - 1e-8)
    hosts = sorted({r["host"] for r in rows})
    per_host = []
    pair_wins = []
    for host in hosts:
        ids = [i for i, r in enumerate(rows) if r["host"] == host]
        if len(set(y[ids])) == 2:
            per_host.append(auc(y[ids], p[ids]))
            pos, neg = p[ids][y[ids] == 1], p[ids][y[ids] == 0]
            pair_wins.extend((float(a > b) + .5 * float(a == b)) for a in pos for b in neg)
    logloss = -y * np.log(p) - (1 - y) * np.log(1 - p)
    out = {
        "pooled_auroc": auc(y, p),
        "equal_host_auroc": float(np.mean(per_host)),
        "within_host_pair_ranking": float(np.mean(pair_wins)),
        "balanced_log_loss": float((logloss[y == 0].mean() + logloss[y == 1].mean()) / 2),
        "balanced_accuracy_at_0_5": float((((p[y == 0] < .5).mean()) + ((p[y == 1] >= .5).mean())) / 2),
        "n_hosts": len(hosts),
        "n_pairs": len(pair_wins),
    }
    if all("train_selected_prediction" in r for r in rows):
        pred = np.array([r["train_selected_prediction"] for r in rows])
        out["balanced_accuracy_at_training_selected_threshold"] = float(((pred[y == 0] == 0).mean() + (pred[y == 1] == 1).mean()) / 2)
    return out


def threshold_from_training(y, probs):
    candidates = np.unique(np.r_[0.5, np.quantile(probs, np.linspace(0, 1, 101))])
    scores = [((probs[y == 0] < t).mean() + (probs[y == 1] >= t).mean()) / 2 for t in candidates]
    best = max(range(len(candidates)), key=lambda i: (scores[i], -abs(candidates[i] - .5)))
    return float(candidates[best])


def standardize(train, test):
    mu = train.mean(0)
    sd = train.std(0)
    sd[sd < 1e-7] = 1
    return np.clip((train - mu) / sd, -8, 8), np.clip((test - mu) / sd, -8, 8)


def pca(train, test, rank=16):
    mu = train.mean(0)
    centered = train - mu
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    basis = vt[:rank].T
    return (train - mu) @ basis, (test - mu) @ basis


def logistic(train, y, test):
    train, test = standardize(train, test)
    xt = torch.tensor(train, dtype=torch.float64)
    xe = torch.tensor(test, dtype=torch.float64)
    yt = torch.tensor(y, dtype=torch.float64)
    w = torch.tensor(np.where(y == 1, len(y) / (2 * sum(y)), len(y) / (2 * (len(y) - sum(y)))), dtype=torch.float64)
    model = torch.nn.Linear(train.shape[1], 1, dtype=torch.float64)
    with torch.no_grad():
        model.weight.zero_()
        model.bias.zero_()
    opt = torch.optim.LBFGS(model.parameters(), lr=1, max_iter=80, line_search_fn="strong_wolfe")
    def closure():
        opt.zero_grad()
        loss = (F.binary_cross_entropy_with_logits(model(xt).flatten(), yt, reduction="none") * w).mean()
        loss = loss + .01 * model.weight.square().sum()
        loss.backward()
        return loss
    opt.step(closure)
    with torch.no_grad():
        return torch.sigmoid(model(xe).flatten()).numpy(), torch.sigmoid(model(xt).flatten()).numpy()


def boosted_stumps(train, y, test, rounds=40):
    """Small deterministic Newton logistic boosting with one split per tree."""
    train, test = standardize(train, test)
    y = np.asarray(y, float)
    bias = math.log((y.sum() + .5) / (len(y) - y.sum() + .5))
    logit = np.full(len(y), bias)
    result = np.full(len(test), bias)
    for _ in range(rounds):
        prob = 1 / (1 + np.exp(-np.clip(logit, -30, 30)))
        grad = y - prob
        hess = np.maximum(prob * (1 - prob), 1e-6)
        best = None
        for j in range(train.shape[1]):
            cuts = np.unique(np.quantile(train[:, j], np.linspace(.1, .9, 9)))
            for cut in cuts:
                mask = train[:, j] <= cut
                n = int(mask.sum())
                if n < 10 or len(y) - n < 10:
                    continue
                gl, hl = grad[mask].sum(), hess[mask].sum()
                gr, hr = grad[~mask].sum(), hess[~mask].sum()
                gain = gl * gl / (hl + 5) + gr * gr / (hr + 5)
                if best is None or gain > best[0]:
                    best = (gain, j, cut, gl / (hl + 5), gr / (hr + 5))
        if best is None:
            break
        _, j, cut, left, right = best
        logit += .07 * np.where(train[:, j] <= cut, left, right)
        result += .07 * np.where(test[:, j] <= cut, left, right)
    return 1 / (1 + np.exp(-np.clip(result, -30, 30))), 1 / (1 + np.exp(-np.clip(logit, -30, 30)))


def main():
    records = [r for r in read("data/dataset_stage1/records.json") if r["role"] == "development"]
    folds = read("data/dataset_stage1/folds.json")["folds"]
    manifest = {r["key"]: r for r in read("data/training_audit_v3/manifest.json")["records"]}
    reservation = ROOT / "data/dataset_stage1/final_reservation.json"
    assert reservation.exists() and read("data/dataset_stage1/final_reservation.json")["admitted_final_records"] == 0
    assert len(records) == 185 and len(folds) == 5
    ordered = sorted(records, key=lambda r: r["key"])
    assert {r["key"] for r in ordered} == set(manifest) - {k for k, v in manifest.items() if v["cohort"] == "test"}
    graph, rtl_mean, rtl_max = [], [], []
    for i, row in enumerate(ordered):
        m = manifest[row["key"]]
        path = ROOT / m["file"]
        assert digest(path) == row["prepared_sha256"] == m["sha256"]
        sample = torch.load(path, weights_only=False, map_location="cpu")
        assert sample["label"] == row["label"] and sample["host"] == row["host"]
        graph.append(graph_features(sample["graph"]))
        rtl_mean.append(sample["rtl"].float().mean(0).numpy())
        rtl_max.append(sample["rtl"].float().max(0).values.numpy())
        if (i + 1) % 40 == 0:
            print(f"Verified and pooled {i + 1}/185 circuits", flush=True)
    graph = np.stack(graph)
    rtl_mean, rtl_max = np.stack(rtl_mean), np.stack(rtl_max)
    size = np.array([[math.log1p(r["legacy_nodes"]), math.log1p(r["legacy_edges"])] for r in ordered])
    length = np.array([[math.log1p(r["rtl_characters"]), math.log1p(r["rtl_lines"]), math.log1p(r["rtl_chunks"])] for r in ordered])
    cohorts = sorted({r["cohort"] for r in ordered})
    cohort = np.array([[int(r["cohort"] == c) for c in cohorts] for r in ordered])
    hosts = sorted({r["host"] for r in ordered})
    host_id = np.array([[int(r["host"] == h) for h in hosts] for r in ordered])
    predictions = defaultdict(list)
    index = {r["key"]: i for i, r in enumerate(ordered)}
    assert set.union(*(set(f["test_keys"]) for f in folds)) == set(index)
    for fold in folds:
        test_ids = np.array([index[k] for k in fold["test_keys"]])
        train_ids = np.array([i for i in range(len(ordered)) if i not in set(test_ids)])
        assert not ({ordered[i]["host"] for i in train_ids} & {ordered[i]["host"] for i in test_ids})
        y = np.array([ordered[i]["label"] for i in train_ids])
        pm_tr, pm_te = pca(rtl_mean[train_ids], rtl_mean[test_ids])
        px_tr, px_te = pca(rtl_max[train_ids], rtl_max[test_ids])
        sets = {
            "size_only": (size[train_ids], size[test_ids]),
            "rtl_length_only": (length[train_ids], length[test_ids]),
            "host_id_only": (host_id[train_ids], host_id[test_ids]),
            "cohort_only": (cohort[train_ids], cohort[test_ids]),
            "graph_aggregates": (np.column_stack([size[train_ids], graph[train_ids]]), np.column_stack([size[test_ids], graph[test_ids]])),
            "pooled_codebert": (np.column_stack([pm_tr, px_tr]), np.column_stack([pm_te, px_te])),
            "combined": (np.column_stack([size[train_ids], length[train_ids], graph[train_ids], pm_tr, px_tr]), np.column_stack([size[test_ids], length[test_ids], graph[test_ids], pm_te, px_te])),
        }
        for name, (tr, te) in sets.items():
            methods = ["logistic"] if name in ("host_id_only", "cohort_only") else ["logistic", "boosted_stumps"]
            for method in methods:
                probs, train_probs = logistic(tr, y, te) if method == "logistic" else boosted_stumps(tr, y, te)
                threshold = threshold_from_training(y, train_probs)
                for i, p in zip(test_ids, probs):
                    r = ordered[i]
                    predictions[f"{name}/{method}"].append({"key": r["key"], "fold": fold["fold"], "host": r["host"], "cohort": r["cohort"], "mechanism_family": r["mechanism_family"], "label": r["label"], "probability": float(p), "training_selected_threshold": threshold, "train_selected_prediction": int(p >= threshold)})
        print(f"Fold {fold['fold']} complete", flush=True)
    summary = {}
    for name, rows in predictions.items():
        rows.sort(key=lambda r: r["key"])
        assert len(rows) == 185 and len({r["key"] for r in rows}) == 185
        summary[name] = {"overall": metrics(rows, [r["probability"] for r in rows]), "folds": {str(k): metrics([r for r in rows if r["fold"] == k], [r["probability"] for r in rows if r["fold"] == k]) for k in range(5)}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "predictions.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps({"reservation_sha256": digest(reservation), "folds_sha256": digest(ROOT / "data/dataset_stage1/folds.json"), "scope": "development detection of synthetic edits and faults", "models": summary}, indent=2), encoding="utf-8")
    print(json.dumps({k: v["overall"] for k, v in summary.items()}, indent=2), flush=True)


if __name__ == "__main__":
    main()
