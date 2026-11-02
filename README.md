# Hardware Trojan Detection and Source-Traced Graph Research

This research project combines gate graphs with RTL embeddings to classify hardware designs as clean or Trojan-inserted. It also rebuilds graphs with an ordered gate-to-RTL source map for future localization research. **The detection results are exploratory; gate localization and explanation accuracy have no reviewed ground truth.** The held-out-family diagnostic currently provides no evidence that the model generalizes to new host designs. See [current results](docs/CURRENT_RESULTS.md).

## Reproduce the 97.62% fusion baseline

The retained baseline achieved **97.62% accuracy and balanced accuracy (41/42 correct)** on the original AES/RS232 dataset using three-fold cross-validation. The separate ten-sample PIC/memctrl diagnostic remains at 50%; the development result is not an unseen-host accuracy claim. This baseline uses the original gate GCN and RTL cross-attention, without the later pin-role or internet-data experiments.

The exact environment, runner, and checked results are in [`experiments/stepwise_rebuild/`](experiments/stepwise_rebuild/), including [`RESULTS.txt`](experiments/stepwise_rebuild/RESULTS.txt) and [`requirements-lock.txt`](experiments/stepwise_rebuild/requirements-lock.txt). With the regenerated graphs and RTL embeddings available, run:

```sh
python experiments/stepwise_rebuild/run.py --stage compare
```

The runner also provides `download`, `build`, `audit`, `gnn`, `embed`, `hosts`, `external`, and `report` stages. The local generated data, model checkpoints, and archived follow-up experiments stay in gitignored `runs/`.

## Why combine the two views?

A graph neural network (GNN) sees gates and their signal connections. CodeBERT captures information from the original Verilog RTL. Cross-attention combines those representations before classification and produces node-level attention scores for later localization analysis.

```text
RTL (Verilog) -> CodeBERT chunks --------------------+
                                                    +-> cross-attention -> clean/Trojan prediction
Netlist (Yosys) -> gate graph -> GNN node features --+
```

The graph pipeline synthesizes Verilog with Yosys, parses each netlist, connects gates by their signals, and builds 20-dimensional node features: gate-class one-hot values plus in-degree, out-degree, controllability, and observability proxies. CodeBERT embeds sliding windows of RTL into variable-length tensors with 768 values per chunk.

## Repository layout and data versions

- `trusthub/` contains Trust-Hub sources, synthesis and feature extraction scripts, and the earlier 93-graph dataset (31 clean, 62 Trojan). Its features should not be mixed with the newer data.
- `research/capstone.ipynb` preserves an earlier Colab experiment. Its reported 52-sample fusion result is separate from the current integrated dataset.
- `pipeline/` contains the data adapter, audit, RTL-only/GNN-only/fusion comparison, metrics, reporting, and preliminary localization tools.
- `data/HT_data_2026-10-31_b40cc08.zip` is the newer package with 94 graph tensors and 94 CodeBERT embeddings. Keep this large archive locally at that path; it is excluded from Git. Its portable manifest marks 60 samples usable. The integrated comparison selects 42 samples from 21 benchmarks that have both clean and Trojan sides. It omits 18 usable but unpaired samples.

The new AES graphs are much larger than the earlier graphs, at roughly 240,000 nodes each. Full GNN and fusion training needs substantial memory and is best run with a GPU.

## Source-traced graph rebuild

The additional B15, s38584, MC8051, BasicRSA and duplicate PIC downloads have specialized processing paths. See [new Trust-Hub data engineering](docs/NEW_TRUSTHUB_DATA.md) for formats, commands, validation and exclusions.

The separate `provenance_v1` graph version can be rebuilt on Windows with the pinned YoWASP Yosys package:

```powershell
& .\trusthub\venv\Scripts\python.exe pipeline\provenance\build.py --all-paired
& .\trusthub\venv\Scripts\python.exe pipeline\provenance\verify.py runs\provenance_v1
& .\trusthub\venv\Scripts\python.exe pipeline\provenance\export_review.py runs\provenance_v1\AES-T100\trojan
```

