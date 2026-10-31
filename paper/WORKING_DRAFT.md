# A Provenance-Audited Pilot of Hardware Trojan Detection Across Host Designs

**Working research draft — not submission ready.** This draft records the completed experiment and its negative result. It does not claim Trojan localization or validated natural-language explanation. All numbers refer to the source-traced `provenance_v1` graph and testbench-free `rtl_clean_v1`/`rtl_expansion_v1` embedding versions.

## Abstract

Hardware Trojan detection studies often report performance across many benchmark variants, even when those variants share a small number of host designs. We built a source-traced pipeline that regenerates Yosys gate graphs, preserves the ordered node-to-RTL source mapping, and creates testbench-free CodeBERT embeddings with source-line spans. We compared RTL-only, graph-only, and cross-attention fusion classifiers on 21 paired AES/RS232 variants, using folds grouped by identical clean RTL. The fusion classifier obtained 1.00 balanced accuracy across 42 out-of-fold samples, but a two-feature RTL-length control obtained 0.786, indicating a shortcut risk. In a small diagnostic specified before model evaluation, comprising five paired memory-controller/PIC16F84 variants from two new host designs, all four approaches obtained 0.50 balanced accuracy at a fixed threshold. This sharp transfer failure, together with only three clean-source groups in development, prevents a generalization claim. The pipeline verified tensor/metadata alignment and source spans, but no gate-level Trojan labels or explanations were independently reviewed. The study provides an auditable negative pilot and a protocol for a larger cross-host benchmark; it does not establish a new localization method.

## 1. Motivation and research question

