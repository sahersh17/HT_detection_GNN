"""Check whether the detector's gate features and directed edges distinguish siblings."""
import json
from collections import Counter, defaultdict

import networkx as nx
import torch

from train_cv import _safe_classes


def gate_graph(folder):
    with torch.serialization.safe_globals(_safe_classes()):
        data = torch.load(folder / "graph.pt", map_location="cpu", weights_only=True)
    graph = nx.DiGraph()
    graph.add_nodes_from((i, {"features": tuple(row)}) for i, row in enumerate(data.x.tolist()))
    graph.add_edges_from(data.edge_index.T.tolist())
    return graph


def isomorphic(left, right):
    if len(left) != len(right) or left.number_of_edges() != right.number_of_edges():
        return False
    # Joint directed color refinement prunes symmetric gate motifs before
    # exact matching. Different color histograms certify a difference.
    graphs = (left, right)
    colors = [{n: g.nodes[n]["features"] for n in g} for g in graphs]
    while True:
        if Counter(colors[0].values()) != Counter(colors[1].values()):
            return False
        previous_count = len(set(colors[0].values()))
        palette = {}
        refined = []
        for graph, labels in zip(graphs, colors):
            updated = {}
            for n in graph:
                key = (labels[n], tuple(sorted(labels[p] for p in graph.predecessors(n))),
                       tuple(sorted(labels[s] for s in graph.successors(n))))
                updated[n] = palette.setdefault(key, len(palette))
            refined.append(updated)
        colors = refined
        if len(palette) == previous_count:
            break
    # Try the saved node ordering within each color class, then verify every
    # directed edge. Failure of this candidate mapping is inconclusive.
    groups = []
    for labels in colors:
        by_color = defaultdict(list)
        for n, color in labels.items():
            by_color[color].append(n)
        groups.append(by_color)
    if Counter(colors[0].values()) != Counter(colors[1].values()):
        return False
    mapping = {a: b for color, nodes in groups[0].items()
               for a, b in zip(nodes, groups[1][color])}
    if all(right.has_edge(mapping[a], mapping[b]) for a, b in left.edges):
        return True
    return None


def compare(data_dir, run_dir):
    rows = json.loads((data_dir / "manifest.json").read_text())["records"]
    results = []
    for host in sorted({row["host"] for row in rows}):
        trojan = gate_graph(run_dir / host / "trojan")
        for negative in ("clean", "benign"):
            other = gate_graph(run_dir / host / negative)
            identical = isomorphic(trojan, other)
            results.append(dict(host=host, negative=negative, isomorphic=identical))
    return results
