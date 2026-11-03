"""Models for the three comparisons. Needs torch + torch_geometric (Colab)."""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv


class GNNOnly(nn.Module):
    def __init__(self, node_dim=20, hidden=64, dropout=0.2):
        super().__init__()
        self.c1, self.c2 = GCNConv(node_dim, hidden), GCNConv(hidden, hidden)
        self.norm, self.drop = nn.LayerNorm(hidden), nn.Dropout(dropout)
        self.head = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden, 2))

    def forward(self, graph, rtl=None):
        x = self.drop(F.relu(self.c1(graph.x, graph.edge_index)))
        h = self.norm(F.relu(self.c2(x, graph.edge_index)))
        logits = self.head(torch.cat([h.mean(0), h.max(0).values])[None])
        return {"logits": logits, "node_embeddings": h}


class CrossAttentionFusion(nn.Module):
    """Same architecture as the Colab notebook (graph<->RTL cross attention); hidden_dim is configurable."""

    def __init__(self, node_dim=20, rtl_dim=768, hidden_dim=64, num_heads=4, dropout=0.2):
        super().__init__()
        self.gcn1, self.gcn2 = GCNConv(node_dim, hidden_dim), GCNConv(hidden_dim, hidden_dim)
        self.graph_norm = nn.LayerNorm(hidden_dim)
        self.rtl_projection = nn.Sequential(nn.Linear(rtl_dim, hidden_dim), nn.GELU(), nn.LayerNorm(hidden_dim))
        self.g_q_r = nn.MultiheadAttention(hidden_dim, num_heads, dropout=dropout, batch_first=True)
        self.r_q_g = nn.MultiheadAttention(hidden_dim, num_heads, dropout=dropout, batch_first=True)
        self.gn, self.rn, self.drop = nn.LayerNorm(hidden_dim), nn.LayerNorm(hidden_dim), nn.Dropout(dropout)
        self.classifier = nn.Sequential(nn.Linear(4 * hidden_dim, hidden_dim), nn.ReLU(),
                                        nn.Dropout(dropout), nn.Linear(hidden_dim, 2))

    def forward(self, graph, rtl, return_attention=True):
        x = self.drop(F.relu(self.gcn1(graph.x, graph.edge_index)))
        node = self.graph_norm(F.relu(self.gcn2(x, graph.edge_index)))
        g, r = node.unsqueeze(0), self.rtl_projection(rtl).unsqueeze(0)
        g_ctx, g2r = self.g_q_r(g, r, r, need_weights=return_attention, average_attn_weights=True)
        g_ctx = self.gn(g + self.drop(g_ctx))
        r_ctx, r2g = self.r_q_g(r, g, g, need_weights=return_attention, average_attn_weights=True)
        r_ctx = self.rn(r + self.drop(r_ctx))
        fused = torch.cat([g_ctx.mean(1), g_ctx.max(1).values, r_ctx.mean(1), r_ctx.max(1).values], -1)
        return {"logits": self.classifier(fused), "node_embeddings": node,
                "contextual_node_embeddings": g_ctx.squeeze(0),
                "graph_to_rtl_attention": g2r.squeeze(0) if g2r is not None else None,
                "rtl_to_graph_attention": r2g.squeeze(0) if r2g is not None else None,
                "fused_embedding": fused}
