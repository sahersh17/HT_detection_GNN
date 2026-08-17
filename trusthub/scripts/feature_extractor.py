from pathlib import Path
import json
import pickle

import torch
from torch_geometric.data import Data


class FeatureExtractor:
    """
    Converts NetworkX gate-level graphs (built by GraphBuilder) into
    PyTorch Geometric Data objects, plus a parallel node-metadata store
    that keeps every node traceable back to its original gate name,
    type, and port connections. The metadata store is what a later
    LLM-based localization/explainability step will read from.
    """

    UNK_TOKEN = "__UNK__"

    def __init__(self, gate_types=None):
        # gate_types: sorted list of known gate type strings (e.g. "$_AND_", "$_DFF_P_", ...)
        self.gate_types = gate_types or []
        self._rebuild_index()

    def _rebuild_index(self):
        self.gate_type_to_idx = {gt: i for i, gt in enumerate(self.gate_types)}
        # UNK always occupies the last slot, so vocab can grow later
        # without invalidating previously-saved feature indices for known types.
        self.unk_idx = len(self.gate_types)
        self.vocab_size = len(self.gate_types) + 1

    # ------------------------------------------------------------
    # Vocabulary — fit once across the whole dataset, then freeze
    # ------------------------------------------------------------

    def fit_vocab(self, gpickle_paths):
        seen = set()
        for path in gpickle_paths:
            with open(path, "rb") as f:
                G = pickle.load(f)
            for _, attrs in G.nodes(data=True):
                seen.add(attrs.get("gate_type", self.UNK_TOKEN))
        self.gate_types = sorted(seen)
        self._rebuild_index()

    def save_vocab(self, path):
        with open(path, "w") as f:
            json.dump({"gate_types": self.gate_types}, f, indent=2)

    @classmethod
    def load_vocab(cls, path):
        with open(path, "r") as f:
            data = json.load(f)
        return cls(gate_types=data["gate_types"])

    # ------------------------------------------------------------
    # Per-graph feature extraction
    # ------------------------------------------------------------

    def _gate_type_onehot(self, gate_type):
        idx = self.gate_type_to_idx.get(gate_type, self.unk_idx)
        vec = [0.0] * self.vocab_size
        vec[idx] = 1.0
        return vec

    def extract(self, gpickle_path, label, graph_id):
        """
        Returns (Data, metadata) for one graph.

        Node ordering is sorted by gate name for determinism — the same
        gate name will always land at the same index across repeated runs,
        which matters once you're mapping GNN output back to gate identity.
        """
        with open(gpickle_path, "rb") as f:
            G = pickle.load(f)

        node_names = sorted(G.nodes())
        node_index = {name: i for i, name in enumerate(node_names)}

        # ---- node features: one-hot gate type + normalized in/out degree ----
        x = []
        node_types = []
        node_ports = []

        for name in node_names:
            attrs = G.nodes[name]
            gate_type = attrs.get("gate_type", self.UNK_TOKEN)
            ports = json.loads(attrs.get("ports", "{}"))

            onehot = self._gate_type_onehot(gate_type)
            in_deg = G.in_degree(name)
            out_deg = G.out_degree(name)

            x.append(onehot + [float(in_deg), float(out_deg)])
            node_types.append(gate_type)
            node_ports.append(ports)

        x = torch.tensor(x, dtype=torch.float)

        # ---- edges ----
        edge_index = [[], []]
        edge_signals = []
        for src, dst, edata in G.edges(data=True):
            edge_index[0].append(node_index[src])
            edge_index[1].append(node_index[dst])
            edge_signals.append(edata.get("signal", ""))

        edge_index = torch.tensor(edge_index, dtype=torch.long)

        y = torch.tensor([label], dtype=torch.long)

        data = Data(x=x, edge_index=edge_index, y=y)
        data.graph_id = graph_id  # carried through for traceability, not used by the GNN itself

        metadata = {
            "graph_id": graph_id,
            "label": label,
            "num_nodes": len(node_names),
            "num_edges": len(edge_signals),
            "node_names": node_names,     # index i here == node i in data.x / edge_index
            "node_types": node_types,
            "node_ports": node_ports,
            "edge_signals": edge_signals,  # index-aligned with edge_index columns
        }

        return data, metadata