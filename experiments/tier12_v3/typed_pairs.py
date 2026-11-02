"""Check the actual typed fusion tensors, including directed edge attributes and multiplicity."""
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/"experiments/typed_fusion_v1"), str(ROOT/"pipeline/provenance")]
spec = importlib.util.spec_from_file_location("typed_provenance", ROOT/"pipeline/provenance/build.py")
provenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provenance)
from prepare import graph_view


def view(path, expected_hash):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError(f"Mapped artifact changed: {path}")
    design = json.loads(path.read_text())
    base, meta = provenance.graph_from_json(design, "top", "pair_check", 0)
    return graph_view(design, dict(meta, top="top"), base)


def distinguish(left, right):
    # Joint feature refinement. Different histograms prove non-isomorphism.
    # Equal histograms alone are inconclusive. Never use graph labels or IDs.
    colors = [list(map(tuple, data.x.tolist())) for data in (left, right)]
    neighbours = []
    for data in (left, right):
        edges = [[] for _ in range(data.num_nodes)]
        for (src,dst), attr in zip(data.edge_index.T.tolist(), data.edge_attr.tolist()):
            edges[dst].append((tuple(attr),src))
        neighbours.append(edges)
    for depth in range(max(map(len,colors))+1):
        if Counter(colors[0]) != Counter(colors[1]):
            return {"distinguished": True, "first_different_round": depth}
        previous = len(set(colors[0]))
        palette = {}
        colors = [[palette.setdefault((label,tuple(sorted((edge,labels[n]) for edge,n in adj))),
                                      len(palette)) for label,adj in zip(labels,edges)]
                  for labels,edges in zip(colors,neighbours)]
        if previous == len(palette):
            break
    return {"distinguished": None, "reason": "refinement inconclusive"}


def main():
    cohort = ROOT/"data/tier12_v2"
    rows = {(r["host"],r["variant"]):r for r in json.loads((cohort/"manifest.json").read_text())["records"]}
    pairs = json.loads((cohort/"decision.json").read_text())["gate_graph_collisions"]
    report = []
    for pair in pairs:
        host = pair["host"]
        graphs = [view(ROOT/"runs/tier12_v2"/host/side/"yosys.json",rows[host,side]["mapped_json_sha256"])
                  for side in (pair["negative"],"trojan")]
        report.append({"host":host, "negative":pair["negative"], "gate_only_isomorphic":pair["isomorphic"],
                       "typed":distinguish(*graphs), "nodes":[g.num_nodes for g in graphs],
                       "directed_edges":[g.num_edges for g in graphs]})
    (ROOT/"data/tier12_v3/typed_v2_pairs.json").write_text(json.dumps(report,indent=2)+"\n")
    print(report)


if __name__ == "__main__":
    main()
