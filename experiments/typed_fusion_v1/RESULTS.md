# Typed fusion v1: executed diagnostic

## Scope and controls

The 52 prepared records comprise 21 paired AES/RS232 development benchmarks (42 circuits) and five paired memctrl/PIC diagnostic benchmarks (10 circuits). Preparation verified source, Yosys, graph, and frozen CodeBERT hashes. Independent verification found all original ordered gate classes and cell-to-cell connections in the typed view, plus 944,812 gate-to-RTL links. The view has 576,936 cell nodes and 51,159,034 directed typed edges. New synthetic tests (4) and existing pipeline tests (22) pass.

The matched training runs below use seed 42, AdamW, identical source-group splits, a fixed 0.5 threshold, family/class/source-balanced sample weights, and **three epochs** for branch and ablation comparisons. A separate fusion external run uses 25 epochs. The memctrl/PIC records and all development folds were previously inspected; these are diagnostic, not blind test results. The external set has only five pairs from two hosts. There are no reviewed gate or line labels.

## Matched three-epoch results

| External arm | Balanced accuracy at 0.5 | AUROC | Trojan ranked above clean, paired |
|---|---:|---:|---:|
| Structured RTL operators only | 0.50 | 0.48 | 2/5 |
| Frozen CodeBERT + structured RTL | 0.50 | 1.00 | 5/5 |
| Typed graph | 0.50 | 0.84 | 5/5 |
| Aligned gated fusion | 0.50 | 0.84 | 5/5 |

The fusion external Trojan-minus-clean probability gaps are only 0.0023 to 0.0107. All ten external samples are classified as clean at the fixed threshold. The region head is not validated as localization: it receives circuit labels only.

| Source-group development fold | RTL AUROC / balanced accuracy | Graph AUROC / balanced accuracy | Fusion AUROC / balanced accuracy |
|---|---:|---:|---:|
| 1: 11 AES pairs | 1.00 / 1.00 | 0.727 / 0.50 | 1.00 / 0.955 |
| 2: 6 AES pairs | 1.00 / 0.50 | 1.00 / 0.50 | 1.00 / 0.50 |
| 3: 4 RS232 pairs | 1.00 / 0.50 | 0.75 / 0.50 | 1.00 / 0.50 |

Fold 1 is confounded by label-correlated AES top-port differences, so its high score cannot establish Trojan-behavior detection. In folds 2 and 3, correct within-pair ranking does not translate to a usable threshold. The RTL-only arm matches fusion's fold AUROC in this pilot; fusion has no demonstrated incremental benefit.

## Input-group ablations (same external split, seed, and three epochs)

| Change | AUROC | Paired wins | Reading |
|---|---:|---:|---|
| Remove RTL operator features from the RTL arm | 1.00 | 5/5 | No measured ranking benefit from these 16 heuristic features. |
| Remove graph numeric, role, and pin-statistic node features, retaining cell type and topology | 0.36 | 2/5 | This feature group matters in this run; shortcut sensitivity remains unresolved. |
| Remove source-alignment links from fusion, falling back to global graph context | 0.96 | 5/5 | The present alignment mechanism does not improve this external result. |

The alignment map covers 99.1% of cells overall, but only about half of AES RTL chunks receive a linked cell in the evaluated folds. Unmatched chunks use global graph context. The heuristic line-overlap links and circuit-only labels may therefore add noise. These ablations are one-seed, five-pair sensitivity tests, not definitive feature attribution.

## Training-only threshold check

After training, a threshold selected for maximum balanced accuracy on the **training** records was applied unchanged to each held-out set. Fusion external training balanced accuracy was 0.905 at threshold 0.3878, while external balanced accuracy remained 0.50. Development fold thresholds 0.4994, 0.5273, and 0.4834 yielded held-out balanced accuracies 1.00, 0.50, and 0.50. This confirms that the score distribution shifts by host/template; calibrating on the current training templates does not solve the detector decision problem.

## Research interpretation

The experiment successfully exercises typed cell connectivity, structural RTL features, frozen CodeBERT, sparse source-map fusion, and region scoring. It does **not** establish a generalizing Trojan detector. The graph descriptors show useful signal in one small external ablation, but that signal may include top-port or host/template cues. The current handcrafted RTL operator frequencies show no added value over CodeBERT. Sparse line-overlap fusion has not added value over an RTL-only branch, and its region outputs have no localization ground truth.

## Full-budget fusion external run

At 25 epochs, fusion external balanced accuracy remains **0.50**: all ten circuits are classified as Trojan. AUROC is **0.80**, and **4/5** paired Trojan variants score above their clean counterpart. The ten probabilities all lie between **0.9984 and 0.9994**; their paired gaps are tiny (four positive gaps around 0.00035–0.00043 and one negative memctrl gap around -0.00005). The learned mixture gate averages approximately **0.1% graph, 99.7% RTL, 0.2% region**, so the trained model has effectively discarded the graph and source-aligned region branches. A threshold selected only from the training records is 0.5149 (training balanced accuracy 1.00), yet external balanced accuracy remains 0.50. This is a particularly clear case of overconfidence and host-dependent score shift.

The saved baseline's 25-epoch external fusion AUROC was 0.84 and balanced accuracy 0.50. The architectures and training details differ, so that historical score is context rather than a controlled comparison. The new architecture has not improved the external diagnostic.

The next decisive data step is to add many independent clean host designs and matched Trojan/benign modifications, including port-matched counterfactuals, then hold out whole hosts and Trojan mechanisms. With those data, rerun multiple seeds and test calibrated circuit decisions and gate/line localization against reviewed labels. A parser-based RTL dataflow extractor would be a stronger successor to the token-frequency features used here.
