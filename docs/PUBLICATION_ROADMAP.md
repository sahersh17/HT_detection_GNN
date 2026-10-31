# Research direction and completion gates

## Validated position as of 2026-10-31

The strongest defensible research question is whether **gate evidence linked back to RTL makes Trojan localization and engineering explanations more accurate and useful** across unseen circuit designs. Detection is a prerequisite. A future paper must establish the benefit of graph evidence over strong RTL-only and graph-only methods. The current pilot does not establish that benefit: on 42 samples from three independent clean-source groups, fusion balanced accuracy is 0.50 and RTL-only is 0.619. No reviewed gate labels or explanation ratings exist. See [BASELINE_RESULTS.md](BASELINE_RESULTS.md) and [LOCALIZATION_STATUS.md](LOCALIZATION_STATUS.md).

This direction needs a sharper contribution than combining a GNN and an LLM. [TrojanLoC](https://arxiv.org/abs/2512.00591) already studies RTL line localization, and [LoRD](https://arxiv.org/abs/2609.17922) reports strong gate localization with structural heuristics. The [ICCAD 2025 gate-level Trojan task](https://www.iccad-contest.org/2025/Problems.html) provides a relevant external comparison. The potential new contribution here is **verified gate-to-RTL provenance plus evidence-constrained trigger, payload, and fix explanations**, evaluated for localization and usefulness. This is a hypothesis, not a demonstrated result.

## Ordered work and acceptance criteria

| Stage | Work | Evidence required before the next claim | Current state |
|---|---|---|---|
| 1. Reproducible data | Regenerate graphs and an ordered gate-to-RTL mapping in the same Yosys run; record tool version, command, source hash, graph hash, and row-order checksum. Recompute RTL chunks with source-line offsets. | Every evaluated node score is joinable to the exact graph row and source range; reject mismatches automatically. | New ZIP lacks the mapping and chunk offsets. Earlier graph provenance covers only 44.2% of Trojan-side nodes. |
| 2. More independent designs | Add additional host families and source groups; decide development and external-test sets before modeling. Audit duplicate RTL, netlists, embeddings, and benchmark derivatives. | Report source groups, families, trigger/payload categories, and independent held-out hosts, not only variant or sample counts. Do not reuse the current three inspected folds as a final test. | 21 paired variants, but only three unique clean-source groups. |
| 3. Reviewed labels | Annotate changed RTL, Trojan gate region, trigger and payload, and ambiguous nodes. Two reviewers independently inspect a stratified subset, resolve disagreements, and keep `-1` for unknown gates. | Publish annotation guide, reviewer agreement, label coverage, graph alignment checks, and a locked reviewed-label version. Diff candidates are never treated as ground truth automatically. | Diff candidates exist; zero reviewed gate-label sets. |
| 4. Strong baselines | Compare RTL-only line localizer, GNN attribution or GNNExplainer, structural heuristic such as LoRD where runnable, and LLM-only RTL explanation with equal input budget. Train direct node localization and a fusion model with the same splits and computational budget. | Report detection and localization per design and family with uncertainty across independent hosts. Include simple structural and random rankings. A negative fusion result must be reported as such. | Detection pilot only; fusion underperforms RTL-only. |
| 5. Grounded explanation | Supply only localized evidence and cited RTL spans to the explanation stage. Require structured `where`, `trigger`, `payload`, and `fix` claims; permit `unknown` when evidence is insufficient. Hide Trust-Hub descriptions from generation. | Citation validity, expert factual judgments, unsupported-claim rate, trigger/payload accuracy, fix usefulness, and counterfactual faithfulness against LLM-only. | Citation validator and draft taxonomy exist; no evaluated generated explanations. |
| 6. Robustness and external test | Freeze models, prompts, thresholds, and exclusion rules; evaluate renamed/obfuscated graphs and unseen hosts once. Measure runtime and memory. | Both detection and gate/RTL localization robustness, confidence intervals by host, and complete failure cases. | No held-out obfuscation set or untouched external host set. |
| 7. Engineer study and release | Blind at least two hardware engineers to method identity; score location, correctness, and fix utility. Release a reproducible artifact and a small traceable case study. | Ratings, disagreements, adjudication, permissions/licensing for data, exact commands, environment, hashes, and a limitations section. | Not started. |

## Claim rules

- **Now:** a reproducible exploratory comparison and a source-tracing audit. Do not claim proven localization, superior fusion, or correct explanations.
- **After stages 1–3:** a defensible labeled benchmark or annotation-method paper is possible, even if fusion remains weak, provided label coverage and reviewer agreement are credible.
- **After stages 4–6:** a method paper is plausible only if localization and explanation results improve on appropriate baselines on unseen hosts. If they do not, publish the negative finding or reposition around dataset/provenance engineering.
- **After stage 7:** claim engineer usefulness only with recorded blinded ratings. A polished demo can show traceability earlier, but must label unreviewed examples as candidates.

## Reproducible current artifact

Run `python pipeline/verify_artifact.py` to check the committed pilot predictions, scoring, fold membership, and input hashes. Run `python -m unittest discover -s pipeline/tests` for the lightweight utilities. The large 2026-10-31 ZIP and model checkpoints are excluded from Git. The verifier requires the ZIP locally at `data/HT_data_2026-10-31_b40cc08.zip` to validate its recorded hash.

## External inputs needed to finish the research claim

1. The exact new-graph generation output with ordered node names, gate-to-RTL source spans, and chunk offsets, or a working Yosys environment to regenerate all of them together.
2. Additional independent clean host designs with licensed clean/Trojan variants and a genuinely untouched test set. The repository already contains unprocessed Trust-Hub archives for other families, including `memctrl-T100.zip` and `b15` variants; they require suitability, licensing, and synthesis checks before inclusion.
3. Hardware engineers who can review candidate labels and blindly assess explanation quality.
4. Enough compute to train and compare models on the ~240,000-node AES graphs, plus time to rerun all baselines under the frozen protocol.

These are experimental dependencies. No code change can turn the current unreviewed source candidates into verified ground truth or create an untouched external test after the pilot has been inspected.
