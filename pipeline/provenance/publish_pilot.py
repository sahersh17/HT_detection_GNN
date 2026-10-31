"""Publish portable provenance_v1 pilot predictions and exact input hashes.

Run after all three --dataset provenance training runs finish:
  python pipeline/provenance/publish_pilot.py
"""
import argparse
import hashlib
import json
import shutil
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from metrics import summarize_predictions  # noqa: E402


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def publish(dataset="provenance"):
    graph_root = ROOT / "runs" / "provenance_v1"
    verification = json.loads((graph_root / "verification.json").read_text(encoding="utf-8"))
    if verification["status"] != "verified" or verification["graphs"] != 42:
        raise ValueError("Run the complete 42-graph verifier before publishing the pilot")
    destination = ROOT / "results" / f"{dataset}_pilot"
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    inputs = [ROOT / "data" / "integrated" / "paired_manifest.json",
              ROOT / "data" / "integrated" / "group_folds.json",
              ROOT / "data" / "HT_data_2026-10-31_b40cc08.zip"]
    inputs += sorted(graph_root.rglob("graph.pt"))
    inputs += sorted(graph_root.rglob("metadata.json"))
    inputs += sorted(graph_root.rglob("yosys.json"))
    if dataset == "provenance_clean":
        rtl_root = ROOT / "runs" / "rtl_clean_v1"
        rtl_verification = json.loads((rtl_root / "verification.json").read_text(encoding="utf-8"))
        if rtl_verification["status"] != "verified" or rtl_verification["samples"] != 42:
            raise ValueError("Run the complete clean-RTL verifier before publishing")
        inputs += [rtl_root / "manifest.json", rtl_root / "verification.json"]
        inputs += sorted(rtl_root.glob("*.pt"))
    for path in inputs:
        hashes[path.relative_to(ROOT).as_posix()] = digest(path)
    models = ("rtl", "gnn", "fusion", "length", "graph_size") if dataset == "provenance_clean" else ("rtl", "gnn", "fusion")
    for model in models:
        source = ROOT / "runs" / f"{dataset}_{model}"
        rows = json.loads((source / "predictions.json").read_text(encoding="utf-8"))
        summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
        if len(rows) != 42 or (model not in ("length", "graph_size") and summary["args"]["dataset"] != dataset):
            raise ValueError(f"Incomplete or wrong-version result for {model}")
        if summarize_predictions(rows)["pooled"] != summary["pooled"]:
            raise ValueError(f"Saved metrics disagree with predictions: {model}")
        target = destination / model
        target.mkdir(exist_ok=True)
        for name in ("predictions.json", "summary.json"):
            shutil.copyfile(source / name, target / name)
    embedding_description = ("testbench-free CodeBERT embeddings with chunk-to-line spans"
                             if dataset == "provenance_clean" else "2026-10-31 packaged CodeBERT embeddings")
    provenance = {"dataset": f"provenance_v1 gate graphs + {embedding_description}",
                  "evaluation_status": ("exploratory_pilot" if dataset == "provenance_clean" else
                                        "superseded_testbench_inclusive_pilot"),
                  "testbenches_in_rtl_embeddings": dataset == "provenance",
                  "synthesis": "YoWASP Yosys 0.69, no ABC",
                  "yowasp_yosys_package": version("yowasp-yosys"),
                  "graphs": verification["graphs"], "nodes": verification["nodes"],
                  "source_covered_nodes": verification["source_covered_nodes"],
                  "reviewed_gate_labels": 0, "hashes": hashes}
    (destination / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return {"destination": str(destination), "hashed_inputs": len(hashes)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["provenance", "provenance_clean"], default="provenance")
    print(json.dumps(publish(parser.parse_args().dataset), indent=2))
