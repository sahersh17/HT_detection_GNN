# Claim-to-evidence ledger

This ledger lists statements currently safe to use in a draft. Any new result
sentence needs an input version, a control, an evaluation unit, and a scope
limit before submission. The current state is an **audit-paper candidate**,
not a publication-ready detector or a validated real localization system.

| Draft claim | Evidence and version | Control and unit | Limit |
| --- | --- | --- | --- |
| Original RTL model has no measured fold-level gain over a metadata-only model. | `data/audit_v1/error_overlap.json`; original 42-side prediction hashes. | Same three clean-source folds; exact paired sign flip, p=1.0. | Three groups make the test coarse; equal scores mask different RS232 errors. |
| A length-plus-window control ranks pairs strongly on the expanded development cohort. | `data/audit_v1/six_host_summary.json` and `six_host_predictions.json`; 0.935 equal-host AUROC over five seeds. | CodeBERT arm, length-only arm, window-only arm; six held-out host families. | All hosts inspected; seven clean sources; mixed language and flow; poor fixed-threshold calibration. |
| The first length-matching intervention failed its shortcut and synthesis checks. | `data/length_decouple_v1/preflight.json`; two pilot pairs. | Padding assignment-count rule; character, line, window, and top inventory checks. | No detector was retrained; no conclusion about semantic RTL signal. |
| The G1c synthetic benchmark is solved by an output-cone control. | `docs/MATCHED_INSERTION_PILOT.md` and `docs/TYPED_PORT_DIAGNOSTIC.md`. | Four inspected hosts; constructed clean/decoy/Trojan sides. | No claim of model improvement or real-world transfer. |
| Existing real gate labels are candidates. | `data/localization_gate_audit/review_packet_v2/manifest.json`; 162 masked review rows. | Source traces and candidate labels; review scoring script prepared. | No independent reviewer and no validated node-level localization score. |
| The pinned independent insertion framework can generate reproducible gate netlists, but this cohort fails benchmark intake. | `data/independent_benchmark_v2/manifest.json`, `graph_verification.json`, `formal_combinational.json`, `sequential_trace.json`, and `decision.json`; pinned [DATE framework](https://github.com/gkaggarwal/HT_Benchmark_HT_Insertion_Framework_DATE_2025/tree/c7a1269c2c6fd4ebfaec2245c7613dba84fd0228). | Eight independent process reruns; top-level SAT or simplified sequential trace; source gate and mapped graph-size controls on 16 development pairs. | Four SAT witnesses, six simplified sequential output witnesses, two SAT failures, two sequential trace failures, two upstream-only variants; count controls rank 16/16. No decoys, second generator, original RTL pairs, or reviewed node labels. |

Do not currently state that fusion improves generalization, that real Trojan
gates are accurately localized, that padding exposed semantic RTL signal, or
that the independent generator has passed the benchmark gates. Keep the four
generator failures and the T300/B15 findings in the limitations and related
negative-results discussion, with their existing evidence versions.

## Release and clean-clone check

The compact prediction tables can be recomputed using
`experiments/audit_v1/reproduce_tables.py`; this is a **table-recalculation**
check, not a full raw-data reproduction. A full clean clone still needs the
local Trust-Hub archives, cached pinned CodeBERT weights, YoWASP Yosys,
generated embeddings, and synthesis outputs. Before submission, a separate
person should run the documented environment and hash-compare every headline
table. Trust-Hub redistribution rights must be checked before publishing its
netlists. The raw files and `runs/` artifacts must not be silently assumed to
be included in a public repository.
