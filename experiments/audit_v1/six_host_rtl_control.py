"""Exploratory six-host RTL-versus-metadata comparison on paired source data.

All six hosts have been inspected previously. Mixed Verilog/VHDL embeddings and
synthesis flows make these descriptive results, not a prospective final test.
"""
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import summarize, auroc  # noqa: E402

INVENTORY = ROOT / "data/audit_v1/host_inventory.json"
MANIFESTS = {
    "Verilog_early": ROOT / "runs/rtl_clean_v1/manifest.json",
    "Verilog_expansion": ROOT / "runs/rtl_expansion_v1/manifest.json",
    "VHDL_MC8051": ROOT / "runs/new_rtl_v1/manifest.json",
    "VHDL_b19": ROOT / "runs/b19_rtl_v1/manifest.json",
}
OUT = ROOT / "data/audit_v1"
ARMS = ("length", "chunks", "length_plus_chunks", "rtl_meanmax")
SEEDS = (42, 43, 44, 45, 46)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def average_precision(labels, scores):
    groups = defaultdict(list)
    for y, score in zip(labels, scores):
        groups[float(score)].append(int(y))
    positives = sum(labels)
    if not positives:
        return None
    seen = hits = area = 0
    for score in sorted(groups, reverse=True):
        group = groups[score]
        seen += len(group)
        hits += sum(group)
        area += (hits / seen) * sum(group) / positives
    return area


def source_sizes(record):
    paths = ([ROOT / record["source"]] if "source" in record else
             [ROOT / name for name in record["sources"]])
    expected = ([record["source_sha256"]] if "source" in record else
                list(record["sources"].values()))
    chars = lines = 0
    for path, digest in zip(paths, expected):
        if sha256(path) != digest:
            raise ValueError(f"Source changed: {path}")
        content = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        chars += len(content)
        lines += len(content.splitlines())
    return chars, lines


def load_samples():
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    complete = {benchmark: family["family"] for family in inventory["families"]
                for benchmark in family["rtl_complete_benchmarks"]}
    records = []
    for version, path in MANIFESTS.items():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for row in manifest["records"]:
            if row["benchmark"] not in complete:
                continue
            embedding = path.parent / row["embedding_file"]
            if sha256(embedding) != row["embedding_sha256"]:
                raise ValueError(f"Embedding changed: {embedding}")
            tensor = torch.load(embedding, map_location="cpu", weights_only=True).float()
            if tensor.shape != (row["num_chunks"], 768) or not torch.isfinite(tensor).all():
                raise ValueError(f"Invalid embedding: {embedding}")
            chars, lines = source_sizes(row)
            records.append({"benchmark": row["benchmark"], "family": complete[row["benchmark"]],
                            "side": row["side"], "label": int(row["side"] == "trojan"),
                            "version": version, "clean_source": None,
                            "source_text_sha256": row["source_text_sha256"],
                            "chars": chars, "lines": lines, "chunks": row["num_chunks"],
                            "features": {
                                "length": torch.tensor([math.log1p(chars), math.log1p(lines)]),
                                "chunks": torch.tensor([math.log1p(row["num_chunks"])]),
                                "length_plus_chunks": torch.tensor([math.log1p(chars), math.log1p(lines),
                                                                     math.log1p(row["num_chunks"])]),
                                "rtl_meanmax": torch.cat((tensor.mean(0), tensor.max(0).values))}})
    by_pair = defaultdict(dict)
    for row in records:
        if row["side"] in by_pair[row["benchmark"]]:
            raise ValueError("Duplicate RTL record")
        by_pair[row["benchmark"]][row["side"]] = row
    if len(complete) != len(by_pair) or any(set(sides) != {"clean", "trojan"} for sides in by_pair.values()):
        raise ValueError("Incomplete paired RTL cohort")
    for sides in by_pair.values():
        for row in sides.values():
            row["clean_source"] = sides["clean"]["source_text_sha256"]
    if len(records) != 72 or len({r["family"] for r in records}) != 6:
        raise ValueError("Expected 36 pairs across six hosts")
    return records


