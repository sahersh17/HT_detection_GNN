"""Frozen diagnostic: train on the 21 original pairs, test memctrl and PIC.

This held-out-family diagnostic has only two new clean host sources. It is not
the untouched, adequately powered final test required for a method paper.
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

import config as C
from metrics import summarize_predictions
from train_cv import _safe_classes, class_weights, pooled_vec

EXPANSION = ["memctrl-T100", *(f"PIC16F84-T{n}" for n in (100, 200, 300, 400))]


def samples():
    train = json.loads(C.PAIRED_MANIFEST.read_text(encoding="utf-8"))["samples"]
    test = [{"benchmark": b, "class_name": side, "label": int(side == "trojan"),
             "family": b.split("-")[0]} for b in EXPANSION for side in ("clean", "trojan")]
    if {s["benchmark"] for s in train} & set(EXPANSION):
        raise ValueError("External benchmark appears in training manifest")
    train_manifest = json.loads((C.ROOT / "runs" / "rtl_clean_v1" / "manifest.json").read_text(encoding="utf-8"))
    test_manifest = json.loads((C.ROOT / "runs" / "rtl_expansion_v1" / "manifest.json").read_text(encoding="utf-8"))
    train_hashes = {r["source_text_sha256"] for r in train_manifest["records"]}
    test_hashes = {r["source_text_sha256"] for r in test_manifest["records"]}
    if train_hashes & test_hashes:
        raise ValueError("RTL source appears in both training and external test")
    return train, test


def load(sample, external):
    benchmark, side = sample["benchmark"], sample["class_name"]
    rtl_root = C.ROOT / "runs" / ("rtl_expansion_v1" if external else "rtl_clean_v1")
    rtl = torch.load(rtl_root / f"{benchmark}_{side}.pt", map_location="cpu", weights_only=True).float()
    graph_root = (C.ROOT / "runs" / ("expansion_graphs" if sample["family"] == "memctrl" else "expansion_pic_graphs")
                  if external else C.PROVENANCE_ROOT)
    with torch.serialization.safe_globals(_safe_classes()):
        graph = torch.load(graph_root / benchmark / side / "graph.pt", map_location="cpu", weights_only=True)
    graph.x, graph.edge_index = graph.x.float(), graph.edge_index.long()
    if int(graph.y.item()) != sample["label"]:
        raise ValueError(f"Graph label mismatch: {benchmark}/{side}")
    return graph, rtl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=["rtl", "gnn", "fusion", "length"])
    parser.add_argument("--epochs", type=int, default=25)
    args = parser.parse_args()
    if args.epochs != 25:
        parser.error("Frozen diagnostic uses exactly 25 epochs")
    train, test = samples()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(C.SEED)
    np.random.seed(C.SEED)
    random.seed(C.SEED)
    out = C.RUNS / f"external_{args.model}"
    out.mkdir(parents=True, exist_ok=True)
    if args.model in ("rtl", "length"):
        if args.model == "length":
            from length_baseline import features
            x_train = torch.tensor([features(s) for s in train], dtype=torch.float32, device=dev)
            x_test = torch.tensor([features(s) for s in test], dtype=torch.float32, device=dev)
        else:
            x_train = torch.stack([pooled_vec(load(s, False)[1], "meanmax") for s in train]).to(dev)
            x_test = torch.stack([pooled_vec(load(s, True)[1], "meanmax") for s in test]).to(dev)
        mean, std = x_train.mean(0), x_train.std(0).clamp(min=1e-6)
        x_train, x_test = (x_train - mean) / std, (x_test - mean) / std
        linear = torch.nn.Linear(x_train.shape[1], 2).to(dev)
        optimizer = torch.optim.LBFGS(linear.parameters(), max_iter=100)
        labels = torch.tensor([s["label"] for s in train], device=dev)
        weights = class_weights(labels.tolist(), dev)

        def closure():
            optimizer.zero_grad()
            loss = F.cross_entropy(linear(x_train), labels, weight=weights)
            loss.backward()
            return loss

        optimizer.step(closure)
        with torch.no_grad():
            probabilities = torch.softmax(linear(x_test), -1)[:, 1].cpu().tolist()
    else:
        from models import CrossAttentionFusion, GNNOnly
        net = GNNOnly(C.NODE_DIM, 64) if args.model == "gnn" else CrossAttentionFusion(C.NODE_DIM, C.RTL_DIM, 64)
        net = net.to(dev)
        optimizer = torch.optim.AdamW(net.parameters(), lr=3e-4, weight_decay=1e-3)
        weights = class_weights([s["label"] for s in train], dev)
        net.train()
        for epoch in range(25):
            total = 0.0
            for i in torch.randperm(len(train)).tolist():
                sample = train[i]
                graph, rtl = load(sample, False)
                optimizer.zero_grad(set_to_none=True)
                output = net(graph.to(dev), rtl.to(dev))
                loss = F.cross_entropy(output["logits"], torch.tensor([sample["label"]], device=dev),
                                       weight=weights, reduction="sum")
                loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                optimizer.step()
                total += loss.item()
            if epoch in (0, 12, 24):
                print(f"epoch {epoch + 1}/25 loss {total / len(train):.4f}", flush=True)
        torch.save(net.state_dict(), out / "model.pt")
        net.eval()
        probabilities = []
        with torch.no_grad():
            for sample in test:
                graph, rtl = load(sample, True)
                output = net(graph.to(dev), rtl.to(dev))
                probabilities.append(float(torch.softmax(output["logits"], -1)[0, 1]))
    rows = [{"benchmark": sample["benchmark"], "family": sample["family"], "true_label": sample["label"],
             "predicted_label": int(probability >= 0.5), "prob_trojan": float(probability), "fold": 0}
            for sample, probability in zip(test, probabilities)]
    summary = summarize_predictions(rows)
    for family in sorted({row["family"] for row in rows}):
        summary[f"family_{family}"] = summarize_predictions([row for row in rows if row["family"] == family])["pooled"]
    (out / "predictions.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({"evaluation_status": "held_out_family_diagnostic",
                                                   "train_pairs": len(train) // 2, "test_pairs": len(test) // 2,
                                                   "train_clean_source_groups": 3, "test_clean_source_groups": 2,
                                                   "args": vars(args), "seed": C.SEED, **summary}, indent=2), encoding="utf-8")
    print(json.dumps(summary["pooled"], indent=2))


if __name__ == "__main__":
    main()
