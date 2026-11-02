# When Source Metadata Predicts Paired Hardware-Trojan RTL: A Cross-Modal Benchmark Audit

**Working manuscript, 2026-11-02.** Target: workshop or benchmark/audit track.
This draft states only measured development results. It is not yet a
submission-ready manuscript; the independent generator intake failed its
benchmark gates, and clean-clone reproduction remains open.

## Abstract

Hardware-Trojan detection papers often use paired clean and infected circuits
to evaluate RTL embeddings, gate graphs, and their fusion. Repeated clean
designs, source length, synthesis conventions, and insertion templates can
make high scores difficult to interpret. We audit a provenance-checked
Trust-Hub cohort using host-grouped comparisons and transparent controls.
In the original 21-pair RTL cohort, a classifier using only character count,
line count, and CodeBERT window count matches the RTL embedding classifier's
balanced accuracy of 0.857; each makes six errors among 42 design sides,
though only two errors overlap. The cohort has just three independent clean
source texts. In a larger, inspected six-host development cohort with 36
pairs, a count-and-window control attains 0.935 equal-host AUROC over five
initializations, compared with 0.706 for a CodeBERT mean/max classifier.
Its fixed-threshold balanced accuracy is 0.500, revealing a ranking versus
calibration split. A four-host synthetic insertion pilot fails a transparent
output-cone control, and its gate-only graphs omit distinctions needed to
represent the functional difference. These findings motivate a benchmark
protocol that checks source and graph shortcuts before learned-model claims.
An intake of a pinned independent insertion framework also fails: two of six
combinational-host variants have no top-output SAT difference under defined
inputs, while source gate count and mapped graph size rank all 16 Trojan
variants above their clean counterparts.
We provide prediction hashes, exact metric recalculation, gate/source
provenance checks, and explicit claim boundaries. The present results support
a benchmark audit, not a new detector or validated real-gate localization.

## 1. Introduction

Detecting a Trojan in a familiar design variant is easier than recognizing
one on an independent host. A model can exploit how benchmark pairs were
packaged, named, embedded, or synthesized. This matters especially for
cross-modal methods: a strong RTL result may come from source metadata, while
a graph result may reflect flow or size. An apparent fusion gain is therefore
meaningful only after transparent controls fail to explain it.

Our project began with a graph/RTL fusion detector and a gate-localization
goal. Rebuilding the data exposed testbench-inclusive legacy embeddings,
repeated clean source texts, mixed gate representations, and unreviewed
localization labels. We turned these observations into a reproducible audit.
The contribution of this paper is the **evaluation and failure analysis**:
pair and host accounting, exact source provenance, comparable metadata and
embedding controls, and a synthetic insertion gate that rejects templates
solved by simple structural rules. We do not introduce a new detector here.

## 2. Related work

