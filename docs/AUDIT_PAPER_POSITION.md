# Cross-modal shortcut audit: research position and contribution boundary

Status: development evidence, 2026-11-02. This is a candidate paper position,
not a claim that a publication-level result has been obtained. The inspected
Trust-Hub hosts and insertion pilots cannot be relabeled as a prospective test.

## Prior work and the remaining question

| Work | Established contribution | What remains distinct here, if validated |
| --- | --- | --- |
| [Xiao et al., 2026](https://arxiv.org/abs/2609.07199) | Feature-based gate detection degrades from pooled gate splits to leave-one-host-family-out on 16 netlists and five hosts. | Evaluate graph-level GNN, RTL, and fusion with paired clean/Trojan and decoy controls, source and synthesis provenance, and a transparent solver ladder. A host split by itself is not novel. |
| [Krieg, 2023](https://repositum.tuwien.at/bitstream/20.500.12708/191214/1/Krieg-2023-Reflections%20on%20Trusting%20TrustHUB-am.pdf) | Audits correctness, maliciousness, stealthiness, and persistence; only three of the 83 selected designs pass all criteria. s38584-T300 is classified ineffective. | Reproducible exact trigger–payload connectivity evidence for the local T300 version, if independently verified; not a new general discovery that Trust-Hub contains ineffective designs. |
| [TrojanForge](https://arxiv.org/html/2405.15184) | Reinforcement-learning insertion and discussion of benchmark and synthesis limitations. | Compare controlled, matched decoys and host/generator transfer; do not claim automated insertion is new. |
| [Popryho et al., 2026](https://arxiv.org/html/2511.08703) | Scalable, function-preserving gate-level HT-like pattern insertion. | Require actual Trojan-on output divergence and verified benign decoys. Their function-preserving patterns do not supply that malicious-behavior check. A reusable public implementation was not confirmed. |
| [SALTY](https://arxiv.org/html/2502.14116) | Structural node-level detection and an author-reported unseen-design evaluation. | Compare task, split, label, and metric definitions before citing numbers as directly comparable. Our current real-node labels are unreviewed. |

This table is a positioning aid, not a complete systematic literature review.

## Empirical contribution currently supported

The corrected RTL study has 42 samples, 21 pairs, three independent clean
source groups, and two host families. The CodeBERT linear classifier reaches
0.857 balanced accuracy and 0.864 AUROC on these inspected folds. A classifier
using only RTL character count, line count, and CodeBERT window count reaches
**0.857 balanced accuracy and 0.855 AUROC** with the same folds and fitting
rule. Both rank the Trojan above clean in 17 pairs and tie in four. Character
and line counts alone reach 0.786 balanced accuracy; window count alone reaches
0.500. These values are saved with per-sample predictions and source hashes in
`data/rtl_lexical_v1/metadata_controls.json` and
`metadata_controls_predictions.json`.

Lexical transformations preserve character and line counts but change total
CodeBERT windows: original 1,078; comments removed 1,210; renamed 1,174;
both 1,310. The original-trained text classifier transfers poorly to the
transformed sources. This shows sensitivity to representation and a strong
metadata-only competitor. It does not prove the text classifier uses only
length or that comments caused the observed host failures.

The four-host G1c synthetic pilot has exact constructed labels and a verified
local output divergence, but a simple output-cone equivalence rule ranks all
Trojans above the two benign variants. Its gate-only graphs are isomorphic
across classes under the current features. It fails the benchmark gate and
must not be used to claim a learned model gain. The port-aware diagnostic
restores some information but does not solve host transfer.

The complete b19-T300/T400/T500 VHDL pairs have now been embedded as a
separate, hash-checked version: six design sides, 346 CodeBERT windows, and
**one** independent clean source. Joining the existing manifests gives six
paired host families with graph and original RTL modalities: AES, RS232,
memctrl, PIC16F84, MC8051, and b19. They contain seven independent clean
source texts because AES has two. The host inventory is saved in
`data/audit_v1/host_inventory.json`. These are inspected development hosts;
the VHDL and Verilog embeddings use different source/window conventions and
must be compared with those differences explicit.

A later [typed-port diagnostic](TYPED_PORT_DIAGNOSTIC.md) adds primitive pin
roles and constants to the G1c graph view. Its four-host WL results remain
weak and the output-cone rule still solves the pilot, so it does not reverse
the no-go decision.

## Candidate claim after a new prospective test

> A hash-verifiable, cross-modal evaluation protocol reveals and controls
> source-length, tokenization, graph-structure, synthesis-flow, and synthetic
> insertion shortcuts in hardware-Trojan detection. On independent hosts and
> generators, it measures whether graph, RTL, or fusion models add value beyond
> transparent rules, and it reports failure modes when they do not.

The prospective benchmark must include independently implemented trigger and
payload mechanisms, real output-changing witnesses, matched benign decoys,
and new host designs. Mechanisms must come from an explicit threat model;
they cannot be selected to make fusion win. The local audit snapshot in
`experiments/audit_v1/protocol.json` is frozen only for **future revisions**.
It is not a retroactive preregistration for the inspected studies.

## Acceptance and claim limits

1. A new generator must pass semantic checks and remain challenging after the
   full transparent control ladder. A confidence interval containing chance
   with four hosts is not evidence that a shortcut is absent.
2. Report every held-out host, generator, mechanism, positive count, and
   uncertainty. Model superiority requires a gain over the strongest relevant
   control and both unimodal models on untouched hosts and a held-out generator.
3. Synthetic constructed labels support synthetic localization only. Real
   gate-level localization remains unscored without independently validated
   labels. With no hardware reviewers, omit engineer-usefulness claims.
4. Trust-Hub transfer after the current rounds of inspection is a descriptive
   sanity check. A publication-level external result needs a genuinely new
   prospective cohort and verified source/flow compatibility.

Reproduce the new control with
`trusthub/venv/Scripts/python.exe experiments/rtl_lexical_v1/metadata_controls.py`,
then run `verify_metadata_controls.py` in the same directory. The prospective
audit rules and local freeze are in `experiments/audit_v1/`.
