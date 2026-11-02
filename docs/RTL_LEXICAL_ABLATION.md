# RTL lexical ablation, exploratory development result

The original RTL-only classifier was evaluated on 21 AES/RS232 clean–Trojan
pairs, grouped into three independent clean-source folds. This ablation uses
those same folds and the same frozen CodeBERT encoder. It changes only
comments, non-keyword identifier spelling, or both. Character count and line
positions are preserved; strings, number literals, and preprocessor directives
are left intact. Included RS232 headers are transformed with their `.v` files.
The original source files are untouched.

All 126 transformed design-side records passed the Yosys Verilog frontend
and hierarchy check, representing 72 unique compilations. The 126 embeddings
contain 67 distinct transformed input texts. For the eight RS232 files with
no comments in the embedded `.v` text, the comment-control embeddings are
exactly equal to the earlier baseline tensors. Two lexical regression tests
also pass. Compilation checks are not a full sequential equivalence proof.

## Results

Balanced accuracy (BA) uses the original fixed threshold of 0.5. AUROC and
paired win rate use scores. “Within” retrains the same linear head on each
transformed training fold. “Transfer” trains on original RTL and tests on
transformed RTL without recalibration.

| RTL arm | Evaluation | BA | AUROC | Paired win rate, half credit for ties |
| --- | --- | ---: | ---: | ---: |
| Original | Within | 0.857 | 0.864 | 0.905 |
| Comments removed | Within | 0.762 | 0.828 | 0.905 |
| Comments removed | Transfer | 0.500 | 0.596 | 0.619 |
| Identifiers renamed | Within | 0.905 | 0.868 | 0.905 |
| Identifiers renamed | Transfer | 0.571 | 0.739 | 0.857 |
| Both | Within | 0.762 | 0.828 | 0.905 |
| Both | Transfer | 0.500 | 0.549 | 0.571 |

All within-arm runs rank the Trojan above the clean design in 17 of 21
pairs, with four ties. The four ties are the RS232 pairs. The RS232 held-out
fold has BA 0.500 in every within-arm run. Identifier renaming increases
thresholded BA on one AES fold but does not improve pairwise ranking; it is
therefore **not** evidence of better host generalization. Comment removal
changes the classifier's score distribution, and the original head transfers
poorly to that new distribution. This demonstrates lexical sensitivity. It
does not establish that comments or naming caused the original failures:
tokenization and the embedding distribution also change. The three inspected
source groups are too few for a publication-level claim.

The next detection experiment should use more independent hosts and
train-only threshold calibration, with equal-host AUROC and paired ranking as
primary measures. The model protocol should be frozen before evaluating new
hosts. The matched synthetic pilot has a separate [no-go audit](MATCHED_INSERTION_PILOT.md).

## Metadata-only control added 2026-11-02

The previously reported character/line-length baseline was rerun on the same
42 samples and frozen folds alongside CodeBERT window count. Length plus
window count reaches **0.857 balanced accuracy and 0.855 AUROC**, compared
with 0.857 and 0.864 for the original RTL embedding classifier. Both have
17 Trojan-over-clean pair wins and four ties. Character/line length alone
reaches 0.786 balanced accuracy and 0.828 AUROC; window count alone reaches
0.500 and 0.637. All features are standardized using only each training fold.

The lexical transforms keep character and line counts identical, so their
length-only predictions remain exactly equal. They change total CodeBERT
windows from 1,078 originally to 1,210 with comments removed, 1,174 with
renaming, and 1,310 with both changes. The length-plus-window control drops
to 0.667 balanced accuracy when the original-trained head is transferred
to comment-stripped sources, and to 0.500 with both transforms. This is a
strong metadata shortcut and a distribution-shift warning on inspected data;
it does not prove causation or generalization to new hosts.

The hash-verified, per-sample results are in
`data/rtl_lexical_v1/metadata_controls.json` and
`metadata_controls_predictions.json`. Run `metadata_controls.py` and
`verify_metadata_controls.py` from `experiments/rtl_lexical_v1/` to regenerate
and check them.

## Reproduction and evidence

Run `prepare.py`, `verify.py`, `embed.py`, `evaluate.py`, and
`verify_report.py` in
`experiments/rtl_lexical_v1/` with `trusthub/venv/Scripts/python.exe` from the
repository root. The large transformed sources and embeddings are in
`runs/rtl_lexical_v1/`. The small tracked
`data/rtl_lexical_v1/summary.json` and `predictions.json` contain the results
and hashes of the generated manifests.
