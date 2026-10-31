# Prospective evaluation protocol

This protocol was written after the first 42-sample pilot results were inspected. It is **not preregistered** and the existing three folds are development evidence, not an untouched final test. Record any future changes to models, prompts, thresholds, and exclusions before obtaining new held-out designs. Freeze the final test set and scoring script before running a final comparison.

## Dataset and splits

Use the 21 paired variants in `data/integrated/paired_manifest.json` for pilot comparisons requiring clean and Trojan sides. Keep all variants sharing identical clean RTL in one fold, as in `group_folds.json`. Report both sample count and number of independent source groups. Develop on the current data, then acquire genuinely new host designs and reserve some as an untouched external test. Do not tune hyperparameters, thresholds, prompts, or localization top-k values on that external test. Keep the benchmark descriptions hidden from model inputs.

## Detection prerequisite

Compare RTL-only, GNN-only, and fusion models on identical folds. Report the pooled and per-fold confusion matrices, balanced accuracy, macro F1, recall, false-positive rate, and AUROC with uncertainty across independent source groups. Detection is a prerequisite; it is not evidence of localization.

## Localization

Score only reviewed gate labels whose names match the exact row order of the evaluated graph. Label unmapped or ambiguous nodes `-1` and exclude them from denominators. Report label coverage, node precision/recall/F1 at the fixed predicted set size `|GT|`, IoU at `|GT|`, hit@1/5/10/50, first-Trojan rank, and a random-ranking reference. Compare GNN-only attribution, fusion attention, and an RTL-only method. Report where each method cannot produce gate or RTL locations. Do not infer accuracy from attention visualizations alone.

## Explanation claims

For each model-produced explanation, record `where`, `trigger`, `payload`, and `fix` claims with exact RTL citations. The validator in `pipeline/explanations/validate.py` checks that citations exist. An expert reviewer separately judges whether each claim is supported and correct using original RTL and held-out benchmark descriptions. Report unsupported-claim rate, trigger/payload category accuracy, location accuracy, and fix usefulness. The taxonomy in `data/localization_reference/taxonomy_draft.json` is a draft reference requiring hardware-expert review.

Compare the grounded method with an LLM-only baseline using the same RTL and token budget but no graph/localization evidence. Keep the same model version, decoding settings, and output schema. To assess faithfulness, rerun explanations after replacing the localized region with an unrelated region and report whether location-dependent claims change appropriately. An unchanged explanation is a failure for that check.

## Engineer review and robustness

For a blinded sample, ask at least two hardware engineers to rate each explanation's correctness, usefulness for locating the modification, and usefulness for fixing it on a fixed 1–5 scale. Record disagreements and adjudication. Separately evaluate renaming and obfuscation variants under a fixed, held-out protocol; report both detection and localization changes. No obfuscated set or engineer ratings are present yet, so neither result should be claimed.
