# Hardware Trojan Detection with GNN–LLM Fusion

A hardware Trojan detection and localization framework that combines **structural** information from gate-level netlists (via a Graph Neural Network) with **semantic** information from RTL source code (via CodeBERT), fused with cross-attention. The goal is not just to classify a design as clean or Trojan-infected, but to localize the suspicious logic and make the decision explainable.

> **Status:** work in progress. Feature extraction for both modalities is built; the cross-attention fusion model and evaluation are under development. Results sections below are placeholders to fill in as experiments finish.

## Motivation

Hardware Trojans are malicious modifications inserted into integrated circuits, and they are hard to find because they are small, rarely triggered, and hide inside large designs. Netlist-only graph models see structure but not intent; RTL-only models see intent but not the synthesized structure. This project fuses both views so each can compensate for the other, and uses attention to point at the nodes and code regions that drove a prediction.

## Approach

```
 RTL (Verilog) ──► CodeBERT (sliding-window chunks) ──► token-level embeddings ─┐
                                                                                ├─► Cross-attention fusion ─► classification
 Netlist (Yosys) ─► gate graph (PyG) ──► GNN node embeddings ──────────────────┘          + localization / explainability
```

1. **Dataset:** TrustHub benchmarks (AES and RS232 families), organized one folder per benchmark variant with its netlist and RTL files
2. **Netlist synthesis:** Verilog is synthesized with Yosys into gate-level netlists, then parsed into graphs
3. **Graph features:** each node carries a 20-dimensional feature vector: gate-class one-hot, in-degree, out-degree, controllability, observability. Graphs are saved as PyTorch Geometric `Data` objects (`x`, `edge_index`, graph label `y`, `graph_id`)
4. **RTL semantics:** `microsoft/codebert-base` embeddings. RTL files far exceed CodeBERT's 512-token limit, so they are split with sliding-window chunking (max length 512, stride 50), masked-mean-pooled per chunk, and saved as variable-length `(num_chunks, 768)` tensors instead of being truncated
5. **Fusion:** cross-attention between GNN node embeddings (queries) and token-level RTL representations (keys/values). Token-level rather than mean-pooled embeddings are used so that attention can attend over multiple code regions
6. **Explainability:** attention weights highlight which nodes and code segments contributed to a Trojan prediction

## Dataset

| Item | Detail |
|---|---|
| Source | TrustHub hardware Trojan benchmarks |
| Families | AES, RS232 |
| Graph labels | 31 clean, 62 Trojan (class-imbalanced) |
| Layout | `data/<family>/<variant>/` with netlist `.pt` and RTL chunk `.pt` files; `manifest.json`, `gate_vocab.json`, and per-variant `metadata/` JSON alongside |

Data caveats worth knowing: file naming differs across families (e.g. `clean/trojan` vs `tjfree/tjin` vs `standard`), some variants lack a matching netlist or RTL side and are excluded, and one AES benchmark ships a pre-synthesized netlist instead of RTL and is skipped in synthesis.

## Robustness and leakage checks

- **Leakage audit:** `check_leakage.py` scans for naming leakage (node or signal names that reveal the label), which has caught a real leak before. Node-name leakage remains an active concern and features are built from structure rather than names
- **Obfuscated held-out set:** an obfuscation pipeline (dummy-logic insertion, signal renaming, reordering) produces a 20-sample test set used *only* for evaluation, never for training or augmentation, to measure how well the model holds up against evasion

## Repository structure

```
.
├── notebooks/            # feature extraction (structural + CodeBERT), synthesis, analysis
├── scripts/              # check_leakage.py, Perl triage script for TrustHub file/manifest mismatches
├── data/                 # TrustHub-derived graphs and embeddings (not tracked; see Dataset)
└── README.md
```

*(Adjust to match your actual repo layout.)*

## Requirements

- Python 3.9+
- PyTorch, PyTorch Geometric, NetworkX
- Hugging Face `transformers` (CodeBERT)
- Yosys (netlist synthesis; on Windows, use WSL since there is no reliable native build)
- Google Colab was used for embedding extraction

## Results

*To be filled in.* Suggested table once experiments are done:

| Model | Accuracy | Precision | Recall | F1 | AUC | Obfuscated-set F1 |
|---|---|---|---|---|---|---|
| GNN only (netlist) | TBD | TBD | TBD | TBD | TBD | TBD |
| CodeBERT only (RTL) | TBD | TBD | TBD | TBD | TBD | TBD |
| **GNN–LLM fusion** | TBD | TBD | TBD | TBD | TBD | TBD |

Because the data is imbalanced (2:1 Trojan to clean) and small, report precision, recall, F1 and AUC rather than accuracy alone, and split by **benchmark variant** (not by random sample) so near-duplicate variants of the same design don't leak between train and test.

## Roadmap

- [x] Dataset organization and netlist synthesis
- [x] Structural graph features
- [x] CodeBERT chunked token-level embeddings
- [ ] Cross-attention fusion module
- [ ] Training and ablations (GNN-only, RTL-only, fusion)
- [ ] Localization and explainability analysis
- [ ] Evaluation on the obfuscated held-out set

## Contributors

*Add team members here.*

## Acknowledgements

Benchmarks from [TrustHub](https://trust-hub.org). RTL encoder: [CodeBERT](https://huggingface.co/microsoft/codebert-base).
