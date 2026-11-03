# Stage 2: frozen-fold CPU baselines

Completed 2026-11-03. Scope: **development detection of synthetic circuit edits and faults**. These numbers do not establish general hardware Trojan detection. Of 65 positives, 41 are native literal edits, eight are native input-pin edits, 14 are other development faults, and only two are original Trust-Hub RS232 attacks from one family. Comparisons with papers trained and tested on Trust-Hub attacks would be misleading.

The model code is `baselines.py`; `analyze.py` creates the fold and uncertainty audit. Inputs are the 185 locked development circuits and five source-owner-grouped folds from Stage 1. Every prepared tensor is SHA-256 verified against the locked manifest before loading. No final candidate or inspected 10-circuit diagnostic enters fitting, selection, or scoring. The final candidate reservation was written in `data/dataset_stage1/final_reservation.json` before the first fit. It admits **zero** final records; independent source provenance, host overlap, semantic validity, benign matching, and a pinned final protocol remain to be checked.

## Preflight

| Fold | Hosts | Negative | Positive | Positive mechanism counts | Unicode copies (negative/positive) |
|---|---:|---:|---:|---|---:|
| 0 | 12 | 24 | 13 | literal 9; pin 1; constant 1; conditional fault 2 | 0 |
| 1 | 12 | 24 | 13 | literal 8; pin 2; constant 1; conditional fault 2 | 6 (4/2) |
| 2 | 12 | 24 | 12 | literal 8; pin 2; bitwise 1; mask 1 | 3 (2/1) |
| 3 | 12 | 24 | 13 | literal 8; pin 2; bitwise 1; receive readiness 2 | 3 (2/1) |
| 4 | 12 | 24 | 14 | literal 8; pin 1; bit slice 1; conditional fault 4 | 0 |

Literal edits still make up 57–69% of the positives in each fold. The 12 saved Unicode text-copy differences cover four entire native host triplets (each two negative and one positive) in folds 1–3. Their 4/12 positive proportion is close to the development pool's 65/185. They are concentrated by host and fold, so the human-readable `.v` copies should still be repaired in a later version. This run reads the hashed prepared `.pt` embeddings, not those divergent copies.

## Features and models

- Size control: log node and edge counts. Separate length control: log RTL characters, lines, and CodeBERT chunk count.
- Host ID negative control: one-hot host identifiers. All validation hosts are unseen, so the expected within-host AUROC is 0.5. Cohort metadata is a second source shortcut control.
- Graph aggregation: 16 node-type proportions, 16 presence flags, and mean, standard deviation, maximum, and 50th, 90th, and 99th percentiles for each of the four numeric node channels, plus graph size.
- CodeBERT: mean and elementwise maximum over each circuit's frozen chunk embeddings. Each pooled 768-dimensional vector is reduced to 16 PCA components learned on the training fold only.
- Combined: graph aggregation, size, RTL length, and the two pooled embedding projections.
- Models: L2-regularized logistic regression implemented with PyTorch LBFGS and a small deterministic logistic gradient booster with decision stumps (40 rounds, fixed split grid). No validation labels informed model settings. The booster is a minimal implementation, not a tuned library implementation.

## Out-of-fold results

Equal-host AUROC averages the within-host AUROC across 60 hosts. Within-host pair ranking compares each positive with both negatives (130 comparisons). The selected cutoff maximizes balanced accuracy on the outer training fold's own fitted scores; this is an exploratory training-only choice, with no validation labels used. The fixed 0.5 cutoff is also shown. The uncertainty intervals are a paired 10,000-resample bootstrap over hosts, descriptive for this development sample.

| Model | Equal-host AUROC | Pooled AUROC | Pair ranking | Balanced log loss | Balanced accuracy, training cutoff | Balanced accuracy, 0.5 |
|---|---:|---:|---:|---:|---:|---:|
| Size logistic | 0.479 | 0.508 | 0.477 | 0.695 | 0.507 | 0.510 |
| Host-ID logistic | 0.500 | 0.512 | 0.500 | 0.693 | 0.500 | 0.500 |
| Cohort logistic | 0.500 | 0.535 | 0.500 | 0.688 | 0.535 | 0.535 |
| Graph aggregates logistic | 0.571 | 0.557 | 0.577 | **0.685** | 0.523 | 0.528 |
| Pooled CodeBERT logistic | 0.467 | 0.498 | 0.438 | 0.696 | 0.502 | 0.509 |
| Combined logistic | **0.583** | 0.528 | **0.585** | 0.717 | 0.511 | 0.503 |
| Graph aggregates boosted stumps | 0.517 | 0.523 | 0.527 | 0.739 | 0.516 | 0.500 |
| Combined boosted stumps | 0.500 | 0.507 | 0.500 | 0.739 | 0.519 | 0.500 |

RTL-length-only logistic had equal-host AUROC 0.517. All 12 model/control results, fold results, and per-circuit predictions are in `data/dataset_stage2/summary.json` and `predictions.json`.

| Logistic comparison | Equal-host AUROC, 95% host bootstrap interval | Difference from size, 95% paired interval |
|---|---:|---:|
| Size | 0.479 [0.388, 0.575] | — |
| Graph aggregates | 0.571 [0.471, 0.667] | +0.092 [−0.058, +0.242] |
| Pooled CodeBERT | 0.467 [0.367, 0.567] | −0.013 [−0.150, +0.121] |
| Combined | 0.583 [0.475, 0.683] | +0.104 [−0.042, +0.246] |

The graph and combined rankings exceed size in point estimate, but both paired intervals include zero. The combined model has worse balanced log loss than size, so its ranks do not translate into reliable probabilities. Equal-host AUROC varies substantially across folds: graph logistic 0.625, 0.604, 0.417, 0.521, 0.688; combined logistic 0.542, 0.667, 0.500, 0.458, 0.750. There is not yet a robust improvement claim.

The combined logistic model scores 0.602 equal-host AUROC on the 49 native hosts and 0.500 on the 11 other hosts. Excluding the four Unicode-affected hosts from evaluation yields 0.607 for combined and 0.589 for graph aggregation, so those text-copy discrepancies do not explain the small lift. This exclusion is a sensitivity check, not a new selected benchmark.

## Decision after Stage 2

The data contain weak, unstable graph-statistic signal beyond size. Pooled CodeBERT does not show independent signal. A GNN is not justified by a clear baseline win yet. If approved, the next stage should begin with the one-fold memorization check and localize which graph features carry the native-edit ranking. A full GNN run should depend on that diagnostic and a locked, independently sourced final benchmark; no final generalization claim is available today.
