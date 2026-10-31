# Integrated pipeline

Run the commands in the [repository README](../README.md) from the repository root. The default paths in `config.py` point to the packaged archive under `data/`; `HT_DATA_ROOT` and `HT_RUNS_ROOT` can override those locations.

`prepare_data.py` selects the 42 samples with clean/Trojan benchmark pairs, extracts their CodeBERT embeddings, and builds three evaluation folds grouped by identical clean RTL source text. `audit_data.py` validates the prepared data. `train_cv.py` trains RTL-only, GNN-only, or fusion models on identical folds, and `report.py` compares their predictions. Graphs stay compressed until loaded for a step.

The graph and fusion models are computationally demanding because the AES graphs have roughly 240,000 nodes. Run full training on a machine with enough memory and preferably a GPU. The RTL-only baseline and small-graph forward passes have been exercised locally; the full graph/fusion cross-validation is still unverified.

For an exploratory comparison on the earlier, smaller graphs with ordered node metadata, add `--dataset legacy` to each `train_cv.py` command. This writes separate `runs/legacy_*` outputs. The completed three-model comparison and its limitations are in `docs/BASELINE_RESULTS.md`.

The localization utilities require original RTL and source-attributed synthesis output. The supplied data archive does not provide verified node-level ground truth.
