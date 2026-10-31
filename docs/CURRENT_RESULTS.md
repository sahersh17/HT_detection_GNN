# Current evidence and claim boundary (2026-10-31)

This page reports **observed exploratory results**, including failures. It is the primary results record for the source-traced graph version. The older pilot in `docs/BASELINE_RESULTS.md`, the supplied 2026-10-31 ZIP, and this rebuild have different graph or embedding versions and must not be pooled. `results/provenance_pilot/` preserves a superseded run using the testbench-inclusive packaged embeddings; its metadata marks that limitation. All tables below use the corrected `provenance_clean_pilot` and the new-host diagnostic.

## Data and provenance

- Development: 21 paired Trust-Hub AES/RS232 variants, 42 samples, three distinct clean RTL texts across **two host families**. Both sides of a pair stay in the same fold. Identical clean RTL texts are grouped across variants.
- Diagnostic: five paired variants, ten samples, from memctrl-T100 and PIC16F84-T100/T200/T300/T400. They represent **two new clean host designs**. The diagnostic protocol was written before evaluating models on these hosts; it is small and has since been inspected.
- All 42 development graphs were regenerated with YoWASP Yosys 0.69 in one versioned no-ABC flow: 540,288 ordered nodes, 538,969 carrying an in-source RTL span. Tensor, row order, source hashes, and Yosys JSON were reconstructed and checked. The five diagnostic pairs were built and checked by the same code. **Source span coverage is a traceability check, not a Trojan-label correctness measure.**
- CodeBERT embeddings were regenerated from synthesizable RTL only. The 42 development samples have 1,078 chunks across 24 unique source texts; the ten diagnostic samples have 826 chunks across seven unique source texts. Every chunk has a checked source-file/line span. A separate audit found that all 42 originally packaged RTL embeddings contained testbenches, so those embeddings are excluded from the corrected experiment.
- The encoder code now pins CodeBERT revision `3b0952feddeffad0063f274080e3c23d75e7eb39`. Four development embeddings, spanning AES and RS232 clean/Trojan sides, were regenerated with that pin and were byte-identical to the saved tensors. The original 42-sample embedding manifest did not record a revision, so the pin was spot-checked rather than retroactively asserted for every file.
- Automatic changed-line intersection created gate **candidates**. There are zero reviewed gate labels and zero reviewed trigger, payload, or fix explanations. No independent hardware reviewers are available.

## Detection: development folds

All rows use the same three clean-source-grouped folds, 42 samples, seed 42. Balanced accuracy (BA) and macro F1 are pooled from out-of-fold predictions. These folds have been inspected repeatedly and do not constitute an untouched final test.

| Input and model | BA | Macro F1 | Interpretation |
|---|---:|---:|---|
| RTL CodeBERT + linear classifier | 0.857 | 0.857 | Development comparison |
| Gate GCN | 0.690 | 0.682 | Development comparison |
| Cross-attention fusion | 1.000 | 1.000 | **Suspiciously perfect on only three source groups; no generalization claim** |
| RTL length only (characters and lines) | 0.786 | 0.775 | Strong shortcut control |
| Graph size only (nodes and edges) | 0.357 | 0.339 | Negative control |

The length-only control reaches 0.786 without seeing circuit semantics. This is evidence that superficial source differences can predict labels in these folds. Attention values exported from the fusion model are aligned to exact graph rows and RTL chunks, but they are **rankings, not validated Trojan locations**.

## Detection: previously reserved host families

Models were fit on all 21 original pairs and evaluated once at a frozen 0.5 threshold on ten samples from the two new hosts. Values below come from saved per-sample probabilities. No threshold adjustment was made after inspection.

| Input and model | BA | Macro F1 | AUROC | Confusion (TN, FP, FN, TP) |
|---|---:|---:|---:|---|
| RTL CodeBERT + linear classifier | 0.500 | 0.451 | 0.84 | 4, 1, 4, 1 |
| Gate GCN | 0.500 | 0.333 | 0.28 | 0, 5, 0, 5 |
| Cross-attention fusion | 0.500 | 0.333 | 0.84 | 0, 5, 0, 5 |
| RTL length only | 0.500 | 0.451 | 0.82 | 4, 1, 4, 1 |

At the fixed decision threshold, **none of the four approaches improves on chance balanced accuracy on the new hosts**. The AUROC values describe ranking among just ten related samples; they do not rescue the fixed-threshold detection result or establish host-level generalization. The same PIC clean source is reused across four variants, leaving only two independent test hosts. The observed development-to-diagnostic collapse is the central finding of this pilot.

## Research claims supported today

The project can demonstrate a reproducible, checked gate-to-RTL *source provenance* pipeline and a controlled analysis of dataset shortcuts and cross-host transfer failure. It cannot support claims of accurate gate/RTL Trojan localization, grounded trigger or payload explanations, fix usefulness, fusion superiority on unseen hosts, or a publishable method improvement. The source-span checks do not assess semantic correctness, and no expert ratings exist.

## Reproduce the saved evidence

Use the project Python environment and the local, gitignored Trust-Hub archives and generated inputs. `results/provenance_clean_pilot/` and `results/external_diagnostic/` contain portable predictions, summaries, and input hashes.

```powershell
& .\trusthub\venv\Scripts\python.exe pipeline\provenance\verify.py runs\provenance_v1
& .\trusthub\venv\Scripts\python.exe pipeline\provenance\verify_rtl.py
& .\trusthub\venv\Scripts\python.exe pipeline\provenance\verify_rtl.py --expansion
& .\trusthub\venv\Scripts\python.exe pipeline\verify_artifact.py --pilot provenance_clean_pilot
& .\trusthub\venv\Scripts\python.exe pipeline\provenance\publish_external.py --verify
```

These checks validate file integrity, graph/embedding alignment, and metric arithmetic. They cannot validate scientific ground truth.
