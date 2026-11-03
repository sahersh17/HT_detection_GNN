# Cross-project dataset expansion pilot

The primary experiment asks whether adding verified native-edit training hosts improves circuit ranking on the same evaluation circuits. The diagnostic estimator is the repository's linear graph-statistics classifier, with the same features, optimizer, seed, and a fixed 0.5 threshold. This initial probe runs despite a failed admission screen to measure the effect of dataset composition. No production or fusion checkpoint is replaced. The supplementary four-project training arm and gate-count check were added after the primary comparison.

## Dataset and verification

Six upstream revisions are pinned in build.py and in the intake manifest. SERV and wb2axip are held in reserve. They have no scored or labeled examples in this pilot. The four development blocks are a four-port grant arbiter, the SHA-1 message scheduler, the 16550 debug readout, and one output bit of a USB CRC-16 block. Each original has an equivalent guarded rewrite, a conditionally toggled output, and a conditionally suppressed output. Both fault families were written for this experiment. The equivalent rewrite is deliberately simple and can be optimized away. These variants stress interface integrity and availability. They do not constitute independently authored security attacks.

The directed testbench for each block checks 14 normal and two activated transactions for each arm, against a separately expressed expected value for the observed output. Both RTL and synthesized Verilog must return the same known values throughout. The CRC test observes one output bit. The SHA-1 test covers the initialized schedule word. These checks do not verify the full upstream components. Project URLs and held-out roles are in protocol.json. Exact source and mapped hashes, observations, and trigger conditions are in the intake. The source-lineage check uses the existing normalized-shingle and exact-module screen against original training hosts. No training host triggered it. Shared maintainers and circuit conventions remain possible across projects.

Of the 50 native-edit families, 49 supply three usable graphs. The scalar and interface audit covers all 50. No native class probe crosses the 0.90 cutoff, and top port names, directions, and widths agree within every triplet. Eight source-origin intervals cross a practical margin, and eight typed comparisons lack a confirmed distinction. The 17 wrapper hosts stay in the separate stress-test report. Neither the native cohort nor the new four pass the evidence required to admit them for detector training.

## Reproduction

Use the project Python environment and Icarus Verilog on PATH. The existing precision feature cache and the predecessor experiment artifacts must be available. For a fresh upstream checkout, clone each repository listed in protocol.json under runs/transfer_v1/upstream using its repository name, then check out the exact commit in build.py. The builder verifies clean tracked files and pinned revisions and only builds the four development projects.

1. Run `trusthub/venv/Scripts/python experiments/transfer_v1/build.py` from the repository root.
2. Run `trusthub/venv/Scripts/python experiments/transfer_v1/evaluate.py --audit`.
3. Run `trusthub/venv/Scripts/python experiments/transfer_v1/evaluate.py`.

## Reading the comparisons

The primary arms train on six original project triplets, then the same six plus 49 native triplets. Both see identical test examples. The supplementary arm also trains on the four new projects, excluding the entire target project when it belongs to the new panel. Each added project's positive and negative classes have equal total loss weight. Host-average AUROC first ranks the scored circuits within each host and then gives each host equal weight. Pooled AUROC also compares scores across hosts. The results file includes predictions, per-host recall and false positives, and paired percentile bootstrap intervals over hosts conditional on fitted scores. A zero-width interval on a tiny sample does not establish population-wide certainty.

| Evaluation set | Six projects | Plus native | Plus new projects |
| --- | ---: | ---: | ---: |
| Four new projects, host AUROC | 1.000 | 1.000 | 1.000 |
| Four new projects, pooled AUROC | 0.688 | 0.688 | 0.812 |
| PIC/memctrl, host AUROC | 0.500 | 1.000 | 0.500 |
| PIC/memctrl, pooled AUROC | 0.800 | 0.840 | 0.800 |
| Independent mutation additions, host AUROC | 0.889 | 0.556 | 0.556 |
| Independent mutation removals, host AUROC | 0.333 | 0.778 | 0.778 |
| Independent mutation replacements, host AUROC | 0.778 | 0.722 | 0.694 |

The four-project pooled score rises when other projects using the same intervention enter training. Gate count ranks both faults above both controls in every one of those projects. On PIC/memctrl, fixed-threshold balanced accuracy stays at 0.500 in all arms. With only two hosts, the apparent native-panel host-AUROC gain has a paired 95% interval of 0 to 1.

The same-engine and unseen-engine matrix uses the nine previously inspected Tier 1/2 hosts. In addition to the base training cohort, it includes authored v2 examples from other hosts for host-held-out tests, or from all nine for the seen-host engine-transfer test. The second engine uses Yosys-selected mutations with the project's own activation adapter. The three operators share the same nine hosts. See comparison.json for separate results and uncertainty for each operator and split. This is generator transfer on inspected data. Real-world performance, transfer to a new attack author, and incremental fusion AUROC remain unmeasured.
