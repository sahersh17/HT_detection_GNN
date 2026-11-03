"""Compare original single-circuit updates with host/class-balanced gradient batches."""
import argparse
import hashlib
import json
import math
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from models import GNNOnly, CrossAttentionFusion
from metrics import summarize

RUN = ROOT / "runs/training_audit_v3"
OUT = ROOT / "data/training_audit_v3"


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False))


def forward(model, item, arm):
    if arm == "fusion":
        return model(item["graph"], item["rtl"], return_attention=False)["logits"]
    return model(item["graph"], item["rtl"])["logits"]


def family_weights(items):
    counts = Counter((item["host"], item["label"]) for item in items)
    families = {item["host"] for item in items}
    return [len(items) / (len(families) * 2 * counts[item["host"], item["label"]])
            for item in items]


def predictions(model, items, arm):
    model.eval()
    output = []
    with torch.no_grad():
        for item in items:
            probability = float(forward(model, item, arm).softmax(-1)[0, 1])
            if not math.isfinite(probability):
                raise ValueError("Nonfinite probability")
            output.append(dict(host=item["host"], benchmark=item["benchmark"],
                               variant=item["variant"], label=item["label"], probability=probability))
    return output


def metrics(rows, threshold=0.5):
    labels = [row["label"] for row in rows]
    scores = [row["probability"] for row in rows]
    pooled = summarize(labels, [int(p >= threshold) for p in scores], scores)
    hosts = {}
    for host in sorted({row["host"] for row in rows}):
        part = [row for row in rows if row["host"] == host]
        y = [row["label"] for row in part]
        p = [row["probability"] for row in part]
        hosts[host] = summarize(y, [int(value >= threshold) for value in p], p)
    return dict(pooled=pooled, hosts=hosts,
                equal_host_auc=float(np.mean([value["auroc"] for value in hosts.values()])),
                equal_host_ba=float(np.mean([value["balanced_accuracy"] for value in hosts.values()])),
                score_range=[min(scores), max(scores)])


def training_threshold(rows):
    candidates = [0.0, 0.5, 1.0]
    scores = sorted({row["probability"] for row in rows})
    candidates.extend((a + b) / 2 for a, b in zip(scores, scores[1:]))
    weights = family_weights(rows)
    def objective(threshold):
        correct = sum(weight for row, weight in zip(rows, weights)
                      if int(row["probability"] >= threshold) == row["label"]) / len(rows)
        return correct, -abs(threshold - 0.5)
    return max(candidates, key=objective)


def evaluate(model, train, test, arm):
    train_rows = predictions(model, train, arm)
    test_rows = predictions(model, test, arm)
    threshold = training_threshold(train_rows)
    weights = family_weights(train_rows)
    nll = sum(-weight * math.log(max(1e-12, row["probability"] if row["label"]
                                    else 1 - row["probability"]))
              for row, weight in zip(train_rows, weights)) / len(train_rows)
    return dict(train=metrics(train_rows), test=metrics(test_rows),
                train_balanced_nll=nll, training_threshold=threshold,
                test_training_threshold=metrics(test_rows, threshold),
                train_predictions=train_rows, test_predictions=test_rows)


