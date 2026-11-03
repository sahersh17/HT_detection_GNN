# Graded results presentation: evidence-led progress report

**Prepared for:** 4 November 2026 presentation  
**Project:** Hardware Trojan detection using gate graphs, RTL embeddings, and cross-attention  
**Evidence cut-off:** Repository results available on 3 November 2026

## 1. Executive summary

The project has delivered a working gate-graph and RTL fusion pipeline, reproduced its initial high development score, and then tested whether that score survives stronger evaluation. The reproduced fusion baseline classified **41 of 42 AES/RS232 development circuits correctly (97.62% balanced accuracy)**. That is a valid result on the original three folds, but those 42 circuits contain only a few independent clean-source groups. On a separate ten-circuit diagnostic from two different host designs, its fixed-threshold balanced accuracy was **50%**. A source-length-only control scored **78.57%** on the development folds. These checks show why the original score cannot be presented as unseen-design detection accuracy.

The team responded with concrete engineering and experimental deliverables. It verified the source-to-graph chain, built a typed graph/RTL fusion experiment, expanded and locked a 185-circuit development set with host/owner-separated folds, compared models against simple controls, repaired graph information loss in a new 127-feature representation, and assembled a separate balanced Trust-Hub development panel of 49 clean/Trojan pairs from 11 families. The newer evaluations do **not** establish a generalizing Trojan detector yet. Their value is that they reveal where performance breaks and provide a reproducible plan for a valid next result.

**Suggested opening statement:** “Our first milestone showed that combining RTL and gate structure works on the original development benchmark. This phase tests whether that success reflects the Trojan or properties of the benchmark. We have reproduced the result, identified a generalization gap, corrected a graph representation defect, and locked a broader evaluation protocol. That puts the project on a sounder path to a credible detection and localization claim.”

## 2. Continuity with the original deliverables

The exact earlier slide deck and rubric were not available in the repository or connected Drive. This mapping uses the objectives in the project README and research roadmap. Replace the labels with the earlier deck's exact terms if it becomes available.

| Original objective | Delivered evidence | Status to say aloud |
|---|---|---|
| Build a graph view of synthesized hardware | Yosys-to-graph pipeline, ordered node metadata, typed connectivity, and checked source mapping. The typed experiment verified 52 circuits, 576,936 cells, and 51,159,034 directed typed edges. | **Implemented and checked for data integrity.** |
| Represent RTL with a language model | Frozen CodeBERT chunk embeddings with source-line spans; corrected embeddings exclude testbench text in the source-traced pilot. | **Implemented and alignment-checked.** |
| Fuse RTL and graph information for circuit classification | Cross-attention fusion baseline reproduced at 41/42 correct on the original development folds; newer typed fusion runs and ablations executed. | **Working model and experiments; no proven gain on new hosts.** |
| Evaluate beyond the initial benchmark | Ten-circuit host-transfer diagnostic, source-length controls, host/owner-separated five-fold development study, training and representation audits. | **Completed diagnostics; generalization remains unresolved.** |
| Locate suspicious gates/RTL and explain them | Ordered gate-to-RTL links and candidate region scoring are available. No independently reviewed gate or line labels exist. | **Traceability foundation built; localization accuracy and explanation correctness unvalidated.** |

This wording gives credit for tangible work without implying that every research aim has already been met.

## 3. Results, in chronological order

### Milestone A — initial integrated baseline

On the original 42 AES/RS232 circuits, the retained reproduction reports fusion **97.62% balanced accuracy**, RTL-only **90.48%**, rebuilt GNN **69.05%**, and a source-length control **78.57%**. The result demonstrates that the pipeline can train and classify its development data. The comparison also shows that superficial properties of RTL carry substantial label information. The same trained approaches reached **50% balanced accuracy at a frozen 0.5 threshold** on ten memctrl/PIC diagnostic circuits from two new clean host designs. This diagnostic has been inspected and is too small to function as a final test.

**Presentation wording:** “We reproduced the original 97.62% development result, then found that the fixed-threshold decision did not transfer to two new host designs. We therefore treat the original figure as a development milestone and use the failure to guide our next data and model changes.”

### Milestone B — typed and source-aligned fusion

