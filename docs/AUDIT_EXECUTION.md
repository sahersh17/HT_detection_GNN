# Audit-first execution record, 2026-11-02

The [candidate paper position](AUDIT_PAPER_POSITION.md) and
`experiments/audit_v1/protocol.json` define the next prospective work. This
record distinguishes completed checks from gates that the existing data cannot
pass. All currently available Trust-Hub hosts have been inspected during
development; there is no untouched final host for the existing detection
results. A separate pinned external gate-level intake now has two reserved
candidate hosts, but has failed its benchmark gates.

| Work | Completed evidence | Current decision |
| --- | --- | --- |
| RTL metadata shortcut | 882 saved predictions across 21 feature/arm/setting groups; source hashes, folds, metrics, and predictions verified. Length plus tokenizer windows scores 0.857 BA, 0.855 AUROC on the original development arm. | The earlier 0.857 RTL BA is not evidence of semantic detection beyond simple metadata. |
| Error overlap and exact group test | On the original 42 sides, RTL and metadata each make six errors but share only two. Their three source-group metric differences are all zero; exact sign-flip p=1.0, with one-sided resolution no finer than 0.125. | Equal aggregate scores hide different RS232 decisions; no observed group-level superiority. See [shortcut audit](SHORTCUT_AUDIT_2026-11-02.md). |
| Six-host RTL comparison | 72 paired sides, 36 pairs, six inspected hosts, seven clean-source texts, five seeds. Count-plus-window control gives 0.935 equal-host AUROC versus 0.706 for CodeBERT mean/max; its fixed-threshold BA is 0.500. Predictions and all metrics recalculate from saved hashes. | Strong ranking shortcut with poor calibration; mixed language and flows, so a descriptive development result only. |
| Length-decoupling preflight | Two pilot pairs received unused-module padding on both sides. A padding-size rule identifies both clean sides; AES windows remain unmatched and one RS232 top inventory changes. | [Failed gate](LENGTH_DECOUPLE_PREFLIGHT.md); no detector retraining or semantic-signal claim. |
| Original lexical ablation | 126 transformed design-side compilation checks; original, comment, rename, and combined embeddings; within and transfer predictions. | Lexical sensitivity is demonstrated; causal leakage source is unresolved. |
| Matched insertion G1–G1c | Four hosts, clean/decoy/Trojan, local cone enumeration, graph hash and node-label alignment, transparent controls, graph-isomorphism diagnostic. | No-go for learned-method claims: output-cone rule is perfect on G1c. |
| b19 paired RTL | Three complete paired variants, six hash-verified VHDL embeddings, 346 chunks, source-line spans, matched graph records, one clean source group. | Include as one inspected host, not three independent hosts. No detection score inferred from successful embedding. |
| Host inventory | Eleven paired graph host families; six have paired original RTL embeddings, with seven unique clean source texts total. | A six-host cross-modal *development* pilot is technically feasible, but mixed languages and synthesis flows remain confounders. |
| Typed port graph | Twelve G1c graphs rebuilt with primary inputs, outputs, one-bit primitive pin roles, constants, and constructed labels. Graph and label checks pass. WL8 gives 0.25 clean-vs-Trojan and 0.75 decoy-vs-Trojan across four hosts. | The [typed-port diagnostic](TYPED_PORT_DIAGNOSTIC.md) does not clear the no-go gate; the semantic output-cone rule remains perfect. |
| Prospective audit rules | Versioned protocol and SHA256 snapshot of code, source manifests, and inspected results. | Applies only to future generator revisions and new hosts. It is not a retrospective preregistration or a sealed external test. |
| Independent red-team | No independent hardware reviewer or second generator available. Existing transparent rule ladder was run by the project. | Do not describe the audit as independently red-teamed. |
| Independent generator intake | Pinned DATE 2025 code and six candidate host files verified by Git blob hash. Four development hosts generated 16 byte-reproducible variants. Graph/candidate-label lineage verified for all; 10 have independent top-level output witnesses under SAT or simplified sequential trace, two fail SAT, two fail the tested sequential trace, two remain upstream-only. Gate count and graph size rank Trojan higher in all 16 pairs. | [No-go intake](INDEPENDENT_BENCHMARK_V2.md): no decoys, second insertion source, paired original RTL, or reviewed node labels. The two final-candidate hosts remain ungenerated. |
| Candidate-label review packet | A 162-row packet masks overt instance names and Trojan markers; a scoring script reports agreement and coverage if human labels arrive. | No independent reviewer, so no human agreement or validated real-gate score. Masking is incomplete. |
| Model comparison | Existing real-host models and five-seed mapped comparison are recorded in other results documents. | Defer a new fusion/augmentation superiority claim while the synthetic pilot fails the generator gate. |
| Real localization | Candidate labels and source spans exist; no reviewed real gate labels. | Do not score them as real localization ground truth. Constructed synthetic labels can support only synthetic evaluation. |

## Reproduce the added checks

From the repository root, with the local archives and generated graph files:

```powershell
$py = '.\trusthub\venv\Scripts\python.exe'
& $py experiments/rtl_lexical_v1/metadata_controls.py
& $py experiments/rtl_lexical_v1/verify_metadata_controls.py
& $py pipeline/provenance/embed_b19_vhdl.py
& $py pipeline/provenance/verify_b19_vhdl.py
& $py experiments/audit_v1/host_inventory.py
& $py experiments/audit_v1/compare_shortcuts.py
& $py experiments/audit_v1/six_host_rtl_control.py
& $py experiments/audit_v1/reproduce_tables.py
& $py experiments/audit_v1/freeze.py --verify
& $py experiments/length_decouple_v1/preflight.py
& $py pipeline/localization/export_blind_review_v2.py
& $py experiments/port_aware_v2/build.py
& $py experiments/port_aware_v2/verify.py
& $py experiments/port_aware_v2/probe.py
& $py experiments/independent_benchmark_v2/verify_graphs.py
& $py experiments/independent_benchmark_v2/shortcut_preflight.py
& $py experiments/independent_benchmark_v2/localization_controls.py
& $py experiments/independent_benchmark_v2/decision.py
& $py -m unittest discover -s pipeline/tests
```

The metadata predictions and summaries live in `data/rtl_lexical_v1/`. The
b19 tensors live in `runs/b19_rtl_v1/`, which is deliberately not committed;
their source and embedding hashes are in its manifest, and the compact audit
is in `data/audit_v1/`. `data/audit_v1/freeze.json` is a local hash snapshot.
The new [claim ledger](CLAIM_AUDIT_2026-11-02.md) separates table
recalculation from full raw-data reproduction and lists the evidence needed
before submission.

## Required new evidence for the next gate

1. An independently implemented insertion generator and mechanism matrix
   based on a declared threat model, with matched clean, benign decoy, and
   output-changing Trojan variants. The complete semantic and shortcut checks
   in the frozen protocol must pass before model training.
2. New independent clean hosts and a final cohort not inspected while tuning
   generators or models. Augmented variants of the six current hosts cannot
   serve as new host evidence.
3. Typed graph features for port roles, pin identity, and constants, with
   equivalence tests and no raw instance names. Re-run transparent baselines
   after this representation change.
4. Independent validation of real gate labels if a real localization claim is
   retained. The present synthetic constructed labels are exact only within
   their own generator and saved node order.

If these inputs remain unavailable, the defensible deliverable is a
reproducible audit with negative or descriptive results and an explicit
scope statement. It should not be presented as a successful fusion method.
