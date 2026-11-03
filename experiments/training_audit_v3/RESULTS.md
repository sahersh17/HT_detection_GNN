# Executed training and preprocessing audit

The old training recipe creates a substantial clean bias, and the graph representation also loses real circuit information. Corrected 100-epoch training improves ranking on this small diagnostic, but test accuracy stays at 50% in every run.

## Completed runs

The corrected recipe uses the same 185 supervised circuits, sanitized frozen RTL embeddings and unchanged 20-channel graphs. Both architectures run 100 epochs with seeds 42, 43 and 44. Test circuits remain the same ten PIC16F84/memctrl designs from two previously inspected hosts.

| Model | Previous five-epoch test AUROC | Corrected 100-epoch test AUROC | Corrected training AUROC | Corrected test accuracy |
| --- | ---: | ---: | ---: | ---: |
| gnn | 0.267 | 0.613 | 0.594 | 50.0% |
| fusion | 0.333 | 0.520 | 0.603 | 50.0% |

These rows average three seeds. The earlier run differs in training recipe, duration and explicit-word sanitization. The longer legacy control shares the sanitized inputs with the corrected run. These contrasts do not isolate every individual optimization change.

| Model | Seed 42 test AUROC | Seed 43 test AUROC | Seed 44 test AUROC |
| --- | ---: | ---: | ---: |
| gnn | 0.80 | 0.84 | 0.20 |
| fusion | 0.84 | 0.52 | 0.20 |

Training-derived thresholds also leave test accuracy at 50% in all six corrected runs. At threshold 0.5, each run assigns all ten circuits to one class. Corrected equal-host AUROC averages 0.667 for GNN and 0.750 for fusion. Both the pooled and host metrics remain unstable across seeds and conditional on only two inspected hosts.

## Training finding

Seed-42 old checkpoints also predicted every training circuit as clean and had training AUROC near 0.52. The collapse therefore precedes host transfer. The old recipe weights and clips one circuit at a time before an Adam update. In the collapsed GNN, every positive circuit gradient is clipped and no clean gradient is clipped. The mean positive classifier-bias gradient changes from -1.348 to -0.076, while the clean mean stays at +0.041. Aggregate intended correction shrinks from -0.447 to -0.000535.

The corrected recipe samples both labels per host, averages gradients across four hosts, clips once, and updates once. The intercept-only control converges to 0.5 under both recipes, showing that the failure depends on the full-network gradient interaction rather than an inevitable class-prior effect of Adam.

The longer legacy controls still fit poorly under the balanced objective. GNN after 100 epochs and 18,500 updates has training balanced NLL 1.715. Fusion after 25 epochs and 4,625 updates has training balanced NLL 2.052. Corrected runs have 1,500 updates and mean training NLL approximately 0.690 for GNN and 0.696 for fusion, close to the uninformative balanced-class value 0.693. The correction improves probability balance, but the full corpus remains weakly fitted.

The legacy fusion control budget was reduced for compute before its final endpoint, without choosing on test scores. The corrected runs retain their fixed 100-epoch endpoint. All checkpoints at epochs 5, 25, 50 and 100 were specified in advance where the budget allows them. Epoch 100 is reported for corrected runs, even when an earlier test score was higher.

## Preprocessing and dataset findings

All 195 records passed label, finite-value, one-hot gate-type, edge-bound and dimensional checks. Graph tensors are exactly unchanged after wording removal. Sixty training host groups and the two diagnostic host groups are disjoint.

Explicit attack terminology is absent from all model RTL views. The sanitizer removes 29 occurrences across six source views, and all six changed views compile. At fixed old fusion weights, sanitized wording leaves test AUROC unchanged for all three seeds. Maximum probability change is 0.000177, so the removed wording does not explain the previous clean-only predictions.

The benign/fault pair tt_um_rejunity_decoder has identical graph features and connectivity with opposite labels. The netlists differ at constant DATA bit 20 of a memory-initialization cell. The graph builder omits that constant value. No deterministic GNN can distinguish this pair from the supplied graph tensors. Opaque memory cells occur in 23 training hosts in the inspected panels; class conflicts in every such host are not established.

This representation issue remains in the controlled rerun. Repairing memory/constant encoding requires a separately versioned graph rebuild. The current comparison holds graph inputs fixed to diagnose the optimizer.

Both networks can memorize the four-circuit UART positive control with dropout disabled, attaining AUROC and balanced accuracy 1.0. That control confirms gradient flow and the ability to learn a readily distinguishable subset. It does not establish separability of all 185 circuits.

Median cross-host feature variation is about 70 times the within-host edit distance for mean RTL embeddings and about 310 times for graph statistics. These summaries support substantial host variation relative to the synthetic edit signal. They do not prove that all model-accessible signals are unusable.

## Interpretation

There is direct evidence of a training-recipe problem and a graph information-loss problem. Longer balanced training reduces the clean prior, but the models still underfit the broad training corpus and fail fixed-threshold detection on the external diagnostic. These results cannot attribute all remaining failure exclusively to dataset quality; representation capacity and optimization remain involved.

Exact numeric results are in data/training_audit_v3/summary.json and training_results.json. The README documents reproduction, checks, input sanitization, controls and the optional attention-export optimization. Eight model checkpoints and all milestone predictions are retained under runs/training_audit_v3.
