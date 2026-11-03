"""Golden-free typed local-node MIL on the frozen semantic graphs."""
import argparse
import hashlib
import json
import math
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/local_mil_v1"
torch.set_num_threads(2)


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def auc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    a, b = p[y == 1], p[y == 0]
    return float(((a[:, None] > b).sum() + .5 * (a[:, None] == b).sum()) / (len(a) * len(b)))


def metrics(rows):
    y = np.array([r["label"] for r in rows])
    p = np.array([r["probability"] for r in rows])
    hosts = sorted({r["host"] for r in rows})
    per_host = []
    for host in hosts:
        ids = [i for i, r in enumerate(rows) if r["host"] == host]
        per_host.append(auc(y[ids], p[ids]))
    return {
        "pooled_auroc": auc(y, p),
        "equal_host_auroc": float(np.mean(per_host)),
        "balanced_accuracy_at_0_5": float(((p[y == 0] < .5).mean() + (p[y == 1] >= .5).mean()) / 2),
        "positive_range": [float(p[y == 1].min()), float(p[y == 1].max())],
        "negative_range": [float(p[y == 0].min()), float(p[y == 0].max())],
    }


def candidates(x, n_cell):
    # Original cells, parameter/init value bits, and literal-valued connection pins.
    select = (x[:, 20] > .5) | (x[:, 25] > .5) | ((x[:, 22] > .5) & (x[:, 28:30].sum(1) > .5))
    assert select[:n_cell].all() and select.any()
    return select


class TypedConv(nn.Module):
    def __init__(self, hidden):
        super().__init__()
        self.self_linear = nn.Linear(hidden, hidden)
        self.source_linear = nn.Linear(hidden, hidden, bias=False)
        self.relation = nn.Embedding(12, hidden)
        self.norm = nn.LayerNorm(hidden)

    def forward(self, h, edge_index, edge_type):
        src, dst = edge_index
        message = self.source_linear(h[src]) + self.relation(edge_type)
        total = torch.zeros_like(h).index_add_(0, dst, message)
        degree = torch.zeros((len(h), 1), device=h.device).index_add_(0, dst, torch.ones((len(dst), 1), device=h.device))
        return F.relu(self.norm(self.self_linear(h) + total / degree.clamp(min=1))) + h


class LocalMIL(nn.Module):
    def __init__(self, layers=2, readout="topk", hidden=64):
        super().__init__()
        self.layers = layers
        self.readout = readout
        self.input = nn.Sequential(nn.Linear(127, hidden), nn.LayerNorm(hidden), nn.ReLU())
        self.convs = nn.ModuleList(TypedConv(hidden) for _ in range(layers))
        self.score = nn.Sequential(nn.Linear(hidden * (layers + 1), hidden), nn.ReLU(), nn.Linear(hidden, 1))
        self.attention = nn.Linear(hidden * (layers + 1), 1) if readout == "attention" else None
        self.reconstruct_value = nn.Linear(hidden * (layers + 1), 4)

    def encode(self, graph, x_override=None):
        h = self.input(graph.x if x_override is None else x_override)
        states = [h]
        for conv in self.convs:
            h = conv(h, graph.edge_index, graph.edge_type)
            states.append(h)
        return torch.cat(states, dim=1)

    def forward(self, graph, mask):
        joined = self.encode(graph)[mask]
        scores = self.score(joined).flatten()
        if self.readout == "max":
            return scores.max()[None]
        if self.readout == "topk":
            top = scores.topk(min(8, len(scores))).values
            return (torch.logsumexp(top, dim=0) - math.log(len(top)))[None]
        weights = torch.softmax(self.attention(joined).flatten(), dim=0)
        return (weights * scores).sum()[None]


def predict(model, items):
    model.eval()
    out = []
    with torch.no_grad():
        for item in items:
            p = float(torch.sigmoid(model(item["graph"], item["candidate_mask"]))[0])
            out.append({"key": item["key"], "host": item["host"], "label": item["label"], "probability": p})
    return out


