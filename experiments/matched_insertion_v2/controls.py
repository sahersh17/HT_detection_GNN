"""Frozen leave-one-host-out shortcut probes for the four-host pilot."""
import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from lofo_graph_baselines import fit_predict, stats, wl  # noqa: E402
from metrics import summarize  # noqa: E402
from train_cv import _safe_classes  # noqa: E402

OUT = ROOT / "runs/matched_insertion_v2"


def load_rows():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    if len(manifest["selected_hosts"]) != 4 or len(manifest["records"]) != 12:
        raise ValueError("Expected frozen four-host, three-variant pilot")
    rows = []
    for row in manifest["records"]:
        path = OUT / row["host"] / row["variant"] / "graph.pt"
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["graph_sha256"]:
            raise ValueError(f"Graph changed: {path}")
        with torch.serialization.safe_globals(_safe_classes()):
            graph = torch.load(path, map_location="cpu", weights_only=True)
        rows.append({**row, "graph": graph})
    return rows


def bootstrap_host_mean(values, seed=42):
    torch.manual_seed(seed)
    n = len(values)
    draws = torch.randint(n, (2000, n))
    means = torch.tensor(values)[draws].float().mean(1)
    return [float(torch.quantile(means, p)) for p in (.025, .975)]


def input_fanout_motifs(row):
    """Count primary-input fanout motifs without names or synthetic-cell IDs."""
    path = OUT / row["host"] / row["variant"] / "yosys.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    module = document["modules"][row["top"]]
    input_bits = {bit for port in module["ports"].values() if port["direction"] == "input"
                  for bit in port["bits"] if isinstance(bit, int)}
    counts = {bit: [0, 0] for bit in input_bits}
    for cell in module["cells"].values():
        for pin, direction in cell["port_directions"].items():
            if direction != "input":
                continue
            for bit in cell["connections"][pin]:
                if bit in counts:
                    counts[bit][int(cell["type"] != "$_NOT_")] += 1
    hist = torch.zeros(16, dtype=torch.float32)
    for not_count, other_count in counts.values():
        hist[min(not_count, 3) * 4 + min(other_count, 3)] += 1
    return hist


def output_xor_motifs(row):
    """Count repeated versus distinct XOR controls in real output cones."""
    path = OUT / row["host"] / row["variant"] / "yosys.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    module = document["modules"][row["top"]]
    drivers = {bit: cell for cell in module["cells"].values()
               for pin, direction in cell["port_directions"].items() if direction == "output"
               for bit in cell["connections"][pin] if isinstance(bit, int)}
    counts = torch.zeros(2, dtype=torch.float32)
    for port in module["ports"].values():
        if port["direction"] != "output":
            continue
        for bit in port["bits"]:
            outer = drivers.get(bit)
            if outer is None or outer["type"] != "$_XOR_":
                continue
            for input_pin, trigger_pin in (("A", "B"), ("B", "A")):
                inner = drivers.get(outer["connections"][input_pin][0])
                if inner is not None and inner["type"] == "$_XOR_":
                    trigger = outer["connections"][trigger_pin][0]
                    prior = [inner["connections"][p][0] for p in ("A", "B")]
                    counts[int(trigger not in prior)] += 1
                    break
    return counts


def main():
    rows = load_rows()
    hosts = sorted({r["host"] for r in rows})
    graphs = [r["graph"] for r in rows]
    vectors = {
        "node_edge_count": torch.stack([torch.log1p(torch.tensor([g.num_nodes, g.num_edges],
                                                        dtype=torch.float32)) for g in graphs]),
        "gate_type_count": torch.stack([g.x[:, :-4].sum(0) for g in graphs]),
        "graph_statistics": torch.stack([stats(g) for g in graphs]),
        "directed_wl2": torch.stack([wl(g) for g in graphs]),
        "input_fanout_motifs": torch.stack([input_fanout_motifs(r) for r in rows]),
        "output_xor_motifs": torch.stack([output_xor_motifs(r) for r in rows]),
    }
    report = {"status": "exploratory_four_host_pilot", "n_hosts": 4,
              "training": "leave one host out, fixed regularized linear probe",
              "cohorts": {}}
    for negative in ("clean_matched", "decoy"):
        cohort = [i for i, row in enumerate(rows) if row["variant"] in (negative, "trojan")]
        results = {}
        for method, matrix in vectors.items():
            predictions = []
            for fold, host in enumerate(hosts):
                train = [i for i in cohort if rows[i]["host"] != host]
                test = [i for i in cohort if rows[i]["host"] == host]
                labels = torch.tensor([int(rows[i]["variant"] == "trojan") for i in train])
                scores = fit_predict(matrix[train], labels, torch.ones(len(train)), matrix[test], 42 + fold)
                predictions.extend({"host": host, "variant": rows[i]["variant"],
                    "true_label": int(rows[i]["variant"] == "trojan"), "score": float(score)}
                    for i, score in zip(test, scores))
            pairwise = {}
            for host in hosts:
                scores = {r["variant"]: r["score"] for r in predictions if r["host"] == host}
                pairwise[host] = (1.0 if scores["trojan"] > scores[negative] else
                                  0.5 if scores["trojan"] == scores[negative] else 0.0)
            y = [r["true_label"] for r in predictions]
            p = [int(r["score"] >= 0.5) for r in predictions]
            summary = summarize(y, p, [r["score"] for r in predictions])
            summary["equal_host_pairwise_auc"] = sum(pairwise.values()) / len(pairwise)
            summary["host_bootstrap_95ci"] = bootstrap_host_mean(list(pairwise.values()))
            results[method] = {"summary": summary, "pairwise_by_host": pairwise,
                               "predictions": predictions}
        report["cohorts"][f"{negative}_versus_trojan"] = results
    (OUT / "controls.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for cohort, methods in report["cohorts"].items():
        for method, result in methods.items():
            print(cohort, method, result["summary"]["equal_host_pairwise_auc"],
                  result["summary"]["host_bootstrap_95ci"])


if __name__ == "__main__":
    main()
