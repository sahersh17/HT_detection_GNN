# Dataset v2: balanced Trust-Hub development panel

This stage changes the dataset only. It does not train or evaluate a detector.
All model inputs in the Trust-Hub panel are single 20-feature gate graphs; a
clean reference is not supplied to the model at inference. The clean/Trojan
pairs are used to curate and audit the benchmark.

## Frozen views

| View | Clean | Positive | Purpose |
| --- | ---: | ---: | --- |
| `trusthub_primary.json` | 49 | 49 | Primary real-benchmark development panel |
| `balanced_mixed_keys.json` | 112 | 112 | Optional balanced development view, including 63 constructed positives |
| `registry.json` | 167 | 112 | Complete eligible graph registry |
| `hard_negative_keys.json` | 55 | 0 | Benign records omitted only from the balanced training view |

The 49 Trust-Hub pairs come from AES (17), MC8051 (7), PIC16F84 (4), RS232
(4), b15 (4), b19 (3), s35932 (3), s38417 (3), s38584 (2), memctrl (1), and
s15850 (1). The panel has 11 families but only 20 distinct clean source
bundles. Multiple variants of a family are dependent observations. The five
development folds in `trusthub_folds.json` keep every family entirely in
training or entirely in testing. They are **not** an untouched final test.

The old stage-1 set contained 185 records. This registry contains 279 unique
graph records: it replaces two duplicated RS232 pairs from stage 1 with their
Trust-Hub pool records and adds 94 previously absent Trust-Hub records. The
quarantined `s38584-T300` pair is excluded. The constructed native-edit cohort remains in the registry
and optional mixed view but is absent from the primary Trust-Hub panel. Its
literal and pin edits must not be reported as hardware Trojan attacks.

## What passed and what remains

The builder checks every graph and source hash, graph labels, feature schema,
node count, and edge bounds. The auditor checks unique keys and graph hashes,
the 50/50 views, complete pairs, and family-disjoint folds. These are data
integrity checks. They do not establish attack activation, payload effect, or
reviewed Trojan gate labels. Mechanism categories remain unclassified rather
than inferred from filenames. The different synthesis flows must be controlled
when models are compared.

Graph size is still a shortcut: the Trojan graph is larger in 43 of 49 pairs,
smaller in six. On the pooled 98 circuits, raw node count gives untrained
AUROC 0.584. The paired size sign is especially strong but requires a paired
comparison; it is an audit, not a golden-free deployment model. A future model
must beat graph-size and synthesis-domain controls on family-held-out data.
The 55 omitted benign examples remain available for a hard-negative check.

This work does **not** create independent new hosts, an independent Trojan
generator, simulation-verified attacks for every pair, matched benign decoys
for each Trust-Hub host, or a final held-out test. These are separate dataset
gaps. The DATE insertion intake is not merged because its own documented
benchmark gates failed (`docs/INDEPENDENT_BENCHMARK_V2.md`).

## Reproduce

From the repository root:

```powershell
.\trusthub\venv\Scripts\python.exe experiments\dataset_v2\build.py
.\trusthub\venv\Scripts\python.exe experiments\dataset_v2\audit.py
```

The build refuses to overwrite changed lock files. The manifest records exact
source and tensor hashes. The audit summary is in `data/dataset_v2/audit.json`.
