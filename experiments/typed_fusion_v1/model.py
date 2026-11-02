"""Weakly supervised typed-graph/RTL fusion for a single circuit at a time."""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F
from torch_geometric.nn import GINEConv

from prepare import EDGE_DIM, NODE_DIM, RTL_DIM


class TypedFusion(nn.Module):
    """Produce graph, RTL and source-aligned region logits without gate labels."""

    def __init__(self, hidden: int = 48, dropout: float = 0.2):
        super().__init__()
        self.node_in = nn.Sequential(nn.Linear(NODE_DIM, hidden), nn.ReLU(), nn.LayerNorm(hidden))
        self.convs = nn.ModuleList([
            GINEConv(nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, hidden)),
                     edge_dim=EDGE_DIM) for _ in range(2)
        ])
        self.norms = nn.ModuleList([nn.LayerNorm(hidden) for _ in self.convs])
        self.rtl_in = nn.Sequential(nn.Linear(768 + RTL_DIM, hidden), nn.ReLU(), nn.LayerNorm(hidden))
        self.graph_head = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden, 1))
        self.rtl_head = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden, 1))
        self.region_head = nn.Sequential(nn.Linear(3 * hidden + 1, hidden), nn.ReLU(),
                                         nn.Dropout(dropout), nn.Linear(hidden, 1))
        self.gate = nn.Sequential(nn.Linear(4 * hidden + 1, hidden // 2), nn.ReLU(),
                                  nn.Linear(hidden // 2, 3))
        self.drop = nn.Dropout(dropout)

    def forward(self, item: dict, arm: str = "fusion") -> dict:
        if arm not in {"graph", "rtl", "structured", "fusion"}:
            raise ValueError(f"Unknown arm: {arm}")
        graph = item["graph"]
        rtl = item["rtl"]
        struct = item["struct"]
        if arm in {"graph", "fusion"}:
            h = self.node_in(graph.x)
            for conv, norm in zip(self.convs, self.norms):
                h = norm(h + self.drop(F.relu(conv(h, graph.edge_index, graph.edge_attr))))
            cell_h = h[:graph.n_cell]
            gmean = cell_h.mean(0)
            gpool = torch.cat((gmean, cell_h.max(0).values))
            graph_logit = self.graph_head(gpool).squeeze()
        else:
            cell_h = None
            gpool = None
            graph_logit = None
        if arm in {"rtl", "structured", "fusion"}:
            encoded = torch.zeros_like(rtl) if arm == "structured" else rtl
            r = self.rtl_in(torch.cat((encoded, struct), dim=-1))
            rpool = torch.cat((r.mean(0), r.max(0).values))
            rtl_logit = self.rtl_head(rpool).squeeze()
        else:
            r = None
            rpool = None
            rtl_logit = None
        if arm == "graph":
            return {"logit": graph_logit, "graph_logit": graph_logit}
        if arm in {"rtl", "structured"}:
            return {"logit": rtl_logit, "rtl_logit": rtl_logit}
        links, weights = item["links"], item["weights"]
        matched = torch.zeros_like(r)
        mass = torch.zeros((len(r), 1), dtype=r.dtype, device=r.device)
        if links.numel():
            chunk, node = links[0], links[1]
            w = weights[:, None]
            matched.index_add_(0, chunk, cell_h[node] * w)
            mass.index_add_(0, chunk, w)
        coverage = (mass > 0).to(r.dtype)
        matched = torch.where(coverage.bool(), matched / mass.clamp(min=1e-6), gmean[None].expand_as(matched))
        region_input = torch.cat((r, matched, torch.abs(r - matched), coverage), dim=-1)
        region_logits = self.region_head(region_input).squeeze(-1)
        k = max(1, math.ceil(len(region_logits) * 0.1))
        region_logit = region_logits.topk(k).values.mean()
        quality = coverage.mean().view(1)
        gate_weights = self.gate(torch.cat((gpool, rpool, quality))).softmax(-1)
        logit = torch.stack((graph_logit, rtl_logit, region_logit)).dot(gate_weights)
        return {"logit": logit, "graph_logit": graph_logit, "rtl_logit": rtl_logit,
                "region_logit": region_logit, "region_logits": region_logits,
                "gate_weights": gate_weights, "alignment_coverage": quality}


def training_loss(output: dict, label: int, arm: str) -> torch.Tensor:
    target = output["logit"].new_tensor(float(label))
    loss = F.binary_cross_entropy_with_logits(output["logit"], target)
    if arm == "fusion":
        for key in ("graph_logit", "rtl_logit", "region_logit"):
            loss = loss + 0.1 * F.binary_cross_entropy_with_logits(output[key], target)
    return loss
