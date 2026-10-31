# Exploratory detection comparison on the earlier graph version

All three models used the 42 samples from 21 paired benchmarks, the same three clean-source-held-out folds, and the newer package's CodeBERT embeddings. GNN and fusion used the **earlier** `trusthub/features` graph tensors because those have ordered node metadata. The experiment used seed 42 and 25 epochs for GNN/fusion. RTL-only used a standardized linear classifier. These runs were completed locally on CPU.

| Model | Balanced accuracy | Macro F1 | Trojan recall | False positives | False negatives | AUROC |
|---|---:|---:|---:|---:|---:|---:|
| RTL-only | 0.619 | 0.616 | 0.714 | 10 | 6 | 0.719 |
| GNN-only | 0.500 | 0.447 | 0.190 | 4 | 17 | 0.481 |
| Fusion | 0.500 | 0.447 | 0.190 | 4 | 17 | 0.385 |

The full per-fold outputs, predictions, summaries, checkpoints, and node attention arrays are in the local `runs/legacy_*` folders (excluded from Git). All 42 fusion attention arrays include node names and graph IDs; their node dimensions were checked against the saved name lists and earlier metadata.

Portable prediction and summary JSONs, along with hashes of the exact input manifests and data ZIP, are in `results/legacy_baselines/` so the table can be recomputed without the model checkpoints.

## Interpretation

Fusion did **not** beat the RTL-only baseline on this split. Each source group is large and there are only three independent clean-source groups, so uncertainty is high; these results are exploratory and should not be presented as evidence of generalization. The graph and fusion models predicted essentially one class for each held-out group. Hyperparameter or split changes based on these held-out results would contaminate the evaluation; a larger independent benchmark set is needed for development and final testing.

No gate-localization accuracy or explanation quality is reported. The older-graph gate candidates cover 44.2% of Trojan-side nodes and are not expert-reviewed ground truth. The newer graph package still lacks matching node metadata.
