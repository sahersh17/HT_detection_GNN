"""One-fold semantic-graph memorization diagnostic; no held-out evaluation."""
import argparse
import hashlib
import json
import math
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch_geometric.nn import GCNConv

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/dataset_stage3"
FOLD = 4  # Preselected as the smallest of the five folds by semantic node count.
SEED = 20261103
MAX_EPOCHS = 80
torch.set_num_threads(2)
torch.manual_seed(SEED)
random.seed(SEED)
np.random.seed(SEED)


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class CellPoolGNN(nn.Module):
    def __init__(self, normalized_pool=False):
        super().__init__()
        self.normalized_pool = normalized_pool
        self.c1 = GCNConv(127, 64)
        self.c2 = GCNConv(64, 64)
        self.norm = nn.LayerNorm(64)
        self.pool_norm = nn.LayerNorm(128) if normalized_pool else nn.Identity()
        self.head = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 2))

    def forward(self, graph):
        x = F.relu(self.c1(graph.x, graph.edge_index))
        x = self.norm(F.relu(self.c2(x, graph.edge_index)))
        cells = x[:graph.n_cell]
        if not len(cells):
            raise ValueError("No original cell rows")
        return self.head(self.pool_norm(torch.cat([cells.sum(0), cells.max(0).values])[None]))


def auc(y, p):
    positive = np.asarray(p)[np.asarray(y) == 1]
    negative = np.asarray(p)[np.asarray(y) == 0]
    return float(((positive[:, None] > negative).sum() + .5 * (positive[:, None] == negative).sum()) / (len(positive) * len(negative)))


def assess(model, items):
    model.eval()
    preds = []
    with torch.no_grad():
        for item in items:
            score = float(model(item["graph"]).softmax(-1)[0, 1])
            preds.append({"key": item["key"], "host": item["host"], "label": item["label"], "probability": score})
    y = np.array([r["label"] for r in preds])
    p = np.array([r["probability"] for r in preds])
    per_host = []
    for host in sorted({r["host"] for r in preds}):
        ids = [i for i, r in enumerate(preds) if r["host"] == host]
        per_host.append(auc(y[ids], p[ids]))
    return {
        "pooled_auroc": auc(y, p),
        "equal_host_auroc": float(np.mean(per_host)),
        "balanced_accuracy_at_0_5": float(((p[y == 0] < .5).mean() + (p[y == 1] >= .5).mean()) / 2),
        "positive_probability_range": [float(p[y == 1].min()), float(p[y == 1].max())],
        "negative_probability_range": [float(p[y == 0].min()), float(p[y == 0].max())],
    }, preds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized-pool", action="store_true")
    parser.add_argument("--max-epochs", type=int, default=MAX_EPOCHS)
    args = parser.parse_args()
    fold_manifest = ROOT / "data/dataset_stage1/folds.json"
    semantic_manifest = ROOT / "data/semantic_graph_v1/manifest.json"
    fold = next(f for f in read("data/dataset_stage1/folds.json")["folds"] if f["fold"] == FOLD)
    semantic = {r["key"]: r for r in read("data/semantic_graph_v1/manifest.json")["records"]}
    audit = {r["key"]: r for r in read("data/dataset_stage1/records.json")}
    items = []
    start = time.monotonic()
    for key in fold["test_keys"]:
        row = semantic[key]
        path = ROOT / row["file"]
        if sha(path) != row["sha256"] or row["sha256"] != audit[key]["semantic_sha256"]:
            raise ValueError(f"Semantic tensor hash mismatch: {key}")
        item = torch.load(path, weights_only=False, map_location="cpu")
        graph = item["graph"]
        if graph.x.shape[1] != 127 or graph.n_cell < 1 or graph.n_cell > graph.num_nodes:
            raise ValueError(f"Invalid cell prefix: {key}")
        graph.x = graph.x.float()
        graph.edge_index = graph.edge_index.long()
        if item["label"] != audit[key]["label"] or item["host"] != audit[key]["host"]:
            raise ValueError(f"Identity mismatch: {key}")
        item["key"] = key
        items.append(item)
    assert len(items) == 38 and len({item["host"] for item in items}) == 12
    groups = defaultdict(lambda: defaultdict(list))
    for i, item in enumerate(items):
        groups[item["host"]][item["label"]].append(i)
    assert all(set(v) == {0, 1} for v in groups.values())
    print(f"Loaded {len(items)} hashed semantic graphs, {sum(x['graph'].num_nodes for x in items)} nodes", flush=True)
    model = CellPoolGNN(normalized_pool=args.normalized_pool)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=0)
    curve = []
    snapshots = {}
    initial, initial_preds = assess(model, items)
    snapshots["0"] = initial
    print(f"Initial train AUROC {initial['pooled_auroc']:.3f}, equal-host {initial['equal_host_auroc']:.3f}", flush=True)
    rng = random.Random(SEED)
    for epoch in range(1, args.max_epochs + 1):
        model.train()
        hosts = sorted(groups)
        rng.shuffle(hosts)
        losses = []
        for host in hosts:
            picks = [rng.choice(groups[host][0]), rng.choice(groups[host][1])]
            optimizer.zero_grad(set_to_none=True)
            loss = sum(F.cross_entropy(model(items[i]["graph"]), torch.tensor([items[i]["label"]])) for i in picks) / 2
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            if not torch.isfinite(norm):
                raise ValueError("Nonfinite gradient")
            optimizer.step()
            losses.append(float(loss.detach()))
        curve.append({"epoch": epoch, "sampled_loss": float(np.mean(losses))})
        if epoch == 1 or epoch % 5 == 0:
            score, predictions = assess(model, items)
            snapshots[str(epoch)] = score
            print(f"Epoch {epoch}: loss {np.mean(losses):.4f}, train AUROC {score['pooled_auroc']:.3f}, equal-host {score['equal_host_auroc']:.3f}, BA {score['balanced_accuracy_at_0_5']:.3f}, seconds {time.monotonic()-start:.1f}", flush=True)
            if score["pooled_auroc"] >= .99 and score["equal_host_auroc"] >= .99 and score["balanced_accuracy_at_0_5"] >= .95:
                break
    final_epoch = max(map(int, snapshots))
    final, predictions = assess(model, items)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "purpose": "single-fold training memorization only; no validation or generalization claim",
        "fold": FOLD, "seed": SEED, "max_epochs": args.max_epochs, "completed_epochs": final_epoch,
        "folds_sha256": sha(fold_manifest), "semantic_manifest_sha256": sha(semantic_manifest),
        "architecture": "127->64->64 GCN; original-cell prefix sum plus max pooling; optional pooled LayerNorm; 64-unit head; no dropout or weight decay",
        "normalized_pool": args.normalized_pool,
        "records": len(items), "hosts": len(groups), "positive": sum(item["label"] for item in items),
        "total_nodes": sum(item["graph"].num_nodes for item in items),
        "elapsed_seconds": time.monotonic() - start, "snapshots": snapshots, "curve": curve,
        "final_predictions": predictions,
    }
    suffix = "normalized" if args.normalized_pool else "rawsum"
    report_path = OUT / f"memorization_fold4_{suffix}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    torch.save(model.state_dict(), OUT / f"memorization_fold4_{suffix}_state.pt")
    print(f"Saved {report_path}", flush=True)


if __name__ == "__main__":
    main()
