"""Run identical graph, RTL, structured-RTL, and aligned-fusion protocols.

All original hosts and the memctrl/PIC diagnostic have been inspected. Outputs
are development diagnostics, not an untouched generalization estimate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import summarize_predictions  # noqa: E402
from train_cv import _safe_classes  # noqa: E402
from model import TypedFusion, training_loss  # noqa: E402

OUT = ROOT / "runs" / "typed_fusion_v1"
EXTERNAL = {"memctrl-T100", *(f"PIC16F84-T{n}" for n in (100, 200, 300, 400))}


def load_data() -> tuple[list[dict], str]:
    manifest_path = OUT / "manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    rows = manifest["records"]
    if len(rows) != 52 or len({(r["benchmark"], r["side"]) for r in rows}) != 52:
        raise ValueError("Expected 42 development and 10 diagnostic records")
    dev_rtl = json.loads((ROOT / "runs/rtl_clean_v1/manifest.json").read_text())["records"]
    ext_rtl = json.loads((ROOT / "runs/rtl_expansion_v1/manifest.json").read_text())["records"]
    clean_hash = {r["benchmark"]: r["source_text_sha256"] for r in dev_rtl + ext_rtl if r["side"] == "clean"}
    samples = []
    for row in rows:
        path = ROOT / row["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"Prepared item hash mismatch: {path}")
        with torch.serialization.safe_globals(_safe_classes()):
            item = torch.load(path, map_location="cpu", weights_only=True)
        graph = item["graph"]
        if (graph.x.shape[1] != manifest["node_dim"] or graph.edge_attr.shape[1] != manifest["edge_dim"]
                or item["rtl"].shape[1] != 768 or item["struct"].shape[1] != manifest["rtl_struct_dim"]
                or item["links"].shape[0] != 2 or len(item["weights"]) != item["links"].shape[1]
                or item["label"] != int(item["side"] == "trojan")):
            raise ValueError(f"Invalid prepared item: {path}")
        item["family"] = row["benchmark"].split("-")[0]
        item["source_id"] = clean_hash[row["benchmark"]]
        samples.append(item)
    return samples, hashlib.sha256(raw).hexdigest()


def weights_for(train: list[dict]) -> list[float]:
    families = {r["family"] for r in train}
    groups = Counter((r["family"], r["label"], r["source_id"]) for r in train)
    sources = Counter((family, label) for family, label, _ in groups)
    return [len(train) / (len(families) * 2 * sources[r["family"], r["label"]]
            * groups[r["family"], r["label"], r["source_id"]]) for r in train]


def pairwise(rows: list[dict]) -> dict:
    pairs = defaultdict(dict)
    for row in rows:
        pairs[row["benchmark"]][row["true_label"]] = row["prob_trojan"]
    complete = [p for p in pairs.values() if set(p) == {0, 1}]
    wins = sum(1 if p[1] > p[0] else 0.5 if p[1] == p[0] else 0 for p in complete)
    return {"pairs": len(complete), "wins_with_half_ties": wins,
            "rate": wins / len(complete) if complete else None}


def run_fold(train: list[dict], test: list[dict], arm: str, epochs: int, seed: int,
             fold: str, output: Path) -> tuple[list[dict], list[dict]]:
    if {r["source_id"] for r in train} & {r["source_id"] for r in test}:
        raise ValueError("Clean source group crosses train/test boundary")
    torch.manual_seed(seed)
    net = TypedFusion()
    optimizer = torch.optim.AdamW(net.parameters(), lr=3e-4, weight_decay=1e-3)
    weights = weights_for(train)
    for epoch in range(epochs):
        net.train()
        total = 0.0
        for idx in torch.randperm(len(train)).tolist():
            optimizer.zero_grad(set_to_none=True)
            output_row = net(train[idx], arm)
            loss = training_loss(output_row, train[idx]["label"], arm) * weights[idx]
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            optimizer.step()
            total += float(loss.detach())
        print(f"{arm}/{fold} epoch {epoch + 1}/{epochs}: loss={total / len(train):.4f}", flush=True)
    output.mkdir(parents=True, exist_ok=True)
    torch.save(net.state_dict(), output / f"{arm}_{fold}.pt")
    net.eval()
    rows, regions = [], []
    with torch.no_grad():
        for item in test:
            prediction = net(item, arm)
            prob = float(prediction["logit"].sigmoid())
            row = {"fold": fold, "family": item["family"], "benchmark": item["benchmark"],
                   "side": item["side"], "true_label": item["label"],
                   "predicted_label": int(prob >= 0.5), "prob_trojan": prob}
            for key in ("graph_logit", "rtl_logit", "region_logit"):
                if key in prediction:
                    row[key.replace("logit", "prob")] = float(prediction[key].sigmoid())
            if arm == "fusion":
                row["gate_weights"] = prediction["gate_weights"].tolist()
                row["alignment_coverage"] = float(prediction["alignment_coverage"])
                regions.append({"benchmark": item["benchmark"], "side": item["side"], "fold": fold,
                                "status": "weakly_supervised_unreviewed",
                                "chunk_probabilities": prediction["region_logits"].sigmoid().tolist()})
            rows.append(row)
    return rows, regions


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", choices=["graph", "rtl", "structured", "fusion"], required=True)
    ap.add_argument("--setting", choices=["cv", "external", "all"], default="all")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ablate", choices=["none", "rtl_struct", "graph_handcrafted", "alignment"],
                    default="none", help="Remove one input group for a matched importance pilot")
    args = ap.parse_args()
    if args.epochs < 1:
        ap.error("epochs must be positive")
    torch.set_num_threads(4)
    samples, manifest_sha = load_data()
    if args.ablate == "rtl_struct":
        for item in samples:
            item["struct"].zero_()
    elif args.ablate == "graph_handcrafted":
        for item in samples:
            item["graph"].x[:, 16:].zero_()
    elif args.ablate == "alignment":
        for item in samples:
            item["links"] = item["links"][:, :0]
            item["weights"] = item["weights"][:0]
    folds = json.loads((ROOT / "data/integrated/group_folds.json").read_text())["folds"]
    jobs = []
    if args.setting in ("cv", "all"):
        for fold in folds:
            test_names = set(fold["test_benchmarks"])
            train = [r for r in samples if r["benchmark"] not in EXTERNAL and r["benchmark"] not in test_names]
            test = [r for r in samples if r["benchmark"] in test_names]
            jobs.append((str(fold["fold"]), train, test, args.seed + fold["fold"]))
    if args.setting in ("external", "all"):
        jobs.append(("external", [r for r in samples if r["benchmark"] not in EXTERNAL],
                     [r for r in samples if r["benchmark"] in EXTERNAL], args.seed))
    suffix = "" if args.ablate == "none" else f"_without_{args.ablate}"
    target = OUT / "training" / f"{args.arm}_{args.setting}_{args.epochs}ep_seed{args.seed}{suffix}"
    target.mkdir(parents=True, exist_ok=True)
    protocol = {"status": "running", "model": "typed_fusion_v1", "arm": args.arm, "setting": args.setting,
                "epochs": args.epochs, "seed": args.seed, "ablation": args.ablate,
                "manifest_sha256": manifest_sha,
                "folds": [name for name, *_ in jobs], "threshold": 0.5,
                "weighting": "equal family/class/unique clean-source contribution",
                "scope": "previously inspected development and two-host diagnostic; no gate ground truth"}
    (target / "protocol.json").write_text(json.dumps(protocol, indent=2))
    all_rows, all_regions = [], []
    for name, train, test, seed in jobs:
        print(f"{args.arm}/{name}: train={len(train)} test={len(test)}", flush=True)
        rows, regions = run_fold(train, test, args.arm, args.epochs, seed, name, target)
        all_rows += rows; all_regions += regions
        (target / "predictions.partial.json").write_text(json.dumps(all_rows, indent=2))
    (target / "predictions.json").write_text(json.dumps(all_rows, indent=2))
    if all_regions:
        (target / "region_candidates.json").write_text(json.dumps(all_regions, indent=2))
    summary = {}
    for name, *_ in jobs:
        rows = [r for r in all_rows if r["fold"] == name]
        metric_rows = [{**r, "fold": 0} for r in rows]
        summary[name] = {"metrics": summarize_predictions(metric_rows)["pooled"], "pairwise": pairwise(rows)}
    protocol["status"] = "completed"
    (target / "protocol.json").write_text(json.dumps(protocol, indent=2))
    (target / "summary.json").write_text(json.dumps({"status": "completed_exploratory",
        "protocol": protocol, "results": summary}, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
