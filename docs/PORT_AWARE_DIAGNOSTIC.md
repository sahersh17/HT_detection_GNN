# Port-aware graph diagnostic

The existing gate graph omits primary-input bits and real output ports. In the
four-cone matched pilot, clean, decoy, and Trojan gate graphs are provably
feature-preserving isomorphic on all four hosts. No permutation-invariant
gate-only GNN can distinguish them with that representation.

`experiments/port_aware_v1/build.py` adds one node per primary-input bit and
one per real output bit, with input-to-gate and gate-to-output edges. It adds
only input/output role flags; port names, benchmark IDs, trigger tags, and
node labels are absent from features. Constructed positive gate labels remain
aligned and are extended with zeros for the new port nodes. The twelve graphs
have hash-recorded source JSON and output tensors.

## Four-host probe

| Control | Matched clean vs Trojan | Decoy vs Trojan |
| --- | ---: | ---: |
| Graph statistics | 0.50 | 0.50 |
| Directed WL, 2 rounds | 0.50 | 0.50 |
| Directed WL, 8 rounds | 0.25 | 0.75 |

Values are equal-host pairwise AUROC under leave-one-host-out training on just
four hosts. At eight WL rounds, the feature histograms first differ at round
6 for PIC16F84 and round 5 for memctrl. They remain identical through round
8 for AES and RS232. This port-aware view restores some structural signal,
but it does **not** establish cross-host discrimination. A deeper attention
layer alone has no demonstrated benefit here.

The [output-cone equivalence control](MATCHED_INSERTION_PILOT.md) still ranks
Trojans above benign variants on all four hosts. This is the method any learned
model must be compared against. The pilot remains a no-go for a fusion claim;
the next valid study needs diverse trigger and payload mechanisms, a second
independent generator, more hosts, and a protocol frozen before model training.

Run `build.py` then `probe.py` in `experiments/port_aware_v1/`. The compact
manifest and probe results are saved under `data/port_aware_v1/`; the graph
tensors remain in the gitignored `runs/port_aware_v1/` directory.