def balanced_batches(train, generator, host_batch_size):
    groups = defaultdict(lambda: defaultdict(list))
    for index, item in enumerate(train):
        groups[item["host"]][item["label"]].append(index)
    hosts = sorted(groups)
    generator.shuffle(hosts)
    for start in range(0, len(hosts), host_batch_size):
        batch = []
        for host in hosts[start:start + host_batch_size]:
            batch.extend(generator.choice(groups[host][label]) for label in (0, 1))
        yield batch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--report-dir", type=Path)
    arguments = parser.parse_args()
    if arguments.manifest and (not arguments.run_dir or not arguments.report_dir):
        parser.error("A custom manifest requires --run-dir and --report-dir")
    manifest_path = arguments.manifest or OUT / "manifest.json"
    run_directory = arguments.run_dir or RUN
    report_directory = arguments.report_dir or OUT
    run_directory.mkdir(parents=True, exist_ok=True)
    report_directory.mkdir(parents=True, exist_ok=True)
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    seed_filter = set(arguments.seeds) if arguments.seeds else None
    torch.set_num_threads(4)
    protocol = read(ROOT / "experiments/training_audit_v3/protocol.json")
    manifest = read(manifest_path)
    items = []
    for row in manifest["records"]:
        path = ROOT / row["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(str(path))
        item = torch.load(path, weights_only=False)
        if not torch.isfinite(item["graph"].x).all() or not torch.isfinite(item["rtl"]).all():
            raise ValueError("Invalid input")
        items.append(item)
    train = [item for item in items if item["cohort"] != "test"]
    test = [item for item in items if item["cohort"] == "test"]
    if {item["host"] for item in train} & {item["host"] for item in test}:
        raise ValueError("Host leakage")
    weights = family_weights(train)
    node_dim = train[0]["graph"].x.shape[1]
    if any(item["graph"].x.shape[1] != node_dim for item in items):
        raise ValueError("Mixed graph feature schemas")
    protocol = dict(protocol, graph_manifest=str(manifest_path), node_dim=node_dim,
                    graph_representation=manifest.get("representation", "legacy"),
                    graph_schema_sha256=manifest.get("schema_sha256"))
    all_results = []
    for arm, constructor in (("gnn", GNNOnly), ("fusion", CrossAttentionFusion)):
        for method in ("balanced", "legacy"):
            seeds = protocol[method + "_seeds"]
            for seed in seeds:
                if seed_filter is not None and seed not in seed_filter:
                    continue
                target = run_directory / f"{arm}_{method}_{seed}.json"
                if target.exists():
                    previous = read(target)
                    if arguments.manifest and previous.get("manifest_sha256") != manifest_sha256:
                        raise ValueError("Existing result uses a different graph manifest")
                    all_results.append(previous)
                    continue
                torch.manual_seed(seed)
                generator = random.Random(seed)
                model = constructor(node_dim=node_dim)
                optimizer = torch.optim.AdamW(model.parameters(), lr=protocol["learning_rate"],
                                              weight_decay=protocol["weight_decay"])
                curve = []
                checkpoints = {}
                seen = set()
                updates = 0
                start_time = time.monotonic()
                total_epochs = (protocol["legacy_epochs"][arm] if method == "legacy"
                                else protocol["epochs"])
                for epoch in range(1, total_epochs + 1):
                    model.train()
                    if method == "balanced":
                        batches = balanced_batches(train, generator, protocol["host_batch_size"])
                    else:
                        order = list(range(len(train)))
                        generator.shuffle(order)
                        batches = ([index] for index in order)
                    gradients = []
                    total_loss = []
                    for batch in batches:
                        optimizer.zero_grad(set_to_none=True)
                        for index in batch:
                            item = train[index]
                            seen.add(index)
                            loss = F.cross_entropy(forward(model, item, arm),
                                                   torch.tensor([item["label"]]))
                            factor = weights[index] if method == "legacy" else 1 / len(batch)
                            weighted = loss * factor
                            weighted.backward()
                            total_loss.append(float(loss.detach()))
                        gradient = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                        if not torch.isfinite(gradient):
                            raise ValueError("Nonfinite gradient")
                        gradients.append(float(gradient))
                        optimizer.step()
                        updates += 1
                    row = dict(epoch=epoch, loss_mean=float(np.mean(total_loss)),
                               gradient_mean=float(np.mean(gradients)),
                               gradient_max=max(gradients), updates=updates)
                    curve.append(row)
                    print(arm, method, seed, epoch, round(row["loss_mean"], 4),
                          round(time.monotonic() - start_time, 1), flush=True)
                    if epoch in protocol["checkpoints"]:
                        result = evaluate(model, train, test, arm)
                        checkpoints[str(epoch)] = result
                        save(run_directory / f"{arm}_{method}_{seed}_partial.json",
                             dict(curve=curve, checkpoints=checkpoints))
                        print("SCORE", arm, method, seed, epoch,
                              result["train"]["pooled"]["auroc"],
                              result["test"]["pooled"]["auroc"], flush=True)
                torch.save(model.state_dict(), run_directory / f"{arm}_{method}_{seed}.pt")
                result = dict(arm=arm, method=method, seed=seed, curve=curve,
                              checkpoints=checkpoints, final=checkpoints[str(total_epochs)],
                              seen_training_records=len(seen), train_records=len(train),
                              updates=updates, elapsed_seconds=time.monotonic() - start_time,
                              manifest_sha256=manifest_sha256, node_dim=node_dim)
                save(target, result)
                all_results.append(result)
    if seed_filter is None:
        save(report_directory / "training_results.json", dict(protocol=protocol,
             manifest_sha256=manifest_sha256, node_dim=node_dim, runs=all_results))


if __name__ == "__main__":
    main()
