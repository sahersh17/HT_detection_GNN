"""Compare frozen graph controls on the port-aware G1c diagnostic view."""
import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from lofo_graph_baselines import fit_predict, stats, wl  # noqa: E402
from train_cv import _safe_classes  # noqa: E402

OUT = ROOT / "runs/port_aware_v1"


def main():
    torch.set_num_threads(2)
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    records = []
    for row in manifest["records"]:
        path = OUT / row["host"] / row["variant"] / "graph.pt"
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["graph_sha256"]:
            raise ValueError(f"Graph changed: {path}")
        with torch.serialization.safe_globals(_safe_classes()):
            graph = torch.load(path, map_location="cpu", weights_only=True)
        records.append({**row, "graph": graph})
    hosts = sorted({row["host"] for row in records})
    if len(hosts) != 4 or len(records) != 12:
        raise ValueError("Expected four-host diagnostic")
    vectors = {"statistics": torch.stack([stats(row["graph"]) for row in records]),
               "directed_wl2": torch.stack([wl(row["graph"], rounds=2) for row in records]),
               "directed_wl8": torch.stack([wl(row["graph"], rounds=8) for row in records])}
    report = {"status": "diagnostic_only", "hosts": hosts, "cohorts": {}}
    report["wl8_first_differing_round"] = {}
    for host in hosts:
        by_variant = {r["variant"]: i for i, r in enumerate(records) if r["host"] == host}
        report["wl8_first_differing_round"][host] = {}
        for negative in ("clean_matched", "decoy"):
            a = vectors["directed_wl8"][by_variant[negative]].reshape(9, 512)
            b = vectors["directed_wl8"][by_variant["trojan"]].reshape(9, 512)
            differing = [round_ for round_ in range(9) if not torch.equal(a[round_], b[round_])]
            report["wl8_first_differing_round"][host][negative] = differing[0] if differing else None
    for negative in ("clean_matched", "decoy"):
        cohort = [i for i, row in enumerate(records) if row["variant"] in (negative, "trojan")]
        methods = {}
        for name, matrix in vectors.items():
            pairs = {}
            for fold, host in enumerate(hosts):
                train = [i for i in cohort if records[i]["host"] != host]
                test = [i for i in cohort if records[i]["host"] == host]
                labels = torch.tensor([int(records[i]["variant"] == "trojan") for i in train])
                scores = fit_predict(matrix[train], labels, torch.ones(len(train)), matrix[test], 42 + fold)
                by_variant = {records[i]["variant"]: float(score) for i, score in zip(test, scores)}
                pairs[host] = {"scores": by_variant,
                    "pairwise_auc": 1.0 if by_variant["trojan"] > by_variant[negative] else
                                    0.5 if by_variant["trojan"] == by_variant[negative] else 0.0}
            methods[name] = {"pairwise_by_host": pairs,
                "equal_host_pairwise_auc": sum(p["pairwise_auc"] for p in pairs.values()) / len(pairs)}
        report["cohorts"][negative + "_versus_trojan"] = methods
    (OUT / "probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for cohort, methods in report["cohorts"].items():
        for name, result in methods.items():
            print(cohort, name, result["equal_host_pairwise_auc"])
    print("first differing WL round", report["wl8_first_differing_round"])


if __name__ == "__main__":
    main()
