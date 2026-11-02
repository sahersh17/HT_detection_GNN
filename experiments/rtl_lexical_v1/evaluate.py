"""Run the frozen three-group RTL classifier on original and lexical controls."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import summarize_predictions  # noqa: E402

OUT = ROOT / "runs/rtl_lexical_v1"
ARMS = ("original", "comments", "names", "both")


def feature(benchmark, side, arm):
    folder = ROOT / "runs/rtl_clean_v1" if arm == "original" else OUT / "embeddings" / arm
    path = folder / f"{benchmark}_{side}.pt"
    if not path.exists():
        raise FileNotFoundError(path)
    tensor = torch.load(path, map_location="cpu", weights_only=True).float()
    return torch.cat((tensor.mean(0), tensor.max(0).values))


def fit(x, labels, seed):
    torch.manual_seed(seed)
    mean, std = x.mean(0), x.std(0).clamp(min=1e-6)
    x = (x - mean) / std
    linear = torch.nn.Linear(x.shape[1], 2)
    weights = torch.bincount(labels, minlength=2).float()
    weights = weights.sum() / (2 * weights.clamp(min=1))
    optimizer = torch.optim.LBFGS(linear.parameters(), max_iter=100)

    def closure():
        optimizer.zero_grad()
        loss = F.cross_entropy(linear(x), labels, weight=weights)
        loss.backward()
        return loss

    optimizer.step(closure)
    return linear, mean, std


def predict(linear, mean, std, x):
    with torch.no_grad():
        return torch.softmax(linear((x - mean) / std), -1)[:, 1].tolist()


def paired_ranking(rows):
    scores = {}
    for row in rows:
        scores.setdefault(row["benchmark"], {})[row["true_label"]] = row["prob_trojan"]
    valid = [pair for pair in scores.values() if set(pair) == {0, 1}]
    wins = sum(pair[1] > pair[0] for pair in valid)
    ties = sum(pair[1] == pair[0] for pair in valid)
    return {"pairs": len(valid), "wins": wins, "ties": ties,
            "win_rate_with_half_ties": (wins + 0.5 * ties) / len(valid) if valid else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", action="append", choices=ARMS)
    args = ap.parse_args()
    samples = json.loads((ROOT / "data/integrated/paired_manifest.json").read_text(encoding="utf-8"))["samples"]
    folds = json.loads((ROOT / "data/integrated/group_folds.json").read_text(encoding="utf-8"))["folds"]
    selected = args.arm or ARMS
    if any(arm != "original" for arm in selected):
        verification = json.loads((OUT / "verification.json").read_text(encoding="utf-8"))
        if len(verification["checks"]) != 126 or verification["passed"] != 126:
            raise ValueError("Full transformed-source compilation has not passed")
        progress = json.loads((OUT / "embedding_progress.json").read_text(encoding="utf-8"))
        available = {(r["benchmark"], r["side"], r["arm"]) for r in progress["records"]}
        required = {(s["benchmark"], s["class_name"], arm) for s in samples
                    for arm in selected if arm != "original"}
        if not required.issubset(available):
            raise ValueError(f"Embeddings incomplete: {len(required - available)} missing")
    all_features = {(s["benchmark"], s["class_name"], arm): feature(s["benchmark"], s["class_name"], arm)
                    for s in samples for arm in selected if arm != "original"}
    # Always load the original arm for the frozen-train transfer evaluation.
    all_features.update({(s["benchmark"], s["class_name"], "original"):
                         feature(s["benchmark"], s["class_name"], "original") for s in samples})
    rows = []
    for arm in selected:
        for setting in (["within", "original_to_control"] if arm != "original" else ["within"]):
            for fold in folds:
                train = [s for s in samples if s["benchmark"] in fold["train_benchmarks"]]
                test = [s for s in samples if s["benchmark"] in fold["test_benchmarks"]]
                tr_arm = "original" if setting == "original_to_control" else arm
                x_tr = torch.stack([all_features[(s["benchmark"], s["class_name"], tr_arm)] for s in train])
                x_te = torch.stack([all_features[(s["benchmark"], s["class_name"], arm)] for s in test])
                model, mean, std = fit(x_tr, torch.tensor([s["label"] for s in train]), 42 + fold["fold"])
                for sample, score in zip(test, predict(model, mean, std, x_te)):
                    rows.append({"arm": arm, "setting": setting, "fold": fold["fold"],
                                 "benchmark": sample["benchmark"], "true_label": sample["label"],
                                 "predicted_label": int(score >= 0.5), "prob_trojan": score})
    summary = {}
    for arm in selected:
        for setting in (["within", "original_to_control"] if arm != "original" else ["within"]):
            group = [r for r in rows if r["arm"] == arm and r["setting"] == setting]
            summary[f"{arm}/{setting}"] = summarize_predictions(group)
            summary[f"{arm}/{setting}"]["paired_ranking"] = paired_ranking(group)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ablation_predictions.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (OUT / "ablation_summary.json").write_text(json.dumps({"status": "exploratory_development_folds",
        "independent_clean_source_groups": 3, "threshold": 0.5, "feature": "CodeBERT chunk mean+max",
        "result": summary}, indent=2), encoding="utf-8")
    if set(selected) == set(ARMS):
        evidence = ROOT / "data/rtl_lexical_v1"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "predictions.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        provenance = {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
                      for name in ("manifest.json", "verification.json", "embedding_progress.json")}
        (evidence / "summary.json").write_text(json.dumps({"status": "exploratory_development_folds",
            "independent_clean_source_groups": 3, "n_design_sides": len(samples),
            "model": "microsoft/codebert-base", "threshold": 0.5,
            "source_artifact_hashes": provenance, "results": summary}, indent=2), encoding="utf-8")
    for key, value in summary.items():
        print(key, value["pooled"])


if __name__ == "__main__":
    main()
