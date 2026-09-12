"""
GNN <-> RTL cross-attention fusion module for hardware Trojan detection.

Pipeline:
    PyG Batch(graphs) -> GNNEncoder -> to_dense_batch -> GNNCodeCrossAttention
    -> masked mean pool -> classifier

Validated against real AES-T100 clean/trojan netlist + RTL chunk samples.
"""
import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv
from torch_geometric.utils import to_dense_batch


class GNNEncoder(nn.Module):
    """Lifts raw node features (gate-class one-hot + degree/controllability/
    observability, 20-dim) into a hidden embedding space via message passing."""

    def __init__(self, in_dim=20, hidden_dim=128):
        super().__init__()
        self.conv1 = GCNConv(in_dim, hidden_dim)
        self.conv2 = GCNConv(hidden_dim, hidden_dim)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index)
        return x


class GNNCodeCrossAttention(nn.Module):
    """Cross-attention fusion: GNN node embeddings attend over RTL token
    embeddings (CodeBERT chunk output). attn_weights doubles as the
    localization/explainability signal (which RTL tokens each node used)."""

    def __init__(self, gnn_dim, code_dim, hidden_dim=256, num_heads=4, dropout=0.1):
        super().__init__()
        self.node_proj = nn.Linear(gnn_dim, hidden_dim)
        self.code_proj = nn.Linear(code_dim, hidden_dim)
        self.cross_attn = nn.MultiheadAttention(
            hidden_dim, num_heads, dropout=dropout, batch_first=True
        )
        self.norm1 = nn.LayerNorm(hidden_dim)
        self.ffn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.GELU(),
            nn.Linear(hidden_dim * 2, hidden_dim),
        )
        self.norm2 = nn.LayerNorm(hidden_dim)

    def forward(self, node_embeds, code_token_embeds, code_attn_mask=None,
                average_attn_weights=True):
        """
        node_embeds:        (B, N, gnn_dim)   from to_dense_batch(GNN output)
        code_token_embeds:  (B, T, code_dim)  padded RTL chunk token embeddings
        code_attn_mask:     (B, T) bool, True = PAD (ignore)
        Returns:
            fused_nodes: (B, N, hidden_dim)   -- mask with node_mask before pooling
            attn_weights: (B, N, T) or (B, num_heads, N, T) if average_attn_weights=False
        """
        q = self.node_proj(node_embeds)
        kv = self.code_proj(code_token_embeds)
        attn_out, attn_weights = self.cross_attn(
            q, kv, kv,
            key_padding_mask=code_attn_mask,
            need_weights=True,
            average_attn_weights=average_attn_weights,
        )
        x = self.norm1(q + attn_out)
        x = self.norm2(x + self.ffn(x))
        return x, attn_weights


def masked_mean_pool(fused_nodes, node_mask):
    """Graph-level embedding from node-level fused output, ignoring padded nodes."""
    mask_f = node_mask.unsqueeze(-1).float()
    return (fused_nodes * mask_f).sum(dim=1) / mask_f.sum(dim=1).clamp(min=1e-8)


if __name__ == "__main__":
    # Smoke test with dummy shapes matching real data (20-dim nodes, 768-dim RTL tokens)
    from torch_geometric.data import Data, Batch
    from torch.nn.utils.rnn import pad_sequence

    g1 = Data(x=torch.randn(50, 20), edge_index=torch.randint(0, 50, (2, 80)), y=torch.tensor([0]))
    g2 = Data(x=torch.randn(40, 20), edge_index=torch.randint(0, 40, (2, 60)), y=torch.tensor([1]))
    batch = Batch.from_data_list([g1, g2])

    encoder = GNNEncoder()
    node_embeds = encoder(batch.x, batch.edge_index)
    dense_nodes, node_mask = to_dense_batch(node_embeds, batch.batch)

    rtl = [torch.randn(30, 768), torch.randn(12, 768)]
    rtl_padded = pad_sequence(rtl, batch_first=True)
    code_mask = torch.zeros(rtl_padded.shape[:2], dtype=torch.bool)
    for i, r in enumerate(rtl):
        code_mask[i, r.shape[0]:] = True

    fusion = GNNCodeCrossAttention(gnn_dim=128, code_dim=768)
    fused, attn = fusion(dense_nodes, rtl_padded, code_attn_mask=code_mask)
    graph_embeds = masked_mean_pool(fused, node_mask)

    print("fused_nodes:", fused.shape, "| attn_weights:", attn.shape, "| graph_embeds:", graph_embeds.shape)