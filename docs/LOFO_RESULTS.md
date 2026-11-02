# Leave-one-host-family-out detection

Completed on 80 graphs (40 clean/Trojan benchmark pairs) across seven families. Each fold trains a fresh GNN on six families and evaluates only the seventh. Variants and repeated clean designs stay together. This is family-level leave-one-out, not sample-level LOOCV.

| Held-out family | Designs | GNN balanced accuracy | Size baseline |
|---|---:|---:|---:|
| AES | 34 | 50.0% | 50.0% |
| MC8051 | 14 | 50.0% | 50.0% |
| PIC16F84 | 8 | 50.0% | 50.0% |
| RS232 | 8 | 50.0% | 50.0% |
| b15 | 8 | 100.0% | 50.0% |
| memctrl | 2 | 50.0% | 50.0% |
| s38584 | 6 | 83.3% | 50.0% |
| Equal-family mean | | **61.9%** | **50.0%** |

GNN pooled accuracy is 57.5%, macro F1 0.568, Trojan recall 45.0%, and false-positive rate 30.0%. Its confusion counts are TN=28, FP=12, FN=22, TP=18. Size-baseline pooled accuracy is 50.0%.

Threshold-free scores show that “five families at 50%” does not imply threshold calibration alone. AES has AUROC 0.882 and pairwise accuracy 15/17 while the model predicts every sample clean. MC8051, PIC16F84 and RS232 rank the Trojan below the paired clean in 6/7, 3/4 and 4/4 pairs. Per-family average precision (AP) and pairwise ranking are saved in [`extended_metrics.json`](../data/lofo_detection/extended_metrics.json).

The GNN predicts a single class for every sample in five of seven holdouts. Performance gains are concentrated in B15 and s38584. This does not establish broad generalization or statistically significant superiority. B15 and s38584 are supplied mapped gate netlists, MC8051 uses GHDL conversion, and older families use other synthesis flows. Host and synthesis-domain effects are therefore entangled. AES has only two unique clean source bundles; each other family has one. Their 40 clean records therefore do not amount to 40 independent designs. Small family sizes, repeated clean designs, previously inspected benchmark families, and one seed limit the evidence. Memctrl has only one pair. This experiment does not measure localization.

Protocol was saved before evaluation: 25 epochs, seed 42 plus fold index, hidden dimension 64, AdamW learning rate 0.0003, weight decay 0.001, fixed threshold 0.5, equal total training weight per family. No held-out-fold tuning or early stopping was used. The size baseline is regularized logistic regression on log node and edge counts, standardized on training data only. Fusion was not evaluated because B15/s38584 lack original RTL.

Artifacts: [protocol and input hashes](../data/lofo_detection/protocol.json), [metrics](../data/lofo_detection/results.json), [GNN predictions](../data/lofo_detection/gnn_predictions.json), [size predictions](../data/lofo_detection/size_predictions.json).

```powershell
trusthub/venv/Scripts/python.exe pipeline/train_lofo.py
trusthub/venv/Scripts/python.exe pipeline/verify_lofo.py
```

Next validation should repeat fixed settings across multiple seeds, test a common synthesis flow where feasible, and use inner grouped validation if choosing thresholds or hyperparameters. Any such choices must use training families only. These inspected folds are now development evidence; retain genuinely new hosts for a final assessment.
