"""One-way frozen-fold transfer check; train fold 4, score folds 0-3 once."""
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/dataset_stage3"))
from memorize_fold import CellPoolGNN
from train import LocalMIL, candidates, metrics, read, sha

torch.set_num_threads(2)
OUT = ROOT / "data/local_mil_v1"


def main():
    configs = {
        "prior_cell_pool_gnn": (CellPoolGNN(normalized_pool=True), ROOT / "data/dataset_stage3/memorization_fold4_normalized_state.pt"),
        "local_1layer_max": (LocalMIL(layers=1, readout="max"), OUT / "fold4_layers1_max.pt"),
        "local_2layer_topk": (LocalMIL(layers=2, readout="topk"), OUT / "fold4_layers2_topk.pt"),
        "local_2layer_attention": (LocalMIL(layers=2, readout="attention"), OUT / "fold4_layers2_attention.pt"),
        "local_2layer_topk_pretrain10": (LocalMIL(layers=2, readout="topk"), OUT / "fold4_layers2_topk_pretrain10.pt"),
    }
    models = {}
    for name, (model, state) in configs.items():
        missing, unexpected = model.load_state_dict(torch.load(state, weights_only=True, map_location="cpu"), strict=False)
        if unexpected or (missing and (name == "prior_cell_pool_gnn" or set(missing) != {"reconstruct_value.weight", "reconstruct_value.bias"})):
            raise ValueError(f"Incompatible checkpoint {name}: missing={missing}, unexpected={unexpected}")
        model.eval()
        models[name] = model
    folds = read("data/dataset_stage1/folds.json")["folds"]
    semantic = {r["key"]: r for r in read("data/semantic_graph_v1/manifest.json")["records"]}
    audit = {r["key"]: r for r in read("data/dataset_stage1/records.json")}
    outputs = {name: [] for name in models}
    with torch.no_grad():
        for fold in folds:
            if fold["fold"] == 4:
                continue
            for key in fold["test_keys"]:
                row = semantic[key]
                path = ROOT / row["file"]
                if sha(path) != row["sha256"] or row["sha256"] != audit[key]["semantic_sha256"]:
                    raise ValueError(f"Hash mismatch: {key}")
                item = torch.load(path, weights_only=False, map_location="cpu")
                graph = item["graph"]
                graph.x = graph.x.float()
                graph.edge_index = graph.edge_index.long()
                graph.edge_type = graph.edge_type.long()
                mask = candidates(graph.x, graph.n_cell)
                for name, model in models.items():
                    if name == "prior_cell_pool_gnn":
                        p = float(model(graph).softmax(-1)[0, 1])
                    else:
                        p = float(torch.sigmoid(model(graph, mask))[0])
                    outputs[name].append({"key": key, "fold": fold["fold"], "host": item["host"], "label": item["label"], "probability": p})
            print(f"Scored held-out development fold {fold['fold']}", flush=True)
    result = {"scope": "exploratory one-way transfer: models trained only on fold 4, evaluated on folds 0-3; not five-fold CV or final test", "training_fold": 4, "scored_folds": [0, 1, 2, 3], "folds_sha256": sha(ROOT / "data/dataset_stage1/folds.json"), "semantic_manifest_sha256": sha(ROOT / "data/semantic_graph_v1/manifest.json"), "models": {name: {"overall": metrics(rows), "by_fold": {str(f): metrics([r for r in rows if r["fold"] == f]) for f in range(4)}, "predictions": rows} for name, rows in outputs.items()}}
    (OUT / "transfer_from_fold4.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({name: result["models"][name]["overall"] for name in models}, indent=2), flush=True)


if __name__ == "__main__":
    main()
