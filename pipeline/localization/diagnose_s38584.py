"""Exploratory structural ranking against unreviewed s38584 candidate labels."""
import json
import sys
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "pipeline"))
from eval_loc import evaluate  # noqa: E402
from train_cv import _safe_classes  # noqa: E402


def main():
    out = []
    for path in sorted((ROOT / "data/localization_gate_audit").glob("s38584-T*_candidate_labels.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        graph_path = ROOT / "runs" / record["graph_id"] / "graph.pt"
        with torch.serialization.safe_globals(_safe_classes()):
            graph = torch.load(graph_path, weights_only=True, map_location="cpu")
        if graph.num_nodes != len(record["node_names"]):
            raise ValueError(f"Graph/label length differs: {record['graph_id']}")
        src, dst = graph.edge_index
        degree = torch.bincount(src, minlength=graph.num_nodes) + torch.bincount(dst, minlength=graph.num_nodes)
        gate_class = graph.x[:, :-4].argmax(1)
        counts = torch.bincount(gate_class)
        rarity = (1 / counts[gate_class].float()).tolist()
        methods = {"degree": degree.float().tolist(), "gate_class_rarity": rarity}
        out.append({"graph_id": record["graph_id"], "label_status": record["audit"]["label_status"],
                    "known_positives": record["labels"].count(1), "known_negatives": record["labels"].count(0),
                    "unknown": record["labels"].count(-1),
                    "methods": {name: {"node_auroc": evaluate(scores, record["labels"])["node_auroc"]}
                                for name, scores in methods.items()},
                    "note": "Discrete baseline scores have large ties; top-k and first-rank depend on arbitrary node order and are omitted."})
    target = ROOT / "data/localization_gate_audit/structural_diagnostic.json"
    target.write_text(json.dumps(out, indent=2), encoding="utf-8")
    for row in out:
        print(row["graph_id"], row["known_positives"], row["known_negatives"], row["unknown"],
              {name: round(result["node_auroc"], 3)
               for name, result in row["methods"].items()})


if __name__ == "__main__":
    main()
