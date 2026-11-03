# Stage 3 diagnostic: one-fold semantic-graph memorization

Completed 2026-11-03. This is a **training-set capacity check**, not a cross-validation or generalization result. No held-out fold, inspected 10-circuit diagnostic, or final-test candidate was scored. The one chosen fold was fold 4, selected before training because it had the smallest semantic-graph node total: 38 circuits, 12 hosts, 24 negatives, 14 positives, and 283,594 nodes. All 38 tensors passed the locked SHA-256 checks.

The diagnostic used a two-layer 64-unit GCN on the 127-feature `semantic_v1` graphs. It pooled only original cell rows (a prefix), with sum plus max pooling and a 64-unit classifier head. It used one positive and one negative from each host per epoch, Adam at 0.001, gradient clipping at 1.0, one seed (20261103), no dropout, and no weight decay. Those settings favor memorization. There was no model or threshold selection using validation data.

| Run | Epochs | Best training pooled AUROC | Final training pooled AUROC | Final equal-host AUROC | Final balanced accuracy at 0.5 |
|---|---:|---:|---:|---:|---:|
| Raw sum plus max | 50 | 0.577 | 0.531 | 0.521 | 0.595 |
| Pooled LayerNorm after sum plus max | 80 | 0.765 (epoch 70) | 0.757 | 0.688 | 0.643 |

The raw sum produced unstable, sometimes enormous loss (for example 27.4 at epoch 1); probabilities saturated at both extremes. Normalizing the pooled vector made the loss stable and raised the best training AUROC, but the model did **not** approach 1.0 on its own training fold. The preset stop rule required pooled and equal-host AUROC at least 0.99 and balanced accuracy at least 0.95; it was never met.

The known `tt_um_rejunity_decoder` memory-bit edit illustrates the bottleneck. Its semantic graph is provably distinct from the two negative variants, but the normalized model assigned probabilities 0.4959369004 and 0.4959373176 to the benign and positive variants, respectively—a difference of only about 4.2e-7. That graph has 34 original cell rows among 10,345 nodes. Across the whole fold, original cells are 27,751 of 283,594 rows (9.8%). Pooling over cells avoids direct bit-node dilution, yet two GCN propagation layers still reduce this local bit difference to a negligible graph-level score. This is an observation about this architecture and optimizer, not proof that the task is impossible.

**Decision:** stop the GNN work at this diagnostic. The requested memorization gate failed, so a multi-seed or full-fold GNN run is not justified. A paired clean-reference baseline would test a different and likely better-posed question for literal and pin-index edits; it should be clearly labeled golden-reference detection and needs separate approval under the stage-by-stage workflow. An untouched benchmark with independently sourced trigger/payload attacks is still required for a general Trojan-detection claim.

Reproduce the normalized run with `trusthub/venv/Scripts/python.exe experiments/dataset_stage3/memorize_fold.py --normalized-pool --max-epochs 80`. The raw run used the same script without normalization and `--max-epochs 50`. Curves, train predictions, and model weights are in `data/dataset_stage3/`.