The typed fusion run adds pin-aware graph connectivity, structured RTL operators, sparse gate-to-RTL alignment, and a region-scoring head. Preparation verified all **52** records: 42 development circuits plus ten diagnostic circuits. It preserved original ordered cell classes and connections and recorded **944,812 gate-to-RTL links**. On the five external pairs, the matched three-epoch fusion model ranked the Trojan side above clean in **5/5 pairs** with **AUROC 0.84**, but **balanced accuracy remained 0.50** because it predicted every circuit as clean at the fixed threshold. The 25-epoch fusion model still had **0.50 balanced accuracy** and became overconfident, predicting every diagnostic circuit as Trojan. The trained mixture weight was overwhelmingly on RTL, so this experiment does not show that graph alignment added value. Region scores are candidates only because the head was trained with circuit labels, not reviewed location labels.

**Presentation wording:** “The architecture and alignment are operational. Pairwise ranking on the tiny diagnostic suggests a signal worth studying, but the circuit decision is not calibrated across hosts. Our next result must show a threshold that works on genuinely new designs.”

### Milestone C — stronger dataset and controls

The team locked **185 development circuits across 60 hosts**, with five folds that keep each host, source repository, and repository owner together. The set has 120 negative and 65 positive circuits. Most positives are constructed edits or faults; only two are original Trust-Hub RS232 attacks, so this experiment measures **development detection of edits and faults**, not broad hardware Trojan detection. The ten previously inspected diagnostic circuits were excluded from model selection. No untouched final-test records have been admitted.

On these locked folds, the combined graph-plus-CodeBERT logistic baseline reached **0.583 equal-host AUROC** and **0.511 balanced accuracy** using a cutoff selected on training data. The graph-aggregate baseline reached **0.571 equal-host AUROC**; size-only reached **0.479**. The combined-minus-size AUROC estimate is **+0.104**, with a host-bootstrap interval of **-0.042 to +0.246**, which includes zero. Pooled CodeBERT alone scored **0.467 equal-host AUROC**. These data provide a weak, unstable graph-statistic signal, not a robust improvement claim.

**Presentation wording:** “A more disciplined split makes the task harder. That is useful: it prevents variants of the same host from inflating our result and tells us that the current model needs better representation and stronger data.”

### Milestone D — graph repair and training diagnosis

The training audit found two actionable problems. The earlier optimization recipe produced a strong clean-class bias. Corrected balanced training improved average diagnostic ranking in some runs, but all six corrected GNN/fusion runs still had **50% fixed-threshold accuracy** on the two inspected hosts. Separately, the legacy graph tensors completely lost a memory-initialization bit that distinguishes a known benign/fault pair. For that pair, no model using the legacy graph tensors could separate the labels from graph input alone.

The new `semantic_v1` representation records constants, memory state, pin positions, bit values, and initialization data in **127 features**. An independent verifier checked **195 rebuilt graphs, 4,352,812 nodes, and 11,113,838 edges** against the original mapped netlists. The known indistinguishable pair is distinguishable in the repaired input. This is an information-preservation result, **not a measured detection-accuracy gain**. A one-fold GCN memorization test on this representation reached a best training pooled AUROC of **0.765** after normalization; it failed the preset 0.99 memorization gate. The team stopped before an expensive full-fold run because that diagnostic did not justify it.

**Presentation wording:** “We found and fixed a concrete information-loss bug. We also tested whether a simple GCN could use the repaired representation and found that this architecture still struggles to learn small local edits. That narrows the next modeling question.”

### Milestone E — a cleaner Trust-Hub development panel

A separate graph-only dataset version now contains **49 clean/Trojan pairs (98 circuits) across 11 Trust-Hub families**. It has balanced labels and family-disjoint development folds. The complete eligible registry contains 279 graphs; a separate optional mixed development view contains 224 circuits, including constructed positives that must remain labeled as such. All 98 primary graphs passed source/hash and graph-schema checks. **No detector has yet been trained or scored on this 49-pair panel.** There are only 20 distinct clean source bundles, all families have been inspected during development, and graph size is a shortcut: the Trojan side is larger in 43/49 pairs. This panel is a much better defined development resource, but it is not an untouched external test.

