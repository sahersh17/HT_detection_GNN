# Gate-label feasibility and improvement gate

This audit is a separate, unreviewed candidate-label version for the mapped `new_gate_v1` graphs. It never changes the supplied graphs or the existing source-traced AES graphs. Candidate files carry the exact graph ID, ordered node names, and input hashes. `pipeline/localization/score_localization.py` will reject them because `reviewed` is false. The local archives also yielded paired s15850, s35932 and s38417 mapped netlists; all 28 mapped graphs across five families passed reconstruction and source checks.

## Mapped netlists

| Benchmark | Trojan-only graph cells | Removed cells | Shared cells with changed mapped connections | Trojan-named cells |
|---|---:|---:|---:|---:|
| s38584-T100 | 9 | 0 | 11 | 8 |
| s38584-T200 | 83 | 0 | 4 | 83 |
| s38584-T300 | 731 | 0 | 4 | 731 |
| s15850-T100 | 27 | 0 | 2 | 22 |
| s35932-T100/T200/T300 | 15 / 12 / 36 | 0 | 8 / 4 / 0 | 14 / 11 / 11 |
| s38417-T100/T200/T300 | 12 / 15 / 44 | 0 | 1 / 4 / 0 | 12 / 15 / 16 |
| b15-T100/T200 | 227 each | 798 each | 1,762 each | 0 |
| b15-T300/T400 | 228 each | 798 each | 1,762 each | 0 |

The three s38584 added-cell counts match the 9/83/731 Trojan-node counts in TrojanSAINT's Table III, but count agreement does not verify each cell. The ninth T100 added cell is `NOT_test_se`; its output enters `Trojan_Trigger`, which drives `Trojan_Payload` and a changed flip-flop data input. T100 and T200 candidate labels are hash-frozen in `s38584_candidate_freeze.json` with coverage 9/6,462/11 and 83/6,469/4 for positive/negative/unknown nodes, respectively. Both remain unreviewed. T300 is **quarantined**: the inserted trigger drives `Tj_Trigger`, while the payload mux selects on `Trigger_out`; Yosys warns that the latter is implicitly declared. Its intended trigger-to-payload behavior has not been established.

The new s15850-T100 and s35932-T300 graphs have one more added cell than published Trojan counts. Their candidate files are marked `correspondence_discrepancy_unreviewed`. Shared cells with changed connections are unknown (`-1`), not benign. The B15 pairs have major structural replacement and are deliberately not given node-label files.

The `rtl_hierarchy_survey.json` inventory found Trojan-only module names in all 17 AES variants and two of three s38584 variants. In AES, clean and Trojan source trees use different wrappers, including `top`, so module-name difference alone is not a Trojan label. B15, MC8051, PIC16F84, RS232, and memctrl have no Trojan-only module declaration in the selected source sets. This survey does not establish whether a same-named module contains an inserted instance.

## First structural controls

Against seven **unreviewed** candidate-labeled variants across s35932, s38417 and s38584, equal-host AUROC is 0.47 for fan-in, 0.29 for fan-out, 0.47 for proximity to outputs, 0.77 for gate-class rarity and 0.27 for fan-out divided by output distance. The 95% host-bootstrap interval for gate-class rarity is 0.63–0.84, but it uses only three inspected hosts and cannot establish a generalization gain. `structural_controls.json` reports tie-aware expected hit@k, random hit@k, AP, AUROC, and first-positive rank bounds per design. The older three-variant s38584 diagnostic includes quarantined T300 and must not be used as the primary result.

`review_packet/blind_nodes.csv` contains 162 stratified cells across the seven graph variants, without candidate labels or model scores. `review_key.json` is separate. No contributor has reviewed the packet yet.

The newer `review_packet_v2/blind_nodes.csv` removes graph source paths and
instance names from the reviewer view, gives each design an opaque ID, and
masks identifiers containing overt Trojan, trigger, and payload words. All
162 excerpts pass an overt-marker scan. Its separate
`review_locator_key_v2.json` restores graph/node identity after review.
`pipeline/localization/score_review_v2.py` can calculate coverage and agreement
for two independent human reviews, or compare one human review with the
automatic candidate labels. The latter is method agreement, not inter-rater
reliability. The packet remains only partially blind because circuit context
can reveal insertion structure. No agreement score is reported without actual
reviewer labels.

## Next gate for improved results

1. Audit every proposed positive, beginning with `NOT_test_se`, and a stratified sample of candidate negatives and unknowns. Preserve disagreements and reviewer expertise. Without independent hardware review, describe these as benchmark-derived or construction-derived labels, not independently verified truth.
2. Add several functionally distinct clean hosts and insertions from independent templates or tools. Freeze host and generator splits before training. Keep a separate versioned graph/provenance record for each synthesis recipe and verify that inserted logic survives synthesis.
3. Train a node model only after the label semantics are frozen. Compare it with random, degree, gate-class and structural-diff controls on held-out hosts. Report per-host AP, AUROC, recall at a fixed inspection budget, and label coverage. Use 3–5 seeds and do not tune on the final hosts.
4. Keep graph-level detection as a separate task. A localization model improves the project only if it helps both node ranking and held-out-host detection without relying on the clean twin at inference.

Reproduce the current audit from the repository root:

```powershell
trusthub/venv/Scripts/python.exe pipeline/localization/audit_gate_labels.py
trusthub/venv/Scripts/python.exe pipeline/localization/survey_rtl_hierarchy.py
trusthub/venv/Scripts/python.exe pipeline/localization/freeze_s38584_candidates.py
trusthub/venv/Scripts/python.exe pipeline/localization/structural_controls.py
trusthub/venv/Scripts/python.exe pipeline/localization/report_structural_controls.py
trusthub/venv/Scripts/python.exe pipeline/localization/export_blind_review.py
trusthub/venv/Scripts/python.exe pipeline/localization/export_blind_review_v2.py
```

The generated files are in `data/localization_gate_audit/`. This is a candidate-label and baseline diagnostic, not a publication localization result.
