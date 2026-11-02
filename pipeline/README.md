# Integrated pipeline

Run the commands in the [repository README](../README.md) from the repository root. The default paths in `config.py` point to the packaged archive under `data/`; `HT_DATA_ROOT` and `HT_RUNS_ROOT` can override those locations.

`prepare_data.py` selects the 42 samples with clean/Trojan benchmark pairs, extracts their CodeBERT embeddings, and builds three evaluation folds grouped by identical clean RTL source text. `audit_data.py` validates the prepared data. `train_cv.py` trains RTL-only, GNN-only, or fusion models on identical folds, and `report.py` compares their predictions. Graphs stay compressed until loaded for a step.

The graph and fusion models are computationally demanding because the AES graphs have roughly 240,000 nodes. Run full training on a machine with enough memory and preferably a GPU. The RTL-only baseline and small-graph forward passes have been exercised locally; the full graph/fusion cross-validation is still unverified.

For an exploratory comparison on the earlier, smaller graphs with ordered node metadata, add `--dataset legacy` to each `train_cv.py` command. This writes separate `runs/legacy_*` outputs. The completed three-model comparison and its limitations are in `docs/BASELINE_RESULTS.md`.

The localization utilities require original RTL and source-attributed synthesis output. The supplied data archive does not provide verified node-level ground truth.

For graph-only leave-one-host-family-out evaluation across the existing and newly integrated Trust-Hub graph versions, run `python pipeline/train_lofo.py`. The frozen 80-graph input list and graph hashes are in `data/lofo_detection/protocol.json`. `python pipeline/extended_lofo.py` derives per-family AUROC, average precision and clean/Trojan pairwise ranking from the saved fixed-seed predictions. This graph-only cohort deliberately excludes the three unpaired BasicRSA variants and duplicate PIC16F84 downloads. The mixed-format cohort is not a substitute for a same-library synthesis dataset.

`python pipeline/run_lofo_seeds.py --cohort yosys_verilog --features raw --weighting source_balanced` runs seeds 42–46 in separate run folders. Use `--cohort all` for the mixed-flow cohort and `--features scaled`, `no_proxies`, or `topology_only` for feature controls. Each run writes a `running` protocol status first and records final metrics only after every requested family fold completes; an interrupted run has partial predictions but no `results.json`. The validation, seed-42 metrics, and limitations are summarized in [`docs/PUBLICATION_PLAN_VALIDATION.md`](../docs/PUBLICATION_PLAN_VALIDATION.md).

For the additional ISCAS mapped pairs, use `pipeline/provenance/run_expansion_pipeline.py` and the separate `data/lofo_expanded/protocol.json` (94 graphs, ten hosts). The complete b19 VHDL pairs are included only in `data/lofo_expanded_b19/protocol.json` (100 graphs, eleven hosts). Pass either file with `--manifest` to the LOFO and baseline scripts. `--cohort mapped` limits evaluation to the five mapped-netlist host families. Results and limitations are in [`docs/EXPANDED_HOST_STUDY.md`](../docs/EXPANDED_HOST_STUDY.md).