**Presentation wording:** “We have now frozen a balanced, family-aware real-benchmark panel. The next model comparison will run here with graph-size and synthesis-flow controls, rather than treating synthetic edits as real attacks.”

## 4. The main interpretation

The strongest defensible conclusion is **progress in reproducibility, data quality, and diagnosis**, alongside a clear performance gap. The original benchmark showed that the fusion system can fit its development distribution. The transfer and shortcut controls showed that the initial high score was not sufficient evidence for new-host detection. The expanded studies exposed a weak and variable signal, an optimization issue, and a specific loss of circuit information in graph construction. The repaired representation and locked Trust-Hub panel are concrete responses to those findings.

Avoid a single “accuracy improved from X to Y” chart. These runs use different data, graph schemas, training budgets, and evaluation units. A visual timeline of **question → test → finding → corrective action** is more accurate and more persuasive.

## 5. Recommended 8-slide story (about 8–10 minutes)

| Slide | Title and on-slide content | Speaker emphasis |
|---|---|---|
| 1 | **Hardware Trojan detection: from promising baseline to reliable evaluation**. One-sentence goal: connect RTL and gate evidence for detection and future localization. | State the original vision and that this update is about measured results. |
| 2 | **What we promised and delivered**. Four boxes: graph pipeline, RTL embeddings, fusion classifier, evaluation/traceability. Status labels: built, checked, tested, localization pending. | Show continuity with earlier deliverables before any metric. |
| 3 | **The starting result**. 41/42 correct; 97.62% development BA. Small subtitle: 42 AES/RS232 circuits, three folds, limited independent sources. | Present the high score accurately; immediately define its scope. |
| 4 | **Does it transfer?**. Two bars: 97.62% development BA versus 50% diagnostic BA on ten circuits from two new hosts. Add “RTL length alone: 78.57% development BA.” | This is the research turning point: a careful team investigates a surprising score. |
| 5 | **What we built in response**. Pipeline diagram: RTL + CodeBERT; Yosys + typed/semantic graph; alignment; fusion; candidate source spans. Callouts: 52 typed records verified; 195 semantic graphs rebuilt. | Separate engineering completion from accuracy. |
| 6 | **Controlled evaluation**. 185 circuits/60 hosts, owner-grouped folds. Small table: size 0.479, graph 0.571, combined 0.583 equal-host AUROC; note uncertainty includes no gain. | Explain host grouping and simple baselines in plain language. |
| 7 | **A concrete bug fixed, and a new benchmark frozen**. Legacy graph omitted a decisive memory bit; new 127-feature graph preserves it. Trust-Hub panel: 49 pairs/11 families, no model result yet. | This is the strongest forward-progress slide. |
| 8 | **Next milestone and success criteria**. Train graph/RTL baselines on fixed family splits; compare size/length controls; freeze independent new hosts and threshold; review localization labels. | Finish with measurable gates and explicit work already prepared. |

If time is short, combine slides 5 and 7. Keep a backup slide with the typed fusion AUROC/ranking and its threshold failure. Do not put the 0.84 AUROC on a headline slide without the 0.50 balanced accuracy beside it.

## 6. Suggested two-minute results script

“In our earlier work, we proposed combining a gate-level graph neural network with CodeBERT representations of RTL. We reproduced the original fusion result: 41 of 42 development circuits were classified correctly, giving 97.62% balanced accuracy. We then asked whether this would hold for designs outside the original AES and RS232 families. On a ten-circuit diagnostic from memctrl and PIC hosts, balanced accuracy at the fixed threshold was 50%. A simple RTL-length control was also strong on the development folds. So the high score is real for that benchmark, but it is not proof of general Trojan detection.

“We used that finding to improve the project. We built and verified typed source-aligned graph data, locked a 185-circuit host-separated development study, and compared our models with size and length controls. Those results show only weak, variable detection signal so far. The audit then found a specific graph representation fault: a memory bit that changes the circuit was absent from the old model input. We repaired that in a new 127-feature graph and verified 195 rebuilt circuits. We have also prepared a balanced 49-pair Trust-Hub development panel across 11 families. Our next evaluation will use that fixed panel and a genuinely independent final host set. The project has moved from a promising prototype to a controlled research pipeline, with clear criteria for claiming detection and localization.”

## 7. Likely questions and safe answers