[Krieg (2023)](https://repositum.tuwien.at/bitstream/20.500.12708/191214/1/Krieg-2023-Reflections%20on%20Trusting%20TrustHUB-am.pdf)
audits Trust-Hub benchmark validity.
[Xiao et al. (2026)](https://arxiv.org/abs/2609.07199) study degradation under
held-out host families for node-level features. Our scope differs in paired
RTL/graph provenance, cross-modal metadata controls, and an explicit
synthetic-generator rejection ladder. Independent insertion methods such as
[TrojanForge](https://arxiv.org/html/2405.15184) and the
[DATE 2025 compatibility-graph framework](https://github.com/gkaggarwal/HT_Benchmark_HT_Insertion_Framework_DATE_2025)
offer routes to a future benchmark; their existence does not by itself make
our current generator or labels independent. A complete related-work review
must align tasks, splits, positive prevalence, and inference-time access to
clean twins before comparing scores.

## 3. Data and methods

**Original paired cohort.** The corrected AES/RS232 data contain 21
clean/Trojan pairs, 42 design sides, two host families, and three independent
clean source texts. Source identity groups repeated variants in the same
fold. The RTL encoder is pinned to a CodeBERT revision, and graph cells carry
ordered source spans checked against synthesis output. Source spans establish
traceability, not Trojan-label truth.

**Expanded development cohort.** Six families (AES, MC8051, PIC16F84,
RS232, b19, memctrl) supply 36 pairs and seven independent clean source
texts. Each leave-one-family-out fit weights hosts equally, then clean-source
groups equally within host. Feature scaling uses training data only. We
compare character/line count, tokenizer-window count, their combination,
and mean/max CodeBERT embeddings with the same linear head over five seeds.
The 0.5 threshold is fixed. We report per-host and equal-host AUROC,
within-pair rank, and thresholded balanced accuracy. These hosts and their
flows were already inspected, so the comparison is retrospective.

**Error and permutation analysis.** We compare the original RTL and metadata
models on identical folds. An exact sign-flip calculation uses the three
clean-source-group metric differences. With only three groups, attainable
p-values are coarse; a null result cannot establish equivalence.

**Synthetic control gate.** Four host circuits each have constructed clean,
benign decoy, and Trojan variants. We check local trigger/payload behavior,
graph/label row order, and transparent size, WL, motif, and output-cone
controls before learned training. For G1c, the output-cone rule ranks every
Trojan above both benign variants; the gate-only graph also admits
feature-preserving isomorphisms across classes. This pilot is rejected as a
method-evaluation benchmark.

**Independent insertion intake.** We pinned the public DATE 2025 gate-level
framework to commit `c7a1269c2c6fd4ebfaec2245c7613dba84fd0228` and
reserved two candidate hosts before generation. Four development hosts yielded
16 variants. A separate adapter pinned the process hash seed and verified
byte-identical reruns. We applied an independent combinational SAT miter or a
simplified sequential trace, rebuilt synthesized graphs and candidate labels
from source, and ran transparent source and graph-count controls. This intake
has no benign decoys, original RTL modality, or second generator.

## 4. Results

On the original cohort, the RTL and metadata models each make six errors;
only two are shared. Per-group balanced accuracy is 1.000, 0.833, and 0.500
for both arms, while AUROC is 1.000, 1.000, and 0.500. The exact paired
sign-flip p-value is 1.0 for both differences. The smallest possible
one-sided p-value with three groups is 0.125. The models' aggregate equality
does not mean they learn the same rule: on four RS232 pairs they fail on
opposite class sides.

In the six-host extension, the count-plus-window model yields 0.935
equal-host AUROC and paired win rate, compared with 0.706 for the RTL
embedding model, averaged over five seeds. The former has 0.500 pooled
balanced accuracy at the fixed threshold; the latter has 0.614. The metadata
control's ranking is strong while its threshold calibration fails on several
hosts. Host-level details and full seed values are in the companion
[shortcut audit](../docs/SHORTCUT_AUDIT_2026-11-02.md). The mixed languages,
windowing conventions, and flows preclude attributing this gap to one cause.

The first length-decoupling construction fails before model training. Both
classes receive unused-module padding, but the clean side has more padding
assignment lines in both pilot pairs. One pair remains one CodeBERT window
apart, and a synthesized top cell inventory changes on one side of the
other pair. We therefore report no RTL-after-padding score and no semantic
signal conclusion. The full failed preflight is preserved.

The synthetic G1c task also fails its benchmark gate: a simple output-cone
equivalence rule achieves perfect pair ranking on the four inspected hosts.
This is a valid baseline for this template and a reason to withhold a new
fusion result on that pilot.

The independent framework intake also fails. Four of six combinational-host
variants have an independent top-level output-difference SAT witness; two
c5315 variants have no difference under the defined-input two-state miter.
Six of eight sequential variants have an output witness under the simplified
scan-FF trace; both s1423 variants fail from the tested zero state and held
input. Two s1423 combinational-insertion variants remain upstream-only.
Across all 16 variants, source gate count and synthesized graph node count
each rank the Trojan above its clean counterpart in every pair. The 16 graph
and candidate-label rows pass hash and reconstruction checks, but their 236
positive candidates are unreviewed. We did not train a detector or inspect the
two reserved final-candidate hosts. See the
[full intake record](../docs/INDEPENDENT_BENCHMARK_V2.md).

## 5. Discussion and limitations

The empirical finding is that source metadata is a strong competitor on the
available inspected pairs. It is not proof that every RTL detector relies on
length, nor a causal estimate of any single confounder. Five optimization
seeds do not create five independent hosts. The six-host cohort contains
only seven clean source texts, and the original test has three. No untouched
final host exists for those detection results; the two new gate-level candidate
hosts remain sealed pending a valid benchmark. The failed length intervention cannot rule out semantic
RTL signal; it only demonstrates how easily a purported control can create
a new shortcut.

Gate-localization files are benchmark-derived **candidates**. A 162-row
masked packet and agreement scorer are ready, but no independent human labels
are available. Accordingly we report no real-node precision, recall, AP,
trigger/payload explanation accuracy, or engineer usefulness. Constructed
synthetic labels are exact only for their generator and graph order.

The pinned independent insertion framework supplied new candidate hosts and
reproducible netlists, but failed behavior and shortcut checks. The next gate
is matched benign decoys, top-level witnesses for every admitted variant, an
independent second generator, and a cohort where transparent controls cannot
solve the classes. Until such a cohort passes, the paper remains an audit and
negative-results contribution.

## Reproducibility and release

The [execution record](../docs/AUDIT_EXECUTION.md) names the scripts and
input versions. `experiments/audit_v1/reproduce_tables.py` recalculates the
six-host metrics and exact group tests from compact saved predictions.
`data/audit_v1/` contains hashes and summaries. Full raw reproduction also
requires separately obtained Trust-Hub archives, pinned model weights, the
recorded synthesis tools, and generated graph/embedding artifacts. A clean
clone and independent rerun have not yet been completed. Trust-Hub
redistribution terms must be checked before releasing raw netlists.