The rebuilt graphs, Yosys JSON, and reviewer sheets are stored in gitignored `runs/provenance_v1/`. All 42 rebuilt graphs passed reconstruction and row-alignment checks. Their source spans are automatic and their Trojan candidates are unreviewed; see [`docs/ANNOTATION_GUIDE.md`](docs/ANNOTATION_GUIDE.md). This graph version uses a different synthesis flow from both earlier datasets, so its metadata cannot be transferred to either of them.

## Reproduce and check the research artifacts

The saved exploratory results can be checked without rerunning training:

```powershell
& .\trusthub\venv\Scripts\python.exe pipeline\verify_artifact.py
& .\trusthub\venv\Scripts\python.exe pipeline\verify_artifact.py --pilot provenance_clean_pilot
& .\trusthub\venv\Scripts\python.exe pipeline\provenance\publish_external.py --verify
& .\trusthub\venv\Scripts\python.exe -m unittest discover -s pipeline\tests
```

The verifiers check sample membership, saved metrics, and hashes of local inputs. They establish artifact integrity, not scientific validity. The source-traced pilot uses `--dataset provenance_clean` for each model. Its CodeBERT embeddings exclude testbenches and save chunk-to-line spans. To rebuild them, run `pipeline/provenance/embed_rtl.py` and `pipeline/provenance/verify_rtl.py` in the project Python environment.

Use the Python environment in `trusthub/venv` with PyTorch and PyTorch Geometric. From the repository root on Windows:

```powershell
& .\trusthub\venv\Scripts\python.exe pipeline\prepare_data.py
& .\trusthub\venv\Scripts\python.exe pipeline\audit_data.py
& .\trusthub\venv\Scripts\python.exe pipeline\train_cv.py --model rtl
& .\trusthub\venv\Scripts\python.exe pipeline\train_cv.py --model gnn --epochs 25
& .\trusthub\venv\Scripts\python.exe pipeline\train_cv.py --model fusion --epochs 25
& .\trusthub\venv\Scripts\python.exe pipeline\report.py rtl=runs\rtl\predictions.json gnn=runs\gnn\predictions.json fusion=runs\fusion\predictions.json
```

`prepare_data.py` extracts the small embedding files and leaves the graphs compressed. All three models use the same evaluation folds. Folds group benchmarks that share identical clean RTL text, preventing those repeated clean sources from appearing in both training and test sets. Full cross-validation on the supplied ~240,000-node graph tensors remains unverified. The new source-traced graphs are a separate version with different node order and topology.

## Robustness and localization

A seven-family leave-one-host-family-out GNN diagnostic on 80 graphs achieved 57.5% pooled accuracy and 61.9% mean family balanced accuracy, versus 50.0% for the size baseline. Five family holdouts remained at 50%; threshold-free AUROC/AP and clean/Trojan pair ranking are in [the extended metrics](data/lofo_detection/extended_metrics.json). The new B15, s38584 and MC8051 graphs are in the hash-pinned LOFO cohort; use [the pipeline guide](docs/NEW_TRUSTHUB_DATA.md) for dataset scope and [the publication assessment](docs/LOFO_RESULTS.md) for limitations.

`trusthub/scripts/check_leakage.py` checks for label clues in graph metadata. The integrated audit additionally checks graph/embedding shapes, labels, and fold overlap. The supplied newer archive does not include source-attributed node mappings needed to establish Trojan-gate ground truth. The `pipeline/localization/` utilities can compare original clean and Trojan RTL and evaluate node rankings once source-attributed synthesis and node alignment are available. Attention scores alone are candidate explanations, not verified Trojan locations.

The separate source-traced development comparison and a ten-sample diagnostic on memory-controller and PIC16F84 hosts have been run. The development set has only three clean-source groups; the diagnostic has only two new clean host designs. [Current results](docs/CURRENT_RESULTS.md) include an RTL-length control that scores strongly on development folds, so apparent detection accuracy can reflect dataset shortcuts. An obfuscated held-out evaluation set and full comparison on the supplied newer graphs remain research work.