def load_fold(fold):
    folds = read("data/dataset_stage1/folds.json")["folds"]
    group = next(f for f in folds if f["fold"] == fold)
    semantic = {r["key"]: r for r in read("data/semantic_graph_v1/manifest.json")["records"]}
    audit = {r["key"]: r for r in read("data/dataset_stage1/records.json")}
    items = []
    for key in group["test_keys"]:
        row = semantic[key]
        path = ROOT / row["file"]
        if sha(path) != row["sha256"] or row["sha256"] != audit[key]["semantic_sha256"]:
            raise ValueError(f"Hash mismatch: {key}")
        item = torch.load(path, weights_only=False, map_location="cpu")
        if item["label"] != audit[key]["label"] or item["host"] != audit[key]["host"]:
            raise ValueError(f"Identity mismatch: {key}")
        graph = item["graph"]
        graph.x, graph.edge_index, graph.edge_type = graph.x.float(), graph.edge_index.long(), graph.edge_type.long()
        assert graph.x.shape[1] == 127 and graph.edge_type.min() >= 0 and graph.edge_type.max() < 12
        item["key"] = key
        item["candidate_mask"] = candidates(graph.x, graph.n_cell)
        items.append(item)
    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fold", type=int, default=4)
    parser.add_argument("--layers", type=int, choices=[1, 2], default=2)
    parser.add_argument("--readout", choices=["topk", "max", "attention"], default="topk")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20261103)
    parser.add_argument("--pretrain-epochs", type=int, default=0)
    args = parser.parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    started = time.monotonic()
    items = load_fold(args.fold)
    print(f"Loaded fold {args.fold}: {len(items)} records, {sum(i['graph'].num_nodes for i in items)} nodes, {sum(int(i['candidate_mask'].sum()) for i in items)} scored candidates", flush=True)
    groups = defaultdict(lambda: defaultdict(list))
    for i, item in enumerate(items):
        groups[item["host"]][item["label"]].append(i)
    assert all(set(group) == {0, 1} for group in groups.values())
    model = LocalMIL(layers=args.layers, readout=args.readout)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    pretrain_history = []
    if args.pretrain_epochs:
        clean = [item for item in items if item["label"] == 0]
        for epoch in range(1, args.pretrain_epochs + 1):
            model.train()
            losses = []
            for item in clean:
                graph = item["graph"]
                values = torch.where(graph.x[:, 25] > .5)[0]
                if not len(values):
                    continue
                selected = values[torch.randperm(len(values))[:min(128, len(values))]]
                target = graph.x[selected, 28:32].argmax(1)
                masked = graph.x.clone()
                masked[selected, 28:32] = 0
                optimizer.zero_grad(set_to_none=True)
                prediction = model.reconstruct_value(model.encode(graph, masked)[selected])
                loss = F.cross_entropy(prediction, target)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.detach()))
            pretrain_history.append({"epoch": epoch, "reconstruction_loss": float(np.mean(losses))})
            print(f"Pretrain {epoch}: masked-bit loss {np.mean(losses):.4f}, seconds {time.monotonic()-started:.1f}", flush=True)
    history = []
    baseline = metrics(predict(model, items))
    best = (baseline["pooled_auroc"], 0)
    print(f"Initial AUROC {baseline['pooled_auroc']:.3f}, equal-host {baseline['equal_host_auroc']:.3f}", flush=True)
    rng = random.Random(args.seed)
    for epoch in range(1, args.epochs + 1):
        model.train()
        hosts = sorted(groups)
        rng.shuffle(hosts)
        losses = []
        for host in hosts:
            picks = [rng.choice(groups[host][0]), rng.choice(groups[host][1])]
            optimizer.zero_grad(set_to_none=True)
            loss = sum(F.binary_cross_entropy_with_logits(model(items[i]["graph"], items[i]["candidate_mask"]), torch.tensor([float(items[i]["label"])])) for i in picks) / 2
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            if not torch.isfinite(norm):
                raise ValueError("Nonfinite gradient")
            optimizer.step()
            losses.append(float(loss.detach()))
        if epoch == 1 or epoch % 5 == 0:
            pred = predict(model, items)
            result = metrics(pred)
            best = max(best, (result["pooled_auroc"], epoch))
            history.append({"epoch": epoch, "loss": float(np.mean(losses)), **result})
            print(f"Epoch {epoch}: loss {np.mean(losses):.4f}, AUROC {result['pooled_auroc']:.3f}, equal-host {result['equal_host_auroc']:.3f}, BA {result['balanced_accuracy_at_0_5']:.3f}, seconds {time.monotonic()-started:.1f}", flush=True)
            if result["pooled_auroc"] >= .99 and result["equal_host_auroc"] >= .99 and result["balanced_accuracy_at_0_5"] >= .95:
                break
    result = {"scope": "golden-free one-fold training memorization; no held-out evaluation", "fold": args.fold, "layers": args.layers, "readout": args.readout, "epochs": args.epochs, "seed": args.seed, "pretrain_epochs": args.pretrain_epochs, "pretrain_history": pretrain_history, "records": len(items), "hosts": len(groups), "semantic_manifest_sha256": sha(ROOT / "data/semantic_graph_v1/manifest.json"), "folds_sha256": sha(ROOT / "data/dataset_stage1/folds.json"), "initial": baseline, "best_pooled_auroc": {"value": best[0], "epoch": best[1]}, "history": history, "final_predictions": predict(model, items), "elapsed_seconds": time.monotonic()-started}
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"fold{args.fold}_layers{args.layers}_{args.readout}" + (f"_pretrain{args.pretrain_epochs}" if args.pretrain_epochs else "")
    (OUT / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    torch.save(model.state_dict(), OUT / f"{name}.pt")
    print(f"Saved {name}", flush=True)


if __name__ == "__main__":
    main()
