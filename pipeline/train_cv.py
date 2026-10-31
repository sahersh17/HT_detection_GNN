"""Exploratory group-held-out CV for RTL, GNN, and fusion detection.

Usage: python train_cv.py --model {rtl,gnn,fusion} [--dataset legacy] [--epochs 25]
The published folds have already been inspected; they are development evidence,
not a fresh final test set for later model selection.
"""
import argparse
import io
import json
import zipfile

import numpy as np
import torch
import torch.nn.functional as F

import config as C
from metrics import summarize_predictions

_SAFE = None


def _safe_classes():
    global _SAFE
    if _SAFE is None:
        from torch_geometric.data import Data
        from torch_geometric.data.data import DataEdgeAttr, DataTensorAttr
        from torch_geometric.data.storage import GlobalStorage
        _SAFE = [Data, DataEdgeAttr, DataTensorAttr, GlobalStorage]
    return _SAFE


def load_graph(z, names, key):
    with torch.serialization.safe_globals(_safe_classes()):
        g = torch.load(io.BytesIO(z.read(names[key.replace("\\", "/")])), map_location="cpu", weights_only=True)
    g.x, g.edge_index = g.x.float(), g.edge_index.long()
    return g


def pooled_vec(t, how):
    t = t.float()
    return {"mean": t.mean(0), "max": t.max(0).values, "meanmax": torch.cat([t.mean(0), t.max(0).values])}[how]