The current localization evidence audit and exact missing inputs are documented in [`docs/LOCALIZATION_STATUS.md`](docs/LOCALIZATION_STATUS.md). The candidate RTL changes and source descriptions for all 21 paired benchmarks are in `data/localization_reference/`; they are not yet reviewed ground truth.

The mapped-netlist gate-label feasibility audit and first structural ranking controls are in [`docs/LOCALIZATION_LABEL_AUDIT.md`](docs/LOCALIZATION_LABEL_AUDIT.md). Its s38584 node labels are hash-aligned mechanical candidates; B15 has no automatic node labels because the netlist correspondence is unstable.

The expanded ten-host development cohort, five-seed mapped-netlist detection comparison, and additional archive inventory are documented in [`docs/EXPANDED_HOST_STUDY.md`](docs/EXPANDED_HOST_STUDY.md). The GNN's ranking gain over simple controls is uncertain and its fixed-threshold accuracy remains 50%.

The newly integrated TrustHub graphs are frozen in a hash-verified 80-record cohort. Per-family ranking metrics, graph-statistics/WL controls, and a publication-readiness assessment are in [`docs/PUBLICATION_PLAN_VALIDATION.md`](docs/PUBLICATION_PLAN_VALIDATION.md). The five-seed evaluator and flow-matched cohort are available, but the complete runs are compute-intensive and must finish before their results can be reported.

The versioned [matched-insertion pilot](docs/MATCHED_INSERTION_PILOT.md) checks four synthetic hosts with benign decoys and constructed gate labels. Its strongest simple baselines solve the current trigger template, so it is a no-go for a new model claim. A [port-aware graph diagnostic](docs/PORT_AWARE_DIAGNOSTIC.md) tests one missing representation capability without claiming a model gain. The separate [RTL lexical ablation](docs/RTL_LEXICAL_ABLATION.md) measures sensitivity to comments and identifier names on the earlier development folds.

The latest [shortcut audit](docs/SHORTCUT_AUDIT_2026-11-02.md) compares RTL embeddings with source-length and tokenizer-window controls across six inspected host families. A [length intervention preflight](docs/LENGTH_DECOUPLE_PREFLIGHT.md) failed its shortcut gate, so no semantic RTL gain is claimed from it. The [pinned external insertion intake](docs/INDEPENDENT_BENCHMARK_V2.md) reproduced 16 gate-level variants but failed behavior and simple-count gates; no model was trained on that cohort. The [execution record](docs/AUDIT_EXECUTION.md), [claim ledger](docs/CLAIM_AUDIT_2026-11-02.md), [external benchmark route](docs/EXTERNAL_GENERATOR_ROUTE.md), and [audit-paper draft](paper/SHORTCUT_AUDIT_DRAFT.md) separate reproduced results from the validation still required for submission.

An exploratory comparison on the earlier graphs is recorded in [`docs/BASELINE_RESULTS.md`](docs/BASELINE_RESULTS.md); keep its graph and embedding versions separate from the source-traced experiment.

For the publication strategy, explicit completion gates, and external inputs still needed, see [`docs/PUBLICATION_ROADMAP.md`](docs/PUBLICATION_ROADMAP.md). The protocol in [`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md) is prospective; the existing pilot folds and the two-host diagnostic have already been inspected. An evidence-bounded [working paper draft](paper/WORKING_DRAFT.md) records the negative transfer result and the missing validation needed before submission.

## Contributors

| Contributor | GitHub |
|---|---|
| Saher | [@sahersh17](https://github.com/sahersh17) |
| Shreya Save | [@shreyaasave](https://github.com/shreyaasave) |
| Rohit Patil | [@rohitpatil-27-08](https://github.com/rohitpatil-27-08) |

## Acknowledgements

Benchmarks are from [TrustHub](https://trust-hub.org). The RTL encoder is [CodeBERT](https://huggingface.co/microsoft/codebert-base).