def fit_predict(train, test, arm, seed):
    torch.manual_seed(seed)
    x = torch.stack([r["features"][arm] for r in train])
    q = torch.stack([r["features"][arm] for r in test])
    y = torch.tensor([r["label"] for r in train], dtype=torch.long)
    by_host_source = Counter((r["family"], r["clean_source"]) for r in train)
    groups_by_host = Counter({family: len({r["clean_source"] for r in train if r["family"] == family})
                              for family in {r["family"] for r in train}})
    weights = torch.tensor([1 / (groups_by_host[r["family"]] * by_host_source[(r["family"], r["clean_source"])])
                            for r in train], dtype=torch.float32)
    weights /= weights.sum()
    mean = (weights[:, None] * x).sum(0)
    std = ((weights[:, None] * (x - mean).square()).sum(0).sqrt()).clamp(min=1e-6)
    x, q = (x - mean) / std, (q - mean) / std
    linear = torch.nn.Linear(x.shape[1], 2)
    optimizer = torch.optim.LBFGS(linear.parameters(), max_iter=100)

    def closure():
        optimizer.zero_grad()
        loss = (F.cross_entropy(linear(x), y, reduction="none") * weights).sum()
        loss.backward()
        return loss

    optimizer.step(closure)
    with torch.no_grad():
        return torch.softmax(linear(q), dim=-1)[:, 1].tolist()


def metrics(rows):
    y = [r["true_label"] for r in rows]
    score = [r["prob_trojan"] for r in rows]
    pred = [r["predicted_label"] for r in rows]
    result = summarize(y, pred, score)
    result["average_precision"] = average_precision(y, score)
    pairs = defaultdict(dict)
    for row in rows:
        pairs[row["benchmark"]][row["true_label"]] = row["prob_trojan"]
    wins = sum(sides[1] > sides[0] for sides in pairs.values())
    ties = sum(sides[1] == sides[0] for sides in pairs.values())
    result["paired_wins"] = wins
    result["paired_ties"] = ties
    result["paired_win_rate_half_ties"] = (wins + 0.5 * ties) / len(pairs)
    return result


def main():
    torch.set_num_threads(4)
    samples = load_samples()
    families = sorted({r["family"] for r in samples})
    predictions = []
    for seed in SEEDS:
        for arm in ARMS:
            for fold, held_out in enumerate(families):
                train = [r for r in samples if r["family"] != held_out]
                test = [r for r in samples if r["family"] == held_out]
                for row, score in zip(test, fit_predict(train, test, arm, seed + fold)):
                    predictions.append({"seed": seed, "arm": arm, "family": held_out,
                                        "benchmark": row["benchmark"], "true_label": row["label"],
                                        "predicted_label": int(score >= 0.5), "prob_trojan": float(score)})
            print(seed, arm, flush=True)
    path = OUT / "six_host_predictions.json"
    path.write_text(json.dumps(predictions, indent=2), encoding="utf-8")
    summary = {"status": "retrospective_inspected_mixed_flow_hosts",
               "protocol": "leave one entire host family out, weighted equally by host and clean source within host",
               "threshold": 0.5, "seeds": SEEDS, "arms": ARMS,
               "samples": len(samples), "paired_variants": len(samples) // 2,
               "hosts": families, "independent_clean_source_groups": len({(r["family"], r["clean_source"])
                                                                      for r in samples if r["label"] == 0}),
               "limitations": ["All hosts were inspected previously", "VHDL and Verilog text mixed",
                               "RTL encoder window boundaries differ by version", "Synthesis flows differ"],
               "input_sha256": {"inventory": sha256(INVENTORY),
                                **{name: sha256(path) for name, path in MANIFESTS.items()}},
               "predictions_sha256": sha256(path), "results": {}}
    for seed in SEEDS:
        summary["results"][str(seed)] = {}
        for arm in ARMS:
            selected = [r for r in predictions if r["seed"] == seed and r["arm"] == arm]
            per_host = {family: metrics([r for r in selected if r["family"] == family])
                        for family in families}
            summary["results"][str(seed)][arm] = {"pooled": metrics(selected),
                "equal_host_auroc": sum(per_host[f]["auroc"] for f in families) / len(families),
                "equal_host_paired_win_rate": sum(per_host[f]["paired_win_rate_half_ties"] for f in families) / len(families),
                "per_host": per_host}
    (OUT / "six_host_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for arm in ARMS:
        values = [summary["results"][str(seed)][arm]["equal_host_auroc"] for seed in SEEDS]
        print(arm, "equal-host AUROC", sum(values) / len(values), "seeds", values)


if __name__ == "__main__":
    main()
