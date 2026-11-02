"""Certify that the current gate-only graph cannot distinguish G1c variants."""
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline/provenance"))
from build import CELL_EXCLUDE  # noqa: E402
from train_cv import _safe_classes  # noqa: E402

OUT = ROOT / "runs/matched_insertion_v3"
PREFIX = "__matched_g1c_"


def load(host, variant):
    folder = OUT / host / variant
    document = json.loads((folder / "yosys.json").read_text(encoding="utf-8"))
    top = next(iter(document["modules"]))
    names = sorted(name for name, cell in document["modules"][top]["cells"].items()
                   if cell["type"].lower() not in CELL_EXCLUDE)
    with torch.serialization.safe_globals(_safe_classes()):
        graph = torch.load(folder / "graph.pt", map_location="cpu", weights_only=True)
    if len(names) != graph.num_nodes:
        raise ValueError("Graph/node order mismatch")
    return names, graph


def relabel(name, swaps):
    for first, second in swaps:
        a, b = PREFIX + first + "_", PREFIX + second + "_"
        if name.startswith(a):
            return b + name[len(a):]
        if name.startswith(b):
            return a + name[len(b):]
    return name


def check(host, target, swaps):
    names_a, graph_a = load(host, "clean_matched")
    names_b, graph_b = load(host, target)
    index_b = {name: i for i, name in enumerate(names_b)}
    permutation = [index_b[relabel(name, swaps)] for name in names_a]
    features_equal = torch.equal(graph_a.x, graph_b.x[permutation])
    source_edges = {(permutation[a], permutation[b]) for a, b in graph_a.edge_index.T.tolist()}
    target_edges = set(map(tuple, graph_b.edge_index.T.tolist()))
    return {"host": host, "comparison": f"clean_matched_to_{target}",
            "nodes": graph_a.num_nodes, "features_equal": features_equal,
            "directed_edges_equal": source_edges == target_edges,
            "isomorphic": features_equal and source_edges == target_edges}


def main():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    results = []
    for host in manifest["selected_hosts"]:
        results.append(check(host, "trojan", [("b", "c")]))
        results.append(check(host, "decoy", [("a", "c"), ("b", "d")]))
    (OUT / "isomorphism.json").write_text(json.dumps({"checks": results,
        "all_isomorphic": all(x["isomorphic"] for x in results)}, indent=2), encoding="utf-8")
    for result in results:
        print(result["host"], result["comparison"], result["isomorphic"])
    if not all(x["isomorphic"] for x in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
