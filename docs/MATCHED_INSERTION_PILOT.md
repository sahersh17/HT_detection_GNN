# Matched insertion pilot: current status

This is an exploratory generator and control audit. It is **not** a validated
training benchmark or a publication result. The four hosts are AES, RS232,
memctrl, and PIC16F84. Each version starts from one hash-recorded clean Yosys
gate netlist per host and creates a matched clean, decoy, and Trojan variant.
Trojan gate labels are assigned from inserted cell identities and aligned with
the saved graph node order. Instance names are not used as model features.

## Verification completed

- All 12 variants of each of the three versions import into Yosys and pass hierarchy checks.
- Each host's three variants have identical node and edge counts.
- Exhaustive enumeration of the inserted two-valued output cone proves clean
  and decoy cancellation for all 256 input patterns and both original output
  values. The Trojan changes the selected output on two patterns. This local
  proof does not replace full sequential simulation of the host.
- Source netlist, generated JSON, and graph hashes are saved in each manifest.

## Shortcut controls and go/no-go decision

| Generator | Clean vs Trojan | Decoy vs Trojan | Decision |
| --- | --- | --- | --- |
| G1, `runs/matched_insertion_v1` | graph statistics and directed WL2: 1.0 equal-host pairwise AUROC | same: 1.0 | Fails shortcut gate |
| G1b, `runs/matched_insertion_v2` | size, gate count, graph statistics, WL2, input-fanout motifs: 0.5; output-XOR motif: 1.0 | same | Fails stronger shortcut gate |
| G1c, `runs/matched_insertion_v3` | size, gate count, graph statistics, WL2, input fanout, output-XOR motif: 0.5; output-cone equivalence: 1.0 | same | Simple semantic baseline solves task |

Each value is from leave-one-host-out probes on four host pairs. The host
bootstrap intervals are degenerate at the reported values. With only four
hosts, an interval containing 0.5 would **not** demonstrate absence of a
shortcut. The output-XOR control uses only the real output port and gate
connectivity: it counts whether consecutive XORs reuse the same control net.
It uses no generator names or labels. Its perfect result shows the G1b pilot
is still easy for a simple, valid structural baseline.

The gate-only graph representation also omits primary-input and real-output
roles. The G1b and G1c cell-only probes therefore have limited ability to see
the functional difference. Their chance scores must not be interpreted as a
hard benchmark for fusion or as evidence that a more complex model is needed.
The G1c output-cone baseline compares small AND/NOT trigger cones using
primary-input bit identities, with no synthetic names or labels. It solves all
four held-out hosts. A learned model cannot improve its ranking on this pilot.
This baseline is specific to the repeated XOR/comparator template; it is a
valid control for this pilot, not a general hardware-Trojan detector.

The G1c `prove_isomorphism.py` check found a feature-preserving directed-graph
isomorphism for clean-to-Trojan and clean-to-decoy on **all four hosts**. This
is stronger than chance-level baseline scores: every permutation-invariant
model using only the current gate features and edges must give the same
prediction to each variant. The functional difference is in primary-input
wiring and which cone drives a real output, both omitted from that graph.
The proof is recorded in `runs/matched_insertion_v3/isomorphism.json`.

## Next generator revision

The G1c revision implements the four-cone design. Its semantic baseline
result shows that repeating one XOR trigger template is too narrow a task.
The next generator needs multiple independently implemented trigger and
payload mechanisms, sequential and combinational behavior, verified benign
decoys, and host-held-out controls. The semantic baseline must remain in the
comparison. Do not select a model on these four inspected hosts.

The independent second generator, remaining hosts, generator-held-out split,
and real-data transfer remain gated on a shortcut-controlled pilot. The
separate detection and localization evaluation protocols should be frozen
before training either model.

## Reproduction

From the repository root, run the three scripts under each of
`experiments/matched_insertion_v1`, `experiments/matched_insertion_v2`, and
`experiments/matched_insertion_v3` in
this order: `generate.py`, `verify.py`, `controls.py`. For v3 also run
`prove_isomorphism.py`. Outputs are in the
matching `runs` directory. The scripts do not modify the TrustHub source files.