def class_weights(labels, dev):
    n = torch.bincount(torch.tensor(labels), minlength=2).float()
    return (n.sum() / (2 * n.clamp(min=1))).to(dev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["rtl", "gnn", "fusion"])
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--wd", type=float, default=1e-3)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--pool", default="meanmax", choices=["mean", "max", "meanmax"])
    ap.add_argument("--tag", default=None)
    ap.add_argument("--dataset", default="new", choices=["new", "legacy", "provenance", "provenance_clean"],
                    help="provenance_clean uses regenerated graphs and testbench-free RTL embeddings")
    a = ap.parse_args()

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tag = a.tag or (a.model if a.dataset == "new" else f"{a.dataset}_{a.model}")
    out = C.RUNS / tag
    out.mkdir(parents=True, exist_ok=True)
    samples = json.loads(C.PAIRED_MANIFEST.read_text(encoding="utf-8"))["samples"]
    folds = json.loads(C.FOLDS.read_text(encoding="utf-8"))["folds"]
    z = zipfile.ZipFile(C.GRAPH_ZIP) if a.dataset == "new" else None
    names = {n.replace("\\", "/"): n for n in z.namelist()} if z else None

    def load(s):
        rtl_path = (C.CLEAN_EMB_ROOT / f"{s['benchmark']}_{s['class_name']}.pt"
                    if a.dataset == "provenance_clean" else C.EMB_ROOT / s["rtl_embedding_path"])
        rtl = torch.load(rtl_path, map_location="cpu", weights_only=True).float()
        g = None
        if a.model != "rtl":
            if a.dataset == "new":
                g = load_graph(z, names, s["graph_archive_path"])
            elif a.dataset == "legacy":
                side = s["class_name"] if s["family"] == "AES" else ("tjfree" if s["label"] == 0 else "tjin")
                path = C.ROOT / "trusthub" / "features" / "data" / s["family"] / s["benchmark"] / f"{side}_netlist.pt"
                with torch.serialization.safe_globals(_safe_classes()):
                    g = torch.load(path, map_location="cpu", weights_only=True)
                g.x, g.edge_index = g.x.float(), g.edge_index.long()
            else:
                path = C.PROVENANCE_ROOT / s["benchmark"] / s["class_name"] / "graph.pt"
                with torch.serialization.safe_globals(_safe_classes()):
                    g = torch.load(path, map_location="cpu", weights_only=True)
                g.x, g.edge_index = g.x.float(), g.edge_index.long()
        return s, g, rtl

    preds = []
    for f in folds:
        torch.manual_seed(C.SEED + f["fold"])
        np.random.seed(C.SEED + f["fold"])
        tr_b, te_b = set(f["train_benchmarks"]), set(f["test_benchmarks"])
        # Keep the large AES graphs in the archive until each step needs one.
        train = [s for s in samples if s["benchmark"] in tr_b]
        test = [s for s in samples if s["benchmark"] in te_b]
        y_tr = [s["label"] for s in train]

        if a.model == "rtl":
            # Torch-only logistic baseline: no extra runtime dependency.
            x_tr = torch.stack([pooled_vec(load(s)[2], a.pool) for s in train]).to(dev)
            x_te = torch.stack([pooled_vec(load(s)[2], a.pool) for s in test]).to(dev)
            mean, std = x_tr.mean(0), x_tr.std(0).clamp(min=1e-6)
            x_tr, x_te = (x_tr - mean) / std, (x_te - mean) / std
            linear = torch.nn.Linear(x_tr.shape[1], 2).to(dev)
            opt = torch.optim.LBFGS(linear.parameters(), max_iter=100)
            labels = torch.tensor(y_tr, device=dev)
            weights = class_weights(y_tr, dev)
            def closure():
                opt.zero_grad()
                loss = F.cross_entropy(linear(x_tr), labels, weight=weights)
                loss.backward()
                return loss
            opt.step(closure)
            with torch.no_grad():
                probs = torch.softmax(linear(x_te), -1)[:, 1].cpu().tolist()
        else:
            from models import CrossAttentionFusion, GNNOnly
            net = GNNOnly(C.NODE_DIM, a.hidden) if a.model == "gnn" else CrossAttentionFusion(C.NODE_DIM, C.RTL_DIM, a.hidden)
            model = net.to(dev)
            opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=a.wd)
            w = class_weights(y_tr, dev)
            model.train()
            for ep in range(a.epochs):
                tot = 0.0
                for i in torch.randperm(len(train)).tolist():
                    s = train[i]
                    _, g, r = load(s)
                    opt.zero_grad(set_to_none=True)
                    o = model(g.to(dev), r.to(dev))
                    # With one item, weighted cross entropy's default mean reduction
                    # divides by that same item's weight and cancels it. Sum retains it.
                    loss = F.cross_entropy(o["logits"], torch.tensor([s["label"]], device=dev),
                                           weight=w, reduction="sum")
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    opt.step()
                    tot += loss.item()
                if ep in (0, a.epochs // 2, a.epochs - 1):
                    print(f"fold {f['fold']} epoch {ep + 1}/{a.epochs} loss {tot / len(train):.4f}")
            torch.save(model.state_dict(), out / f"{tag}_fold{f['fold']}.pt")
            model.eval()
            probs = []
            node_dir = out / "node_outputs"
            node_dir.mkdir(exist_ok=True)
            with torch.no_grad():
                for s in test:
                    _, g, r = load(s)
                    o = model(g.to(dev), r.to(dev))
                    probs.append(float(torch.softmax(o["logits"], -1)[0, 1]))
                    arrays = {"node_embeddings": o["node_embeddings"].cpu().numpy()}
                    if a.dataset in ("legacy", "provenance", "provenance_clean"):
                        if a.dataset == "legacy":
                            side = s["class_name"] if s["family"] == "AES" else ("tjfree" if s["label"] == 0 else "tjin")
                            metadata_path = (C.ROOT / "trusthub" / "features" / "metadata" / s["family"] /
                                             s["benchmark"] / f"{side}_netlist.json")
                        else:
                            metadata_path = C.PROVENANCE_ROOT / s["benchmark"] / s["class_name"] / "metadata.json"
                        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                        if metadata["num_nodes"] != g.num_nodes or metadata["graph_id"] != g.graph_id:
                            raise ValueError(f"Node metadata does not match graph: {s['benchmark']}")
                        arrays["node_names"] = np.asarray(metadata["node_names"])
                        arrays["graph_id"] = np.asarray(g.graph_id)
                    if "rtl_to_graph_attention" in o:
                        arrays["rtl_to_graph_attention"] = o["rtl_to_graph_attention"].cpu().numpy()
                        arrays["graph_to_rtl_attention"] = o["graph_to_rtl_attention"].cpu().numpy()
                    np.savez_compressed(node_dir / f"fold{f['fold']}_{s['benchmark']}_{s['class_name']}.npz", **arrays)
        for s, p in zip(test, probs):
            preds.append({"fold": f["fold"], "benchmark": s["benchmark"], "true_label": int(s["label"]),
                          "predicted_label": int(p >= 0.5), "prob_trojan": float(p)})

    (out / "predictions.json").write_text(json.dumps(preds, indent=2))
    summary = summarize_predictions(preds)
    (out / "summary.json").write_text(json.dumps({"evaluation_status": "exploratory_pilot",
                                                   "args": vars(a), "seed": C.SEED, **summary}, indent=2))
    for k, v in summary.items():
        print(k, {m: (round(x, 4) if isinstance(x, float) else x) for m, x in v.items()})


if __name__ == "__main__":
    main()
