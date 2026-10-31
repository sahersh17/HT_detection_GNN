"""Score node rankings only when their order matches reviewed gate labels.

Usage: python score_localization.py reviewed_labels.json score_files_dir output.json
Reviewed labels: {"designs": [{"graph_id": str, "node_names": [...],
  "labels": [-1/0/1, ...], "reviewed": true, "source": str}]}
Each score file: {"graph_id": str, "node_names": [...], "scores": [...]}.
"""
import json
import math
import sys
from pathlib import Path

from eval_loc import aggregate, evaluate


def score_one(label_record, score_record):
    if not label_record.get("reviewed"):
        raise ValueError(f"Unreviewed labels: {label_record['graph_id']}")
    if label_record["graph_id"] != score_record["graph_id"]:
        raise ValueError("Graph IDs differ")
    if label_record["node_names"] != score_record["node_names"]:
        raise ValueError(f"Node order differs: {label_record['graph_id']}")
    labels, scores = label_record["labels"], score_record["scores"]
    if len(labels) != len(scores) or len(labels) != len(label_record["node_names"]):
        raise ValueError("Node, label, and score lengths differ")
    if not all(math.isfinite(float(s)) for s in scores):
        raise ValueError("Non-finite localization score")
    result = evaluate(scores, labels)
    if result is None:
        raise ValueError(f"No known Trojan nodes: {label_record['graph_id']}")
    return {"graph_id": label_record["graph_id"], "label_source": label_record["source"], **result}


def main(labels_path, scores_dir, output_path):
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))["designs"]
    files = sorted(Path(scores_dir).glob("*.json"))
    scores = {r["graph_id"]: r for r in
              (json.loads(p.read_text(encoding="utf-8")) for p in files)}
    expected = {r["graph_id"] for r in labels}
    if expected != set(scores):
        raise ValueError(f"Missing scores: {sorted(expected - set(scores))}; "
                         f"unexpected scores: {sorted(set(scores) - expected)}")
    per_design = [score_one(r, scores[r["graph_id"]]) for r in labels]
    output = {"per_design": per_design, "macro": aggregate(per_design)}
    Path(output_path).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output["macro"], indent=2))


if __name__ == "__main__":
    main(*sys.argv[1:4])