Trojan detection must transfer beyond variants of the same host circuit to be useful in an unfamiliar design. Our question is whether a graph plus RTL model offers reliable classification on unseen host designs, and whether source-linked graph evidence could eventually support gate and RTL localization. Existing work already studies [RTL line localization](https://arxiv.org/abs/2512.00591) and [gate-level structural localization](https://arxiv.org/abs/2609.17922); a combination of a graph encoder and an RTL encoder alone is therefore not a sufficient novelty claim. We focus this pilot on provenance and cross-host evaluation.

## 2. Data and methods

### 2.1 Benchmark units and splits

The development set contains 17 AES and four RS232 paired clean/Trojan variants, giving 42 labeled samples. Identical clean RTL texts define three groups across two circuit families. We keep each pair together and assign each clean-source group to one held-out fold. The previously reserved diagnostic has memctrl-T100 and PIC16F84-T100/T200/T300/T400, ten samples across two new clean host designs. PIC16F84 variants reuse one clean source. The diagnostic protocol, including the 0.5 decision threshold and seed 42, was recorded before evaluating those families. It has now been inspected and must not be called an untouched final test again.

### 2.2 Graph and source provenance

We synthesize each clean and Trojan RTL source with YoWASP Yosys 0.69 using `read_verilog`, `hierarchy`, `proc`, `opt`, `flatten`, `techmap`, `opt`, and `write_json`. The flow omits ABC and produces a graph version distinct from previously packaged tensors. Each cell receives an ordered node row, a fixed gate-class encoding, degree and path-distance features, and the Yosys `src` source spans. We store the Yosys JSON, exact command, source hashes, graph tensor, and ordered node names together. A verifier reconstructs the graph and checks tensor equality, row order, edge count, source hashes, and source-line bounds. For the 42 development graphs, 538,969 of 540,288 nodes have an in-source span. This number measures metadata coverage only; a span can be broad or semantically irrelevant to a Trojan.

### 2.3 RTL representation

We encode synthesizable Verilog with [CodeBERT](https://arxiv.org/abs/2002.08155), using 512-token windows, 50-token overlap, and masked mean pooling of last-layer token embeddings. We store tokenizer offsets mapped to file and line ranges. We exclude testbenches because an audit showed that all 42 originally packaged embeddings included testbench text. The corrected development embeddings contain 1,078 chunks, and the diagnostic embeddings contain 826 chunks. The source text supplied to the encoder contains no benchmark identifier, file name, or label wrapper.

### 2.4 Models and controls

The RTL baseline pools chunk embeddings by mean and maximum and fits a train-standardized linear classifier. The graph baseline is a two-layer GCN with 64 hidden units. The fusion classifier uses graph node representations and RTL chunks with cross-attention. GNN and fusion training uses seed 42, AdamW, learning rate 3e-4, weight decay 1e-3, and 25 epochs. We also fit a control using only the log of RTL character and line counts, and a development-only control using graph node and edge counts. All reported diagnostic predictions use the frozen threshold 0.5. We report balanced accuracy, macro F1, AUROC, and confusion counts; we do not treat individual variants as independent host circuits.

## 3. Results

### 3.1 Grouped development folds

| Model | Balanced accuracy | Macro F1 |
|---|---:|---:|
| RTL-only | 0.857 | 0.857 |
| GCN-only | 0.690 | 0.682 |
| Fusion | 1.000 | 1.000 |
| RTL length only | 0.786 | 0.775 |
| Graph size only | 0.357 | 0.339 |

The perfect fusion result has only three clean-source groups behind it. The strong RTL-length result shows that nonsemantic source-size differences predict labels in this dataset. These folds are useful for debugging and model comparison but cannot support a claim of cross-host robustness.

### 3.2 Previously reserved host diagnostic

| Model | Balanced accuracy | Macro F1 | AUROC | TN / FP / FN / TP |
|---|---:|---:|---:|---|
| RTL-only | 0.500 | 0.451 | 0.84 | 4 / 1 / 4 / 1 |
| GCN-only | 0.500 | 0.333 | 0.28 | 0 / 5 / 0 / 5 |
| Fusion | 0.500 | 0.333 | 0.84 | 0 / 5 / 0 / 5 |
| RTL length only | 0.500 | 0.451 | 0.82 | 4 / 1 / 4 / 1 |

All models reach 0.50 balanced accuracy at the fixed threshold on the two new hosts. The GCN and fusion classifiers mark every diagnostic sample as Trojan. AUROC is reported for completeness but is unstable with ten samples representing just two hosts. No confidence interval across independent hosts is meaningful with this sample size.

## 4. Interpretation and threats to validity

The experiment demonstrates that excellent grouped development performance can coexist with poor transfer to new circuit families. The likely contributors include too few independent hosts, benchmark-specific edits, source-length differences, model calibration, and design-family distribution shift; these are hypotheses, not isolated causal explanations. The diagnostic is too small to attribute the failure to any one factor. Source span coverage verifies traceability of synthesis records but does not validate Trojan gate labels. Automatic clean/Trojan line differences generate candidates with unknown false-positive and false-negative rates. No hardware experts were available to review gate labels or assess explanation usefulness. Cross-attention scores are not causal evidence of Trojan location. The original ~240,000-node AES graph package lacks its matching ordered metadata and is outside this experiment.

## 5. Reproducibility and next experiment

The repository commits per-sample predictions, fold summaries, and hashes for the development and diagnostic inputs. `docs/CURRENT_RESULTS.md` gives verification commands. The next study needs a larger set of independently distinct host designs, a new test set untouched until models and thresholds are frozen, explicit source-length and rename controls, and independently validated gate or RTL labels. A localization paper would then compare against dedicated RTL localization, graph attribution, structural heuristics, and LLM-only explanations under matched budgets. Explanation usefulness needs blinded hardware-engineer review; without it, that claim should be omitted.

## 6. Conclusion

The current artifact makes graph-to-RTL provenance and a cross-host failure visible and reproducible. It is a foundation for a stronger benchmark and a useful portfolio project, but the evidence does not yet justify a hardware Trojan localization or explanation paper.

## References

1. Xiao et al., [TrojanLoC: LLM-based Framework for RTL Trojan Localization](https://arxiv.org/abs/2512.00591), 2025.
2. Tehrani et al., [Demystifying Gate-Level Localization of RTL Trojans](https://arxiv.org/abs/2609.17922), 2026.
3. Feng et al., [CodeBERT: A Pre-Trained Model for Programming and Natural Languages](https://arxiv.org/abs/2002.08155), 2020.
4. [ICCAD 2025 CAD Contest, Problem A: Hardware Trojan Detection on Gate Level Netlist](https://www.iccad-contest.org/2025/Problems.html).
