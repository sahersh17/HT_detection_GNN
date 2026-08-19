from pathlib import Path
from collections import deque
import json
import pickle
import re

import torch
from torch_geometric.data import Data


def classify_gate_type(raw_type):
    """
    Collapses a raw synthesized cell name (standard-cell library name like
    'AND2X1'/'DFFARX1', or a Yosys internal primitive like '$_AND_') down to
    its underlying boolean/sequential function. See earlier discussion:
    this prevents the model from learning "which synthesis flow produced
    this graph" instead of real circuit structure.
    """
    t = raw_type.lstrip("\\").upper()

    patterns = [
        (r"DFF|LATCH",   "DFF"),
        (r"AOI",         "AOI"),
        (r"OAI",         "OAI"),
        (r"ISOL",        "ISOLATION"),
        (r"XNOR",        "XNOR"),
        (r"ANDNOT",      "ANDNOT"),
        (r"ORNOT",       "ORNOT"),
        (r"NAND",        "NAND"),
        (r"NOR",         "NOR"),
        (r"XOR",         "XOR"),
        (r"MUX|^MX\d",   "MUX"),
        (r"BUF",         "BUF"),
        (r"AND",         "AND"),
        (r"OR",          "OR"),
        (r"NOT|INV",     "NOT"),
    ]

    for pattern, label in patterns:
        if re.search(pattern, t):
            return label

    return "OTHER"


