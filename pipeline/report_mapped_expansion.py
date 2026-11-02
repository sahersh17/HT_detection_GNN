"""Aggregate complete mapped-host LOFO results without selecting on held-out folds."""
import json
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "data/lofo_expanded"
RUNS = ROOT / "runs/lofo_integrated/lofo_expanded"


def interval(values, rng, repeats=10000):
    draws = sorted(sum(rng.choice(values) for _ in values)/len(values) for _ in range(repeats))
    return [draws[250], draws[9749]]


def main():
    baseline = json.loads((COHORT / "baselines_mapped/graph_baselines.json").read_text())
    families = sorted(baseline["summary"]["size"])
    runs = []
    for seed in (42, 43, 44, 45, 46):
        folder = RUNS / f"mapped_seed_{seed}_scaled_source_balanced"
        protocol = json.loads((folder / "protocol.json").read_text())
        if protocol["status"] != "completed_family_LOFO":
            raise ValueError(f"Incomplete GNN run: {folder}")
        result = json.loads((folder / "results.json").read_text())
        if sorted(result["per_family_rank_metrics"]) != families:
            raise ValueError(f"Family mismatch: {folder}")
        runs.append({"seed": seed, "families": {f: result["per_family_rank_metrics"][f]["auroc"] for f in families},
                     "pooled_auroc": result["metrics"]["pooled"]["auroc"]})
    rng = random.Random(42)
    models = {}
    for name, per in baseline["summary"].items():
        values = [per[f]["auroc"] for f in families]
        models[name] = {"equal_host_mean_auroc": statistics.mean(values),
                        "host_bootstrap_95_percentile": interval(values, rng),
                        "per_host": {f: per[f]["auroc"] for f in families}}
    seed_means = [statistics.mean(run["families"].values()) for run in runs]
    per_host = {f: statistics.mean(run["families"][f] for run in runs) for f in families}
    models["gnn_scaled"] = {"equal_host_mean_auroc": statistics.mean(seed_means),
                             "seed_std": statistics.stdev(seed_means),
                             "host_bootstrap_95_percentile": interval(list(per_host.values()), rng),
                             "per_host_mean": per_host, "per_seed_equal_host_mean": seed_means,
                             "per_seed_pooled_auroc": [run["pooled_auroc"] for run in runs]}
    comparisons = {}
    for name, baseline_model in models.items():
        if name == "gnn_scaled":
            continue
        differences = [per_host[f]-baseline_model["per_host"][f] for f in families]
        # Resample hosts and seeds together; uncertainty is still poorly
        # resolved with five related hosts and five seeds.
        draws = []
        for _ in range(10000):
            sampled_hosts = [rng.choice(families) for _ in families]
            sampled_seeds = [rng.choice(runs) for _ in runs]
            gnn = statistics.mean(statistics.mean(run["families"][f] for run in sampled_seeds)
                                  for f in sampled_hosts)
            control = statistics.mean(baseline_model["per_host"][f] for f in sampled_hosts)
            draws.append(gnn-control)
        draws.sort()
        comparisons[name] = {"mean_difference": statistics.mean(differences),
                             "host_seed_bootstrap_95_percentile": [draws[250], draws[9749]]}
    report = {"status": "development_inspected_hosts", "cohort": "data/lofo_expanded/protocol.json",
              "families": families, "seeds": [42, 43, 44, 45, 46], "models": models,
              "gnn_minus_controls": comparisons,
              "limitations": ["Five host families; s15850 has one pair", "All families inspected before this report",
                              "B15 synthesis differs from the other mapped netlists",
                              "s38584-T300 has a documented trigger/payload disconnection",
                              "Host bootstrap intervals are descriptive at n=5"]}
    (COHORT / "mapped_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, model in models.items():
        print(name, round(model["equal_host_mean_auroc"], 3), model["host_bootstrap_95_percentile"])


if __name__ == "__main__":
    main()
