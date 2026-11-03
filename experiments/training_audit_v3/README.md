# Training and preprocessing investigation

The earlier all-clean behavior occurred on the training data as well as the ten diagnostic circuits. Seed-42 training AUROC was approximately 0.52 for both architectures. That observation establishes a fitting problem before interpreting external transfer.

## Checks and controls

The input verifier checks all 195 records. Graph tensors and connections are unchanged by text sanitization, labels match the documented arms, all 20 graph channels and 768-dimensional RTL vectors are finite, gate channels remain one-hot, and every edge index is in range. Training and diagnostic host sets are disjoint. The six changed RTL model views compile with their original top modules and include files.

The text sanitizer removes case-insensitive occurrences of trojan, tjfree, tjin, infected and malicious. Comments containing those words become whitespace. Affected identifiers receive consistent neutral hashed names. Other occurrences receive neutral text. It removes 29 occurrences across two training attack variants and four diagnostic variants. Labels and provenance remain in metadata, which the model forward methods do not read. The frozen encoder revision and all graph tensors are preserved.

Both models reach 100% accuracy on a four-circuit UART positive control after 200 balanced gradient steps. That control uses dropout zero and learning rate 0.001. It demonstrates that the architecture, labels and backward path can learn a readily distinguishable subset. It does not establish that the full dataset is separable.

An intercept-only Adam control converges to 0.5 under both weighting recipes. Single-circuit updates alone therefore do not inevitably create a clean prior.

## Gradient clipping finding

The old recipe weights each circuit loss, clips its gradient, then updates Adam. At the collapsed augmented GNN checkpoint, every positive circuit is clipped and no negative circuit is clipped. Mean positive classifier-bias gradient changes from -1.348 before clipping to -0.076 after clipping. The negative mean stays at +0.041. Across the 185 circuits, clipping reduces the intended mean correction from -0.447 to -0.000535.

This is a measured effect in the full network. The interaction between per-circuit class weights and gradient clipping nearly removes the correction that should increase positive predictions. The corrected recipe samples both labels for each host, accumulates the average gradient across four hosts, and then clips and updates once.

## Representation finding

One native benign/fault pair, tt_um_rejunity_decoder, has exactly identical ordered graph feature and connection tensors with opposite labels. The netlists differ in DATA bit 20 of a memory-initialization cell. One has a constant zero and the other a constant one. The original graph builder only connects integer net identifiers and does not encode that constant bit. The GNN cannot distinguish these two inputs.

Opaque memory cells occur in 23 training hosts in the inspected six-project and native panels. This inventory does not prove a class collision in each host. The graph representation is preserved in the controlled rerun so the optimizer comparison keeps the same inputs. Its loss of memory initialization information remains unresolved.

Mean RTL embeddings also have median cross-host distance 3.144 versus 0.0448 between a positive and the mean negative of its own host. The corresponding graph-statistic distances are 2.196 and 0.00708. These measurements indicate much larger host variation than edit variation in these summaries. They do not establish that the full nonlinear model has no usable signal.

## Longer controlled runs

The supervised pool is the same 185 circuits as augmentation_v2. The ten previously inspected PIC16F84/memctrl diagnostic circuits are held out by host. All models use the same sanitized RTL views. No input normalization or architecture dimensions change.

The balanced recipe runs 100 epochs with seeds 42, 43 and 44. The legacy recipe control uses seed 42, with 100 GNN epochs and 25 fusion epochs. The fusion control has 4,625 optimizer updates, exceeding the corrected run's 1,500 updates. Its budget was shortened for compute after the GNN control completed, without selecting on test performance. Both use the default architecture and dropout 0.2, AdamW learning rate 0.0003, weight decay 0.001, and gradient clipping at one. Balanced sampling sees one example of each class per host per epoch, selecting the design arm randomly. The legacy recipe traverses all 185 records per epoch with the original family/class weights. Thus the recipes have different optimizer update counts, which are recorded.

Checkpoints at epochs 5, 25, 50 and 100 are specified before scoring. The corrected endpoint is epoch 100. The legacy fusion endpoint is epoch 25. Test outcomes are never used to select checkpoints, thresholds or hyperparameters. A secondary threshold is fitted on training predictions only and reported alongside the fixed 0.5 threshold.

Training omits attention-weight exports through an optional return_attention flag. Existing forward callers retain their default outputs. A dropout-free numerical check confirms equivalent logits and gradients, with maximum differences of 5.96e-8 and 2.98e-7.

## Reproduction

Use the repository Python environment.

1. Run experiments/training_audit_v3/audit.py and positive_controls.py.
2. Run experiments/training_audit_v3/optimizer_control.py and clipping_audit.py.
3. Run experiments/training_audit_v3/sanitize.py and verify_inputs.py.
4. Run experiments/training_audit_v3/verify_sanitized.py with Icarus Verilog available.
5. Run experiments/training_audit_v3/verify_attention.py.
6. Run experiments/training_audit_v3/train.py. Optional seed groups can run independently using --seeds 42 and --seeds 43 44. Run once without that option after completion to collate all eight saved runs.

The numerical report is data/training_audit_v3/training_results.json. Individual checkpoints, curves and predictions are stored under runs/training_audit_v3. Sanitized model text and frozen embeddings are hashed in data/training_audit_v3/manifest.json.