class FeatureExtractor:
    """
    Converts NetworkX gate-level graphs (built by GraphBuilder) into
    PyTorch Geometric Data objects, plus a parallel node-metadata store
    that keeps every node traceable back to its original gate name,
    raw cell type, functional class, and port connections.

    Node features (paper-8 style, hand-engineered + structural):
      - one-hot functional gate class
      - in-degree, out-degree
      - controllability proxy: shortest distance from a primary input
      - observability proxy: shortest distance to a primary output
    """

    UNK_TOKEN = "__UNK__"

    def __init__(self, gate_classes=None):
        self.gate_classes = gate_classes or []
        self._rebuild_index()

    def _rebuild_index(self):
        self.gate_class_to_idx = {gc: i for i, gc in enumerate(self.gate_classes)}
        self.unk_idx = len(self.gate_classes)
        self.vocab_size = len(self.gate_classes) + 1

    # ------------------------------------------------------------
    # Vocabulary — fit once across the whole dataset, then freeze
    # ------------------------------------------------------------

    def fit_vocab(self, gpickle_paths):
        seen = set()
        for path in gpickle_paths:
            with open(path, "rb") as f:
                G = pickle.load(f)
            for _, attrs in G.nodes(data=True):
                raw_type = attrs.get("gate_type", self.UNK_TOKEN)
                seen.add(classify_gate_type(raw_type))
        self.gate_classes = sorted(seen)
        self._rebuild_index()

    def save_vocab(self, path):
        with open(path, "w") as f:
            json.dump({"gate_classes": self.gate_classes}, f, indent=2)

    @classmethod
    def load_vocab(cls, path):
        with open(path, "r") as f:
            data = json.load(f)
        return cls(gate_classes=data["gate_classes"])

    # ------------------------------------------------------------
    # Structural metrics (paper-8 style: controllability / observability)
    # ------------------------------------------------------------

    @staticmethod
    def _bfs_distances(G, sources):
        """
        Multi-source BFS shortest-path distance from any node in `sources`
        to every other node, following edges in G's given direction.
        Unreached nodes get distance -1 (later mapped to a sentinel value,
        not silently treated as 0 — 0 would falsely mean 'primary input').
        """
        dist = {n: -1 for n in G.nodes()}
        q = deque()
        for s in sources:
            if dist[s] == -1:
                dist[s] = 0
                q.append(s)
        while q:
            u = q.popleft()
            for v in G.successors(u):
                if dist[v] == -1:
                    dist[v] = dist[u] + 1
                    q.append(v)
        return dist

    def _compute_controllability(self, G):
        """
        Proxy for SCOAP-style controllability: how many logic levels a
        signal is from a primary input. Primary inputs approximated as
        nodes with in_degree == 0 (nothing drives them within this graph).
        """
        primary_inputs = [n for n in G.nodes() if G.in_degree(n) == 0]
        return self._bfs_distances(G, primary_inputs)

    def _compute_observability(self, G):
        """
        Proxy for SCOAP-style observability: how many logic levels a
        signal is from a primary output. Computed as controllability
        on the reversed graph, from nodes with out_degree == 0.
        """
        primary_outputs = [n for n in G.nodes() if G.out_degree(n) == 0]
        return self._bfs_distances(G.reverse(copy=False), primary_outputs)

    @staticmethod
    def _normalize_distance(d, sentinel_value):
        """
        -1 (unreached) is replaced with sentinel_value rather than 0, so an
        unreachable node is never confused with a true primary input/output
        (distance 0). sentinel_value should be larger than any real distance
        seen in practice — passed in per-graph based on that graph's diameter.
        """
        return float(d) if d != -1 else float(sentinel_value)

    # ------------------------------------------------------------
    # Per-graph feature extraction
    # ------------------------------------------------------------

    def _gate_class_onehot(self, gate_class):
        idx = self.gate_class_to_idx.get(gate_class, self.unk_idx)
        vec = [0.0] * self.vocab_size
        vec[idx] = 1.0
        return vec

    def extract(self, gpickle_path, label, graph_id):
        """
        Returns (Data, metadata) for one graph.

        Node ordering is sorted by gate name for determinism — the same
        gate name will always land at the same index across repeated runs.
        """
        with open(gpickle_path, "rb") as f:
            G = pickle.load(f)

        node_names = sorted(G.nodes())
        node_index = {name: i for i, name in enumerate(node_names)}

        controllability = self._compute_controllability(G)
        observability = self._compute_observability(G)

        # Sentinel for unreached nodes: one more than the largest real
        # distance seen in this graph (or 1 if the graph is trivially small).
        max_real_dist = max(
            [d for d in controllability.values() if d != -1] +
            [d for d in observability.values() if d != -1] +
            [0]
        )
        sentinel = max_real_dist + 1

        x = []
        node_raw_types = []
        node_gate_classes = []
        node_ports = []
        node_controllability = []
        node_observability = []

        for name in node_names:
            attrs = G.nodes[name]
            raw_type = attrs.get("gate_type", self.UNK_TOKEN)
            gate_class = classify_gate_type(raw_type)
            ports = json.loads(attrs.get("ports", "{}"))

            onehot = self._gate_class_onehot(gate_class)
            in_deg = G.in_degree(name)
            out_deg = G.out_degree(name)
            ctrl = self._normalize_distance(controllability[name], sentinel)
            obs = self._normalize_distance(observability[name], sentinel)

            x.append(onehot + [float(in_deg), float(out_deg), ctrl, obs])

            node_raw_types.append(raw_type)
            node_gate_classes.append(gate_class)
            node_ports.append(ports)
            node_controllability.append(ctrl)
            node_observability.append(obs)

        x = torch.tensor(x, dtype=torch.float)

        edge_index = [[], []]
        edge_signals = []
        for src, dst, edata in G.edges(data=True):
            edge_index[0].append(node_index[src])
            edge_index[1].append(node_index[dst])
            edge_signals.append(edata.get("signal", ""))

        edge_index = torch.tensor(edge_index, dtype=torch.long)
        y = torch.tensor([label], dtype=torch.long)

        data = Data(x=x, edge_index=edge_index, y=y)
        data.graph_id = graph_id

        metadata = {
            "graph_id": graph_id,
            "label": label,
            "num_nodes": len(node_names),
            "num_edges": len(edge_signals),
            "node_names": node_names,
            "node_types": node_raw_types,
            "node_gate_classes": node_gate_classes,
            "node_ports": node_ports,
            "node_controllability": node_controllability,
            "node_observability": node_observability,
            "edge_signals": edge_signals,
        }

        return data, metadata