**“Why did the accuracy fall from 97.62% to 50%?”**  
“Those numbers measure different distributions. The first is a small, source-dependent development set; the second uses two new host designs. The shift and the strong source-length control suggest the model learned some benchmark-specific patterns. We are testing that directly with host-separated folds and simple controls.”

**“Is 0.84 AUROC on the typed fusion external run good?”**  
“It indicates ranking on five related pairs, but at the fixed threshold every diagnostic sample received the same class, so balanced accuracy was 0.50. It is a useful diagnostic, not a deployable result.”

**“Did fusion beat RTL-only?”**  
“Not on the present new-host diagnostic. The RTL-only arm matched or exceeded fusion ranking in the small typed run, and the long fusion run relied almost entirely on RTL. We are keeping fusion as a hypothesis to test against matched baselines, not presenting superiority as established.”

**“Does the 49-pair Trust-Hub dataset prove generalization?”**  
“No. It is a frozen development panel with family-separated folds. It has not yet been used for a model result, and the families have been inspected. We still need a separately sourced untouched final set.”

**“Can you show the Trojan gates?”**  
“We can show source-linked candidate regions and verify graph-row/source alignment. We cannot give a gate-localization accuracy figure until the candidate labels are independently reviewed.”

**“What is the main contribution so far?”**  
“An end-to-end reproducible prototype plus a rigorous diagnosis of its limits: source traceability, controlled transfer tests, shortcut baselines, a documented graph-information repair, and a locked next benchmark. Those are necessary steps toward a credible detector.”

## 8. Before presenting

1. Put the dataset and unit beside every metric: **42 development circuits**, **ten diagnostic circuits/two hosts**, or **185 development circuits/60 hosts**. Never place metrics from these cohorts in one unlabeled ranking table.
2. Use **balanced accuracy** for circuit decisions and **AUROC** for ranking. Explain that a strong AUROC can coexist with 50% balanced accuracy when the threshold is wrong.
3. Label constructed edits/faults as such; reserve “Trust-Hub Trojan” for the original benchmark variants.
4. Mark candidate gate regions as **unreviewed**, and never say localization or explanation accuracy has been measured.
5. Rehearse the one-sentence conclusion: **“We reproduced the prototype, exposed its transfer limit, repaired a real input defect, and locked the next credible test.”**

## 9. Evidence index

- Initial reproducibility and transfer: [`experiments/stepwise_rebuild/RESULTS.txt`](../experiments/stepwise_rebuild/RESULTS.txt), [`README.md`](../README.md).
- Typed fusion methods, ablations, and checked counts: [`experiments/typed_fusion_v1/RESULTS.md`](../experiments/typed_fusion_v1/RESULTS.md), [`runs/typed_fusion_v1/verification.json`](../runs/typed_fusion_v1/verification.json).
- Locked 185-circuit panel and CPU baselines: [`experiments/dataset_stage1/README.md`](../experiments/dataset_stage1/README.md), [`experiments/dataset_stage2/RESULTS.md`](../experiments/dataset_stage2/RESULTS.md), [`data/dataset_stage2/audit.json`](../data/dataset_stage2/audit.json).
- Training diagnosis and semantic graph repair: [`experiments/training_audit_v3/RESULTS.md`](../experiments/training_audit_v3/RESULTS.md), [`experiments/semantic_graph_v1/README.md`](../experiments/semantic_graph_v1/README.md), [`data/semantic_graph_v1/verification.json`](../data/semantic_graph_v1/verification.json), [`experiments/dataset_stage3/RESULTS.md`](../experiments/dataset_stage3/RESULTS.md).
- Trust-Hub v2 panel: [`experiments/dataset_v2/README.md`](../experiments/dataset_v2/README.md), [`data/dataset_v2/audit.json`](../data/dataset_v2/audit.json).
- Localization boundary and research plan: [`docs/LOCALIZATION_STATUS.md`](LOCALIZATION_STATUS.md), [`docs/PUBLICATION_ROADMAP.md`](PUBLICATION_ROADMAP.md).

**Scope note:** This is a report based on the repository evidence, not an assertion about wording in an unavailable prior slide deck or grading rubric. All newer model and dataset results remain development or inspected diagnostics; none is an untouched final hardware-Trojan generalization test.
