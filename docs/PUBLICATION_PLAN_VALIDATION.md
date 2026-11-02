# Validation of the proposed publication plan

The new paired graph data is integrated into a hash-pinned, graph-only leave-one-host-family-out cohort. The 80 records cover 40 clean/Trojan variants across seven host families. Training excludes the held-out family. B15 and s38584 contribute graph data but no original RTL embeddings; BasicRSA has only Trojan sources and is excluded; duplicate PIC16F84 archives add no samples.

## Step 1: evaluation

**Per-family AUROC/AP and pairwise ranking: done for the existing seed-42 result.** Threshold-free metrics confirm the 50% balanced-accuracy folds are not all a threshold problem:

| Family | GNN AUROC | GNN AP | Correct Trojan-over-clean pairs | Unique clean source bundles |
|---|---:|---:|---:|---:|
| AES | 0.882 | 0.940 | 15/17 | 2 |
| MC8051 | 0.143 | 0.466 | 1/7 | 1 |
| PIC16F84 | 0.250 | 0.565 | 1/4 | 1 |
| RS232 | 0.000 | 0.365 | 0/4 | 1 |
| b15 | 1.000 | 1.000 | 4/4 | 1 |
| memctrl | 1.000 | 1.000 | 1/1 | 1 |
| s38584 | 1.000 | 1.000 | 3/3 | 1 |

Pooled pairwise accuracy is 25/40 (0.625), while pooled AUROC is 0.566 and AP is 0.547. Pair counts are not independent host counts: the forty clean records come from eight exact clean source bundles. AES alone has two such bundles; each other family has one. The current results remain single-seed development evidence.

**Stronger baselines: one fixed-seed comparison completed.** The graph-statistics and two-round directed Weisfeiler–Lehman histogram baselines use the same seven held-out families and source-balanced training weights.

| Family | Graph statistics AUROC | WL AUROC |
|---|---:|---:|
| AES | 0.441 | 0.412 |
| MC8051 | 0.143 | 0.714 |
| PIC16F84 | 1.000 | 1.000 |
| RS232 | 1.000 | 1.000 |
| b15 | 1.000 | 0.000 |
| memctrl | 0.000 | 1.000 |
| s38584 | 0.667 | 0.500 |

These simple baselines match or beat the GNN on multiple families and fail on others. That instability makes them essential controls and suggests host-specific structure is a serious risk. These scores are also from one seed; they do not establish a winning method.

**Five-seed estimates: not completed.** A runner now supports five fixed seeds and records an independent output folder for each run. The earlier controlled study was interrupted with only partial folds saved. Do not quote its partial outputs as means or standard deviations. Run the five-seed protocol before choosing a model or threshold.

The hash-pinned loader passed a one-family AES smoke run. Attempts to run all seven folds over five seeds for both the full and common-Yosys cohorts were stopped because each fold requires repeated training passes over very large graphs. Their seed-42 partial prediction files have no `results.json`; the protocol files are marked `interrupted_partial_no_results`. They are not evaluation results. The runner now marks runs `running` and changes the status only after all requested folds finish. For a publication run, execute one cohort/configuration at a time on a machine with adequate compute and retain the complete per-seed outputs.

## Step 2: shortcuts and synthesis

The existing audit exposes a major input-representation confound. About 25–30% of B15 mapped cells and 24–26% of s38584 mapped cells collapse to `OTHER`, including compound and arithmetic cells. AES includes memory cells. The new mapped netlists provide port connectivity but no library truth tables. These graphs are not yet a common gate vocabulary or a functionally harmonized dataset.

A common Verilog/Yosys cohort can be selected with `--cohort yosys_verilog`; it contains AES, RS232, PIC16F84, and memctrl. The earlier scaling/source-duplication experiment used this cohort but did not finish all folds. The new runner makes the matched cohort explicit.

Feature controls are available in `pipeline/train_lofo.py`: `raw`, `scaled` (training-only log/standardization of four numeric features), `no_proxies` (drop controllability/observability distance proxies), and `topology_only` (drop gate-class indicators). Compare all against the same folds, source-balanced weights and seeds. The feature controls have not yet been run across all folds/seeds. `topology_only` alone does not remove every flow shortcut because degree and graph size can also depend on synthesis.

The current README’s “size baseline” is a useful first control, but its 50% performance does not rule out stronger structural shortcuts: graph-statistics/WL results vary sharply by family. Keep per-family results visible and check node-feature distributions, unknown-cell rates, graph size and synthesis recipe alongside scores.

## Step 3: localization

The proposed localization headline is **not supported yet**. TrustHub’s written descriptions provide attack behavior such as trigger and payload, but not an ordered set of Trojan gate IDs for these graphs. RTL diffs and automatic Yosys source spans are candidate labels, not ground truth. New B15/s38584 spans point to mapped-netlist lines; MC8051 spans point to generated Verilog; none identifies the changed original RTL gates. Independent hardware reviewers are currently unavailable.

Do not report top-k hit rate, node rank or localization accuracy until labels map unambiguously to graph nodes and an independent reviewer checks them. Do not describe attention as a localization baseline: `GNNOnly` has no attention mechanism, and the cross-attention fusion model has not been trained/evaluated under this seven-family protocol. A clean/Trojan structural diff can be a candidate-generation baseline only where node correspondence is reliable, and must be reviewed before scoring.

## Reproduction commands

```powershell
trusthub/venv/Scripts/python.exe pipeline/extended_lofo.py
trusthub/venv/Scripts/python.exe pipeline/lofo_graph_baselines.py
trusthub/venv/Scripts/python.exe pipeline/train_lofo.py --cohort yosys_verilog --seed 42 --features raw --weighting source_balanced
trusthub/venv/Scripts/python.exe pipeline/run_lofo_seeds.py --cohort yosys_verilog --features raw --weighting source_balanced
```

The first two commands regenerate the derived threshold-free metrics and one-seed baseline. The last command runs five seeds on the common Yosys cohort; use `--cohort all` for the mixed-format cohort. Add `--features scaled` or `--features no_proxies` to execute those controlled ablations. Until all required runs complete and are source/hash verified, report the corresponding evidence as incomplete.

Artifacts: [`extended_metrics.json`](../data/lofo_detection/extended_metrics.json), [`graph_baselines.json`](../data/lofo_detection/graph_baselines.json), and each [`LOFO run folder`](../runs/lofo_integrated/).
