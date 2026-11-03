# Executed augmentation results

The augmentation produced no demonstrated improvement in host generalization. Pooled AUROC increased, while equal-host AUROC declined and all 18 runs classified every diagnostic circuit as clean at threshold 0.5.

## Actual neural model comparison

The baseline uses 18 verified circuits from six project hosts. Augmentation uses 185 circuits across 60 host groups, including 49 native-edit triplets, four revised development projects, and two independently sourced RS232 benchmark variants. The same ten PIC16F84/memctrl test circuits are excluded from all training conditions. These two hosts were inspected previously. This baseline differs from the original 42-circuit AES/RS232 development experiment.

GNNOnly and CrossAttentionFusion use the repository default architectures, fixed log1p graph numeric inputs and frozen pinned CodeBERT features. Seeds are 42, 43 and 44. Both primary conditions use five epochs. An additional baseline control has 925 optimizer updates, matching the augmented budget, and reproduces the fixed-epoch baseline AUROCs.

| Model | Baseline pooled AUROC | Augmented pooled AUROC | Baseline equal-host AUROC | Augmented equal-host AUROC | Balanced accuracy, both |
| --- | ---: | ---: | ---: | ---: | ---: |
| gnn | 0.187 | 0.267 | 0.333 | 0.083 | 0.500 |
| fusion | 0.187 | 0.333 | 0.333 | 0.292 | 0.500 |

The host metric calculates AUROC within each host and then gives each of the two hosts equal weight. Pooled AUROC also compares scores between circuits belonging to different hosts. This distinction explains why the two metrics can move in opposite directions.

| Model | Seed | Baseline pooled AUROC | Augmented pooled AUROC |
| --- | ---: | ---: | ---: |
| gnn | 42 | 0.20 | 0.48 |
| gnn | 43 | 0.16 | 0.16 |
| gnn | 44 | 0.20 | 0.16 |
| fusion | 42 | 0.20 | 0.68 |
| fusion | 43 | 0.20 | 0.16 |
| fusion | 44 | 0.16 | 0.16 |

The seed-averaged equal-host AUROC change is -0.250 for GNN, with descriptive paired host-bootstrap interval [-0.667, 0.167]. Fusion changes by -0.042, with interval [-0.333, 0.250]. The intervals condition on these trained predictions and only two inspected test hosts. They do not establish population-wide precision.

## Verified dataset changes

All four benign modular arithmetic rewrites survive the chosen no-ABC synthesis flow. The inserted identity is SAT-proved at its output width. Directed source and synthesized tests match their bounded reference observations. Other synthesis optimizations can remove this redundant logic.

Original Trust-Hub RS232-T2100 and RS232-T2200 attacks are unchanged and pass independent source-to-netlist behavioral replay. T2100 suppresses receive readiness following a false-start pulse. T2200 suppresses readiness during ordinary serial reception. These are two externally authored benchmark variants in one shared host family and source collection. Independence between their individual authors is unknown.

## Remaining shortcut failures

Against clean originals, both faults have more cells on all four new projects. Against the new benign arithmetic rewrites, they have fewer cells on all four. The pooled cell-count ranking of 0.50 hides these opposing signatures. Pooled host-held-out graph-statistics AUROC is 0.781, WL is 0.812 and gate-histogram is 0.625 on the four-project cohort. Source-character ranking is 0.875. These estimates use four inspected hosts and have wide intervals.

For the two externally authored variants, cells, edges, source characters and lines perfectly rank attacks above clean. The explicit word Trojan also perfectly separates their raw RTL from clean. The prior native-panel audit retains eight source-origin margin failures and eight inconclusive or unavailable typed comparisons. The shortcut evidence continues to block an admission or generalization claim.

The neural comparison combines all additions and does not isolate the contributions of native examples, benign rewrites, and external attacks. Five epochs are an exploratory training budget. The update-matched control addresses additional optimizer steps, while broader host and attack-author transfer remains unmeasured.

Exact predictions, metrics, protocols and hashes are in data/augmentation_v2/training_results.json, manifest.json, shortcuts.json and intake.json. Eighteen model checkpoints and individual run records are retained under runs/augmentation_v2. Reproduction instructions are in experiments/augmentation_v2/README.md.
