# Golden-free local-node architecture experiment

Completed 2026-11-03. **Inference uses one suspect circuit only.** No clean twin, source diff, host identifier, or gate labels enter the model. The 185-circuit development dataset still mainly measures synthetic edit and fault detection, not general hardware Trojan detection. No reserved final candidate or previously inspected ten-circuit diagnostic was scored.

## Implementation

`train.py` adds a 127-input, 64-hidden local node scorer over verified `semantic_v1` graphs. It preserves all twelve recorded directed edge types in two typed message-passing layers, with residual features from the input and each layer. Candidate nodes are original cells, parameter/init value bits, and literal-valued connection pins. The circuit-label loss trains a multiple-instance model through one of three readouts: max node score, log-sum-exp of the top eight scores, or learned attention. One-layer max and two-layer top-k/attention variants were tested. This is local one- or two-hop context, which covers the planned short receptive-field alternative to extracted cones.

The fourth variant first trains the two-layer encoder on the 24 clean/benign fold-4 circuits to reconstruct randomly masked four-state value bits. It then fine-tunes the same top-k circuit-label model. The pretraining uses clean labels to select training examples but no clean reference at inference. Its masked-bit reconstruction loss fell from 0.672 to 0.084 over ten epochs.

All models use the same 38 hashed fold-4 training circuits (12 hosts, 24 negatives, 14 positives), one seed, 80 supervised epochs, Adam at 0.001, host-balanced positive/negative sampling, and gradient clipping. The prior normalized cell-pooling GNN from Stage 3 is the control. No validation score selected a checkpoint or hyperparameter; comparisons below use the final epoch. Best training snapshots are reported only to show whether any model reached the memorization gate.

## Training-fold fit

| Model | Best training pooled AUROC | Final training pooled AUROC | Final training equal-host AUROC | Final balanced accuracy at 0.5 |
|---|---:|---:|---:|---:|
| Prior cell-pooling GNN | 0.765 | 0.757 | 0.688 | 0.643 |
| One-layer typed max-node | 0.667 | 0.607 | 0.542 | 0.571 |
| Two-layer typed top-k MIL | 0.711 | 0.693 | 0.625 | 0.631 |
| Two-layer typed attention MIL | 0.762 | 0.757 | 0.604 | 0.631 |
| Two-layer top-k + clean masked-bit pretraining | 0.717 | 0.717 | 0.625 | 0.613 |

None approaches the preregistered near-perfect memorization target. The known `tt_um_rejunity_decoder` memory-bit edit remains nearly tied with its negative variants: the final positive-versus-benign probability gap is about 4.8e-7 with top-k and about 3.0e-5 with attention. This is consistent with the local bit signal still being weak after message passing or MIL selection. It does not prove the architecture cannot detect a verified trigger/payload Trojan.

## One-way unseen-host transfer

Models trained on fold 4 were scored once on the other four frozen development folds: 147 circuits, 48 unseen hosts, 96 negatives, 51 positives. `evaluate_transfer.py` and `transfer_controls.py` use the identical train/test split for every row. This is **not** five-fold cross-validation; each model had only 12 training hosts. The intervals are descriptive paired host bootstrap intervals from 10,000 resamples.

| Model | Equal-host AUROC | 95% host interval | Pooled AUROC | Balanced accuracy at 0.5 | Difference vs prior GNN, 95% paired interval |
|---|---:|---:|---:|---:|---:|
| Size-only logistic | 0.448 | [0.344, 0.552] | 0.505 | 0.506 | −0.156 [−0.333, +0.031] |
| Graph-aggregate logistic | 0.589 | [0.469, 0.703] | 0.521 | 0.520 | −0.016 [−0.130, +0.104] |
| Prior cell-pooling GNN | **0.604** | [0.479, 0.719] | 0.523 | 0.517 | Reference |
| One-layer typed max-node | 0.495 | [0.453, 0.531] | 0.519 | 0.517 | −0.109 [−0.229, +0.016] |
| Two-layer typed top-k MIL | 0.531 | [0.448, 0.615] | 0.552 | 0.517 | −0.073 [−0.203, +0.063] |
| Two-layer typed attention MIL | **0.604** | [0.484, 0.724] | 0.501 | 0.485 | 0.000 [−0.141, +0.141] |
| Two-layer top-k + clean pretraining | 0.536 | [0.469, 0.604] | 0.548 | 0.523 | −0.068 [−0.193, +0.063] |

The architecture changes do not improve equal-host ranking over the prior GNN. Attention ties it in point estimate, with a wide paired interval; top-k, max, and pretraining are lower. No model has useful threshold accuracy. The host-level result is more relevant than pooled AUROC because every host has its own negative and positive variants. As in Stage 2, the positives are mostly native literal and pin edits, for which a single circuit may have no identifiable malicious structure.

## Decision and remaining work

The local-node and clean-pretraining experiments were executed and did not pass the fit gate. A full multi-seed, five-fold GNN run on this development pool would add cost without a demonstrated capacity or transfer gain. Direct node supervision was **not** implemented because the project has no reviewed real Trojan-gate labels; automatic diff-derived candidate labels are not established ground truth. Explicit output-cone extraction was also not run: the one- and two-hop local scorers supplied the requested short-context alternative. A future cone experiment should first verify that its sampled regions contain both trigger and payload and compare against structural rarity controls.

The next data requirement is still a behavior-verified, diverse Trojan benchmark with matched benign decoys, reviewed gate labels if localization is claimed, and untouched independent hosts and insertion source. Golden-free inference remains the deployment setting.

Artifacts: `data/local_mil_v1/` contains model states, epoch curves, per-circuit transfer predictions, same-split controls, and bootstrap intervals. The scripts in this directory reproduce them.
