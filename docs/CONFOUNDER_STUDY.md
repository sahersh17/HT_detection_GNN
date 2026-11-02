# Baseline confounder study

This study keeps the two-layer GCN and mean/max pooling fixed. It addresses feature scaling, repeated clean records and seed variability before an architecture comparison. Training outputs are separate from the original LOFO results.

## Audit findings

The 80 records contain 40 clean entries but only eight exact clean source bundles: two AES bundles and one for each other family. They do not represent 40 independent clean hosts. Exact-source grouping is conservative: it will not detect renamed or logically equivalent sources.

The last four numerical features have very different scales across hosts. For example, maximum fan-out is 15 for RS232 and 511 for MC8051. The study applies log1p followed by training-fold-only standardization to these four features. Gate-class indicators are unchanged. Normalizer fitting balances family/class contributions and discounts repeated sources; no held-out graph contributes to fitting.

The generic OTHER cell class covers about 25–30% of B15 and 24–26% of s38584. These include AO/OA compound gates and arithmetic cells. AES contains `$memrd_v2` and `$meminit` operations. Thus the exports do not share primitive-gate granularity. A common vocabulary or numeric scaling cannot by itself harmonize their semantics. These findings must accompany any accuracy claim.

## Fixed experiment

Five seeds (42–46), four arms (raw, scaled, duplicate-aware weighting, both), and two cohorts produce 220 fold runs. Every run uses 25 epochs, hidden size 64, AdamW at 0.0003, weight decay 0.001 and threshold 0.5. Identical fold/seed initializations and example orders are used across arms. No hyperparameter or threshold search is performed.

The full cohort holds out each of seven families. The restricted cohort holds out each of AES, RS232, PIC16F84 and memctrl, which share the Verilog/Yosys recipe. This restriction reduces recipe variation but changes host composition and retains memory/primitive differences; it is not a causal estimate of synthesis effects.

Duplicate-aware weights give each family equal total loss weight, each class half its family's weight, and each unique source equal weight within that class. Repeated copies divide that source's weight. Evaluation reports both all-record metrics and metrics with each exact source represented once (averaging its predictions). Balanced accuracy handles the resulting unequal numbers of unique clean and Trojan sources.

Reports average balanced accuracy equally across families, then summarize its mean and standard deviation across seeds. Seeds quantify optimization variation, not additional independent host evidence. These previously inspected families remain development evidence.

## Run and inspect

Use `trusthub/venv/Scripts/python.exe pipeline/confounder_study.py --seed 42` and repeat for 43–46. Each completed fold is saved immediately under `data/confounder_study/seed_<seed>/`. Existing fold files are skipped for resumption; use a new output directory if changing the protocol or code.

Run `trusthub/venv/Scripts/python.exe pipeline/report_confounders.py` after all jobs finish. The `--watch` option waits up to six hours and then verifies all planned fold outputs before creating `data/confounder_study/summary.json` and `RESULTS.md`. Until those reports exist, the experiment is incomplete. The initial two weighting/scaler regression tests passed.

## What remains for synthesis harmonization

A new graph version would need functional definitions for mapped library cells, explicit memory lowering, a shared mapping recipe, and equivalence checks against original designs. The current B15/s38584 stubs provide port directions only and cannot establish those semantics. Do not relabel AO as AND or memory operations as flip-flops just to reduce the unknown count. Preserve the existing exports and their recorded limitations until a validated replacement exists.
