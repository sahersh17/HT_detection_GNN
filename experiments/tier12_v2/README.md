# Tier 1 and Tier 2 mixed-edit pilot

This revision uses the same nine inspected hosts, payload effects, reference models, workloads, synthesis flow, and 0.90 stop threshold as tier12_v1. There are 27 rows in each revision and nine host groups across the two revisions combined. Each group contains an original and two edits of the same kind. Each edited class has three additions, three removals, and three replacements.

| Operation | Hosts | Construction |
| --- | --- | --- |
| Addition | CRC32, MAC, FIR | Add a guarded assignment to an existing enabled datapath. The benign override computes the specified result. The Trojan override changes it. |
| Removal | SPI, I2C, SRAM controller | Start with a split condition or data path. Delete a redundant qualification for the benign edit or an essential term for the Trojan. |
| Replacement | FIFO, ALU, PWM | Substitute an expression or literal in an existing branch. The benign replacement preserves the result. The Trojan alters a reachable case. |

## Verification and decision

All nine revised baselines passed Yosys equivalence against their retained v1 clean RTL. All nine benign variants passed equivalence against their revised baselines. Each Trojan matched the oracle on the bounded normal workload and diverged on its saved witness from reset. The first differing cycle and both output values matched v1 for every host. All 59,799 cycle outputs agreed between RTL and mapped simulation. During full-byte random stress, SPI diverged from the clean oracle on four output cycles. The other eight had zero differing cycles in that workload.

Each cell below is the equal-host proportion of pairs in which the Trojan scores higher, with half credit for ties. Fitted controls train on the other eight hosts in each fold. The decision uses both directions and both negative classes.

| Control | v1 original | v2 original | v1 benign | v2 benign |
| --- | ---: | ---: | ---: | ---: |
| Source characters | 1.000 | 0.500 | 0.500 | 0.389 |
| Graph nodes | 1.000 | 0.556 | 0.611 | 0.611 |
| Graph edges | 1.000 | 0.556 | 0.611 | 0.611 |
| Fitted source metadata | 1.000 | 0.500 | 0.389 | 0.611 |
| Fitted graph statistics | 1.000 | 0.500 | 0.500 | 0.389 |
| Directed WL, two rounds | 0.889 | 0.667 | 0.444 | 0.611 |

All 13 controls passed the frozen threshold on both comparisons. Edit kind is still tied to host in this design. Every addition Trojan had more nodes than its own original, and every removal Trojan had fewer. Report these as development results. The ver2 revision catalog admits zero synthetic training rows pending independent generation and review. Keep all revisions and derivatives of a host on the same side of any split. The next generator should cross edit kinds within hosts and produce both benign and malicious edits under an independently implemented procedure.

The supplementary gate-graph check identified three opposite-label pairs with identical node features and directed connectivity after relabeling. These were ALU and FIFO original versus Trojan, and CRC32 benign versus Trojan. A permutation-invariant gate-only detector must tie on those pairs even though the simulation witnesses differ. The other 15 pairs were structurally distinguishable. This finding applies to the cell-only input. A port- and pin-aware representation should be checked on these three witnesses before using the cohort for a graph-detector comparison.

## Reproduction

From the repository root, with the same toolchain as v1:

```powershell
python experiments/tier12_v2/pilot.py verify
.\trusthub\venv\Scripts\python.exe experiments/tier12_v2/pilot.py audit
```

The first stage builds the RTL, verifies behavior, and writes the semantic manifest. The second stage runs the original controls, writes the v2 catalog and decision, and compares the directed cell graphs with all detector node features preserved. The graph comparison is a supplementary diagnostic. The frozen controls and cutoff are unchanged.
