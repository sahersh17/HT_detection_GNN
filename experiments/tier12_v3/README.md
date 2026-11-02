# Independent mutation pilot on the nine Tier 1 and Tier 2 hosts

**Decision. Hold training.** The typed representation distinguishes the three previously colliding pairs. Every new matched triplet passed its behavioral checks. Across the new edit families, a gate-type histogram probe ranked the Trojan above its clean sibling in 27 of 27 host-held-out comparisons.

## Representation check

The check rebuilds the existing typed fusion view from the hash-verified mapped netlist. It uses detector node features, directed connections, pin roles and edge attributes, and excludes the class, graph ID and names from comparison. All three original collisions had different node-feature histograms even before neighborhood refinement. ALU had 314 nodes on each side, CRC32 had 310, and FIFO had 376. A distinguishable input establishes that the representation retains a difference. It does not measure detector performance.

## Independent source and matching policy

The independently authored engine is the installed Yosys 0.69 `mutate` pass at revision 9f75ca1f9. It enumerates forced-bit and conditional-inversion mutations on cells of each original host, including the affected pin, bit and control bit. The adapter selects among proposals on primary-data-connected cell inputs using a fixed hash order. Seed 739 controls the engine's conditional-bit proposals. The source and operator choices come from this engine instead of the v1/v2 substitution table. The nine hosts, the adapter's two-byte activation guard, and the construction of matched arms are shared project choices. This measures a second mutation procedure on inspected hosts.

- **Addition.** Add one proposed conditional toggle. The matched arms use a toggle that is inert or active at the trigger.
- **Replacement.** Under the same trigger, replace an input bit with a proposed constant value. The benign value agrees with the bit at activation.
- **Removal.** Construct a verified clean baseline with two canceling active toggles and one inert toggle on the same pin. Delete the inert toggle for the benign arm or one active toggle for the Trojan arm.

Each operation refers to the mutation program before the common Verilog emission and synthesis passes. A guarded replacement can increase the mapped gate count. The cancellation baseline is deliberately constructed. All three kinds occur on every host. There are 81 design arms, 72 distinct emitted Verilog texts, and nine host groups. The addition and replacement clean arms repeat the same text within each host. These netlist-derived Verilog texts are a different source modality from the authored v2 RTL.

The adapter stores exact engine commands, SHA-256 hashes of the engine binary and proposal lists, original source hashes, and the directed workload in run-length encoding. The reference model, class-specific expected behavior, host ID and operator plan stay outside detector inputs. Upstream implementation: [Yosys mutation pass](https://github.com/YosysHQ/yosys/blob/9f75ca1f9/passes/sat/mutate.cc).

## Verification

Yosys proved all 27 clean and 27 benign arms equivalent to their original host. It found no structural check errors during mapping. Each of the 27 Trojan arms agreed with the reference on the bounded normal workload and diverged from reset on its directed witness. All 263,421 cycle outputs agreed between the emitted Verilog and the mapped implementation. There were zero differing output cycles on the seeded 1,536-command full-byte stress workload. The restricted normal workload excludes the selected high-byte operand pairs by construction. The directed witnesses demonstrate activation and an observable functional effect. Typed graph features distinguish all 54 new clean/Trojan and benign/Trojan pairs.

## Frozen shortcut checks

The same five scalar and eight fitted controls ran within each edit family and across all three. Fitted controls held out an entire host across all derivatives. The mixed comparison ranks within each host and edit family, then gives equal weight to hosts. A win rate of at least 0.90 in either direction blocks admission. Counts below are tie-adjusted Trojan win rates with the named control.

| Control against clean | Addition | Replacement | Removal | Mixed |
| --- | ---: | ---: | ---: | ---: |
| Characters | 1.000 | 1.000 | 0.000 | 0.667 |
| Nodes | 1.000 | 1.000 | 0.000 | 0.667 |
| Edges | 1.000 | 1.000 | 0.000 | 0.667 |
| Fitted gate-type histogram | 1.000 | 1.000 | 0.556 | 1.000 |
| Fitted graph statistics | 1.000 | 1.000 | 0.889 | 0.963 |

On the benign/Trojan task, the strongest mixed control in either direction was the two-round directed WL histogram at 0.685. The strongest single-family benign comparison reached 0.889. On the separate source-identity diagnostic, emitted Verilog was longer than the corresponding v2 text for every matched host and arm. Keep generator results separate. Zero records were admitted for detector training.

## Reproduction

Run from the repository root with the project Python environment, YoWASP Yosys, the cached CodeBERT tokenizer, and Icarus Verilog on PATH. The first command uses the retained mapped v2 artifacts, reproducible via the v2 pilot verifier.

```powershell
.\trusthub\venv\Scripts\python.exe experiments/tier12_v3/typed_pairs.py
python experiments/tier12_v3/generate.py
python experiments/tier12_v3/verify.py
.\trusthub\venv\Scripts\python.exe experiments/tier12_v3/controls.py
```

The verification report links the compressed input schedules to first-difference cycle indices and output values in each manifest. Each edit family has its own decision file. The top-level decision file records the host-held-out mixed comparison, all threshold crossings, and the generator-identity diagnostic.
