# Hardware Trojan Detection with GNN–LLM Fusion

This research project combines circuit structure from gate-level netlists with RTL source-code embeddings to classify hardware designs as clean or Trojan-inserted. The intended next step is to evaluate whether the model can also identify suspicious gates. That localization result has not yet been validated.

## Why combine the two views?

A graph neural network (GNN) sees gates and their signal connections. CodeBERT captures information from the original Verilog RTL. Cross-attention combines those representations before classification and produces node-level attention scores for later localization analysis.

```text
RTL (Verilog) -> CodeBERT chunks --------------------+
                                                    +-> cross-attention -> clean/Trojan prediction
Netlist (Yosys) -> gate graph -> GNN node features --+
```

The graph pipeline synthesizes Verilog with Yosys, parses each netlist, connects gates by their signals, and builds 20-dimensional node features: gate-class one-hot values plus in-degree, out-degree, controllability, and observability proxies. CodeBERT embeds sliding windows of RTL into variable-length tensors with 768 values per chunk.

## Repository layout and data versions

- `trusthub/` contains Trust-Hub sources, synthesis and feature extraction scripts, and the earlier 93-graph dataset (31 clean, 62 Trojan). Its features should not be mixed with the newer data.
- `research/capstone.ipynb` preserves an earlier Colab experiment. Its reported 52-sample fusion result is separate from the current integrated dataset.
- `pipeline/` contains the data adapter, audit, RTL-only/GNN-only/fusion comparison, metrics, reporting, and preliminary localization tools.
- `data/HT_data_2026-10-31_b40cc08.zip` is the newer package with 94 graph tensors and 94 CodeBERT embeddings. Keep this large archive locally at that path; it is excluded from Git. Its portable manifest marks 60 pairs usable. The integrated comparison selects 42 samples from 21 benchmarks that have both clean and Trojan sides. It omits 18 usable but unpaired samples.

The new AES graphs are much larger than the earlier graphs, at roughly 240,000 nodes each. Full GNN and fusion training needs substantial memory and is best run with a GPU.

## Run the integrated comparison

Use the Python environment in `trusthub/venv` with PyTorch and PyTorch Geometric. From the repository root on Windows:

```powershell
& .\trusthub\venv\Scripts\python.exe pipeline\prepare_data.py
& .\trusthub\venv\Scripts\python.exe pipeline\audit_data.py
& .\trusthub\venv\Scripts\python.exe pipeline\train_cv.py --model rtl
& .\trusthub\venv\Scripts\python.exe pipeline\train_cv.py --model gnn --epochs 25
& .\trusthub\venv\Scripts\python.exe pipeline\train_cv.py --model fusion --epochs 25
& .\trusthub\venv\Scripts\python.exe pipeline\report.py rtl=runs\rtl\predictions.json gnn=runs\gnn\predictions.json fusion=runs\fusion\predictions.json
```

`prepare_data.py` extracts the small embedding files and leaves the graphs compressed. All three models use the same evaluation folds. Folds group benchmarks that share identical clean RTL text, preventing those repeated clean sources from appearing in both training and test sets. The integrated data audit, packaged tests, RTL-only training, and small-graph model forward passes have been run locally. Full GNN and fusion cross-validation remains unverified.

## Robustness and localization

`trusthub/scripts/check_leakage.py` checks for label clues in graph metadata. The integrated audit additionally checks graph/embedding shapes, labels, and fold overlap. The supplied newer archive does not include source-attributed node mappings needed to establish Trojan-gate ground truth. The `pipeline/localization/` utilities can compare original clean and Trojan RTL and evaluate node rankings once source-attributed synthesis and node alignment are available. Attention scores alone are candidate explanations, not verified Trojan locations.

An obfuscated held-out evaluation set and full three-model comparison remain research work.

## Contributors

| Contributor | GitHub |
|---|---|
| Saher | [@sahersh17](https://github.com/sahersh17) |
| Shreya Save | [@shreyaasave](https://github.com/shreyaasave) |
| Rohit Patil | [@rohitpatil-27-08](https://github.com/rohitpatil-27-08) |

## Acknowledgements

Benchmarks are from [TrustHub](https://trust-hub.org). The RTL encoder is [CodeBERT](https://huggingface.co/microsoft/codebert-base).
