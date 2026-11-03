# Synthesis-surviving benign edits and external attacks

This experiment augments the six-project training panel with 49 usable native-edit triplets, four development blocks, and two original Trust-Hub RS232 attack variants. The held-out set is the same ten circuits from PIC16F84 and memctrl. Both test hosts were inspected in earlier experiments. SERV and wb2axip remain reserved.

## Verified construction

The four new benign edits implement modular addition followed by subtraction of one at the original output width. SAT proves the expression is the identity for all inputs. The no-ABC synthesis flow retains more cells for each edit. This retained arithmetic depends on that flow. A different optimizer can remove it.

| Development block | Original cells | Benign cells |
| --- | ---: | ---: |
| Four-port arbiter | 18 | 34 |
| SHA-1 schedule memory | 2800 | 3072 |
| UART debug readout | 124 | 396 |
| USB CRC-16 | 54 | 174 |

The bounded workloads agree with explicit expected outputs in original and mapped Verilog. The CRC bench observes bit four. The SHA-1 bench covers the initialized schedule word. SAT proves the inserted identity expression, and these workloads validate integration on a bounded domain. They do not establish full component correctness or synthesis equivalence across every circuit state.

RS232-T2100 and RS232-T2200 are original benchmark attacks from the existing Trust-Hub sources. Their RTL is unchanged. They are externally authored relative to this project's mutation adapters. They share one host and benchmark collection. Independence between their individual authors is unknown.

T2100 accepts normal bytes 00 and 01, then suppresses receive readiness after a false-start pulse. On the final A5 frame, clean outputs A5 with ready asserted and Trojan outputs the previous byte with ready deasserted. T2200 suppresses readiness during ordinary serial reception. Both source and synthesized outputs reproduce these effects. The build retains exact source and mapped hashes. Source inputs to CodeBERT exclude testbenches and filenames.

## Shortcut interpretation

The new benign arms remove the pooled perfect gate-count ordering. Faults exceed the untouched originals and are smaller than the benign arithmetic rewrites. Their pooled ranking of 0.50 hides these opposite signatures. The shortcut report therefore includes separate original-versus-fault and benign-versus-fault controls. Family-held-out graph statistics, gate histograms and WL histograms also run on the four-project cohort. One RS232 host is insufficient for a fitted host-held-out external-authorship probe. Scalar size and source length remain perfect on its two original benchmark pairs. The explicit word Trojan also perfectly ranks these two attack sources over their clean siblings, supplying a direct lexical clue to raw-RTL fusion.

The native-panel audit from transfer_v1 is linked in the shortcut report. This panel still carries source-origin and representation limitations. These admission failures qualify the trained comparisons as diagnostic augmentation tests.

## Neural comparison

The actual GNNOnly and CrossAttentionFusion implementations from pipeline/models.py use their default architecture. Frozen CodeBERT embeddings use revision 3b0952feddeffad0063f274080e3c23d75e7eb39 and masked mean pooling. The four numeric graph channels receive the same fixed log1p transformation in every cohort. Gate types and graph connections are preserved.

Both training conditions use five epochs, seeds 42, 43 and 44, AdamW at 0.0003, weight decay 0.001, gradient clipping at one, and equal total weight per host and class. The baseline has 18 circuits across six hosts. The augmented condition has 185 circuits across 60 hosts. Equal epochs give augmented training more optimizer updates. An additional baseline control repeats only the six-project data for exactly 925 updates, matching the augmented run. This control was added before neural model scoring. Both fixed-epoch and equal-update comparisons are reported.

All ten diagnostic samples are identical between conditions. Entire hosts are excluded from training, including all variants of each test host. Predictions use threshold 0.5. The report includes pooled and equal-host AUROC, per-host results, balanced accuracy, per-seed differences, and host-bootstrap intervals conditional on the trained predictions. With only two test hosts, uncertainty about future host populations remains substantial.

## Reproduction

Run the following from the repository root with the existing project environment and artifacts available.

1. Run `trusthub/venv/Scripts/python experiments/augmentation_v2/build.py` with Icarus Verilog available.
2. Run `trusthub/venv/Scripts/python experiments/augmentation_v2/shortcuts.py`.
3. Run `trusthub/venv/Scripts/python experiments/augmentation_v2/prepare.py`.
4. Run `trusthub/venv/Scripts/python experiments/augmentation_v2/train.py`.

The builder uses the pinned upstream originals from transfer_v1. Source and graph artifacts remain under runs/augmentation_v2. Data manifests and numeric reports are under data/augmentation_v2. Existing GNN and fusion checkpoints are retained separately.
