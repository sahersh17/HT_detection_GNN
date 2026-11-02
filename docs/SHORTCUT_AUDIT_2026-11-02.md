# RTL shortcut audit: inspected development cohorts

Status: exploratory, 2026-11-02. All hosts below were inspected during model
and pipeline development. These results can support an audit paper, but cannot
serve as a sealed evaluation of a new detector.

## Original corrected RTL comparison

The 21 paired variants contain only three independent clean-source groups.
The original RTL model and the character/line/window-count control each made
six errors among 42 design sides. They share two errors; their other four
errors are on opposite sides of the same four RS232 pairs. Equal fold scores
therefore do **not** mean the models make the same decisions.

| Fold | Pairs | RTL balanced accuracy | Metadata balanced accuracy | RTL AUROC | Metadata AUROC |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 11 | 1.000 | 1.000 | 1.000 | 1.000 |
| 2 | 6 | 0.833 | 0.833 | 1.000 | 1.000 |
| 3 | 4 | 0.500 | 0.500 | 0.500 | 0.500 |

The exact paired sign-flip test over these three group-level differences gives
`p = 1.0` for both balanced accuracy and AUROC. The smallest attainable
one-sided p-value with three groups is `1/8 = 0.125`; the smallest two-sided
value for a nonzero symmetric statistic is `2/8 = 0.25`. This is a resolution
limit, not evidence that the models are equivalent. Per-example predictions,
fold membership, hashes, and the exact calculation are in
`data/audit_v1/error_overlap.json`.

## Six-host development extension

The expanded paired RTL cohort has 72 design sides, 36 clean/Trojan pairs,
six host families, and only seven distinct clean source texts. We used five
initializations, leave-one-entire-host-family-out, train-only normalization,
and loss weights that give equal total weight to each host and then each clean
source within it. Verilog and VHDL, encoder window conventions, and synthesis
flows are mixed. These are descriptive results, not independent replications.

| Arm | Equal-host AUROC, mean ± seed SD | Equal-host paired win rate | Pooled balanced accuracy at 0.5, mean ± seed SD |
| --- | ---: | ---: | ---: |
| Character and line counts | 0.833 ± 0.000 | 0.833 | 0.500 ± 0.000 |
| CodeBERT window count | 0.804 ± 0.000 | 0.804 | 0.500 ± 0.000 |
| Counts plus windows | **0.935 ± 0.000** | **0.935** | 0.500 ± 0.000 |
| CodeBERT mean/max embedding | 0.706 ± 0.090 | 0.706 | 0.614 ± 0.036 |

The table averages five seeds. Seed SD measures optimization variation, not
uncertainty over new hosts. The metadata model ranks many pairs correctly
but predicts one class throughout several held-out hosts at the fixed 0.5
threshold. Its 0.500 balanced accuracy reflects calibration failure, not
absence of ranking signal. AUROC within a one-pair host is especially fragile.

| Held-out host | Pairs | Count+window AUROC | RTL embedding AUROC |
| --- | ---: | ---: | ---: |
| AES | 17 | 1.000 | 1.000 |
| MC8051 | 7 | 0.857 | 0.786 |
| PIC16F84 | 4 | 0.750 | 0.700 |
| RS232 | 4 | 1.000 | 0.750 |
| b19 | 3 | 1.000 | 0.500 |
| memctrl | 1 | 1.000 | 0.500 |

These per-host values average the five seeds. On this inspected cohort, the
simple metadata control is at least as strong as the RTL embedding model on
every host. This does not establish that the embedding has no semantic signal,
because source style, language, windowing, and flow are confounded. It does
establish that an apparent high detection score needs this control.

The complete per-sample predictions, per-seed/per-host metrics, input hashes,
and training recipe are in `data/audit_v1/six_host_predictions.json`,
`six_host_summary.json`, and `experiments/audit_v1/six_host_rtl_control.py`.
`experiments/audit_v1/reproduce_tables.py` recalculates every reported metric
from the saved predictions and checks their hash.

## Claim boundary

The defensible finding is that the present paired RTL benchmarks admit a
strong source-metadata shortcut, and the present representation has not shown
an advantage over that shortcut on these inspected hosts. The experiment does
not identify a unique causal mechanism or prove that all hardware-Trojan RTL
benchmarks have this property. No method-superiority or real localization
claim follows from it.
