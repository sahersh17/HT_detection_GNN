"""Export aligned fusion attention rankings for later reviewed-label scoring.

Usage: python pipeline/provenance/export_attention_scores.py
These scores are exploratory hypotheses, not localization accuracy.
"""
import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def export(node_outputs, graph_root, destination):
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(node_outputs.glob("*_trojan.npz")):
        with np.load(path, allow_pickle=False) as arrays:
            names = arrays["node_names"].tolist()
            graph_id = str(arrays["graph_id"].item())
            attention = arrays["rtl_to_graph_attention"]
        if attention.ndim != 2 or attention.shape[1] != len(names):
            raise ValueError(f"Attention/node length mismatch: {path}")
        benchmark = graph_id.split("/")[1]
        metadata = json.loads((graph_root / benchmark / "trojan" / "metadata.json").read_text(encoding="utf-8"))
        if graph_id != metadata["graph_id"] or names != metadata["node_names"]:
            raise ValueError(f"Attention/graph row alignment mismatch: {path}")
        scores = attention.mean(axis=0).astype(float).tolist()
        record = {"graph_id": graph_id, "node_names": names, "scores": scores,
                  "method": "fusion RTL-to-graph attention, mean over RTL chunks",
                  "evaluation_status": "unscored_candidate"}
        (destination / f"{benchmark}.json").write_text(json.dumps(record), encoding="utf-8")
        rows.append({"graph_id": graph_id, "nodes": len(names), "chunks": int(attention.shape[0])})
    if not rows:
        raise ValueError(f"No Trojan attention files under {node_outputs}")
    return {"exported": len(rows), "graphs": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-outputs", type=Path, default=ROOT / "runs" / "provenance_fusion" / "node_outputs")
    parser.add_argument("--graph-root", type=Path, default=ROOT / "runs" / "provenance_v1")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "provenance_fusion" / "attention_scores")
    args = parser.parse_args()
    summary = export(args.node_outputs, args.graph_root, args.out)
    print(json.dumps({"exported": summary["exported"]}, indent=2))


if __name__ == "__main__":
    main()
