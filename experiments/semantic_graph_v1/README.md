# Constant and memory-preserving graph repair

## Most recent RTL-only evidence

The most recent archived CodeBERT-only external arm is the three-epoch, seed-42 typed_fusion_v1 ablation with structured RTL features removed. On ten PIC16F84/memctrl circuits, AUROC is 1.00, accuracy and balanced accuracy are 0.50, macro F1 is 0.333, and all five pairs rank correctly. Every circuit is classified as Trojan at threshold 0.5. The CodeBERT-plus-structured RTL arm has the same metrics.

The later 100-epoch audit trained GNN and fusion branches. It produced no newer RTL-only metric. These older RTL-only results use the 42-circuit AES/RS232 development pool and are not a matched baseline for the newer 185-circuit augmentation experiment.

## Faults found

1. Literal-valued pin connections were omitted from graph edges and node features. This discarded 0, 1, x and z values.
2. Memory DATA contents, INIT/reset parameters and net initialization values were not visible to the model.
3. Separate memory initialization/read/write cells were not connected by their shared MEMID state.
4. A set of cell-to-cell edges collapsed pin identity, bit position and parallel connections.
5. Different memory operations and internal cell variants could share the legacy OTHER gate category.
6. A circuit with no synthesized cells was rejected even when it had valid constant outputs.

The known tt_um_rejunity_decoder benign/fault pair differs at DATA bit 20 of a $meminit cell. Its old ordered feature and connectivity tensors are identical despite opposite labels.

## Implemented representation

The semantic_v1 graph retains original cell rows as a prefix and adds anonymous net, port, pin-bit, parameter-bit, memory-state and initial-value nodes. Values use distinct four-state features. Bit positions, widths and slots use exact binary feature encodings, avoiding float rounding of large integer values. Cell type IDs use a fixed, published operator vocabulary. Unknown operators and unsupported parameter forms raise errors.

Connections preserve their pin direction, slot and bit position. Memory operations connect to a shared state node through MEMID equality. The identifier text is excluded from model features. Memory geometry, initialization addresses, word counts, priority and payload bits remain explicit in graph inputs. Cell and net initialization attributes are retained.

Parameter strings follow Yosys's MSB-first convention, while connection arrays remain LSB-first. Signed integer fields, empty vectors and unknown/high-impedance bits are supported. Node names, graph IDs, class labels and source paths remain metadata. Original cell-to-cell edges are also retained.

This is a new 127-feature schema. It needs newly initialized model input layers. Historical 20-feature graphs and their checkpoints use their original representation.

## Verification

The repaired benign and fault graphs each have 10,345 nodes and 38,555 directed edges. Both reconstruct 10,027 connection/parameter bits. Six memory operations connect to three memory states. Their model-feature multisets differ, and the distinction survives node reordering without reading labels, IDs or filenames.

Both actual GNNOnly and CrossAttentionFusion models accept the schema, produce finite outputs and backpropagate finite gradients. At a fixed random initialization, their logit differences on the pair are approximately 1.29e-5 and 5.93e-6. These checks demonstrate input sensitivity, and are not detection-accuracy results.

Thirty pipeline tests pass. Regression cases include same-population bit swaps, four-state constants, parameter round trips, signed memory offsets, memory identity aliases, initialization attributes, name/label changes, constant-only circuits and deliberate loss of a constant value.

All 195 records are rebuilt from their hash-checked original Yosys JSON. The independent verifier reconstructs values from serialized model tensors, checks attachments and pin directions, and compares copied RTL tensors exactly against the sanitized source cohort. Corpus coverage and hashes are recorded in data/semantic_graph_v1/verification.json.

The standard provenance command-line builder and reconstruction verifier also pass on RS232-T2100 clean.

## How this can help accuracy

The repair removes an information-theoretic obstacle for the known pair and exposes local constant and memory context that the old GNN never received. Larger graphs alone do not establish better detection. Matched training must compare the legacy and semantic views using the corrected balanced-gradient recipe, identical host splits, seeds and training budget.

Attention or pooling should give appropriate weight to original cells and relevant memory context. The auxiliary bit nodes make the representation larger and can dilute global mean pooling. Validation-host calibration and an RTL-only reference on the same sanitized cohort are also needed when measuring accuracy. This change has not yet been evaluated by a new full training run.

## Reproduction and entry points

Rebuild the recorded cohort with the existing project Python environment.

    python experiments/semantic_graph_v1/prepare.py --all
    python experiments/semantic_graph_v1/verify_cohort.py

The default prepare command verifies just the known host's three arms. The provenance CLI also accepts --representation semantic_v1 and defaults to a separate runs/provenance_semantic_v1 destination. Verify such exports using pipeline/provenance/verify.py.

The corrected training runner now infers input dimensions from the graph manifest. A later matched experiment can use the following explicit destinations.

    python experiments/training_audit_v3/train.py --manifest data/semantic_graph_v1/manifest.json --run-dir runs/semantic_graph_v1/training --report-dir data/semantic_graph_v1/training

A custom manifest requires separate output directories, and cached training results must match its manifest hash. This command starts the longer model-training experiment. It is documented here for reproducibility.

The 127-column layout and schema hash are published in each graph's metadata. Changing the operator vocabulary or layout requires a new version and new model weights.
