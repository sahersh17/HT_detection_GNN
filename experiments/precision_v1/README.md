# Precision extension on ver2

The analysis starts from the frozen six-family scores and keeps the same admission thresholds, TrustHub reference panel, feature definitions and host-held-out probe training. The original 29 margin failures and their family-count projections are listed in the interval review. The primary panel is fixed at 63 new candidates; the separately screened 16-family supplementary panel addresses verification attrition. The original failures remain part of the admission decision.

## Original-only evidence

The source inventory reads public Tiny Tapeout submission manifests from the fixed SkyWater shuttle snapshots. Each top's original source files come from the author's pinned repository commit. Source hashes, source lists, declared authors and titles, reference netlist hashes, shuttle commits, and reference PDK revision are retained. Separate submissions must have different repository owners, declared authors, title, top name and source file hashes. Identical substantive modules or greater than 80% normalized 11-token-shingle containment exclude a candidate. These are implementation-lineage checks. The projects share a harness, technology and program of origin, and some perform related functions. The host bootstrap does not model higher-level clustering by ecosystem.

Only genuine originals in the clean TrustHub token range enter the source qualification. The published, independently built chip netlist supplies the test oracle via the SkyWater functional cell models. A deterministic sequence resets each top, drives 16 idle normal cycles, then varies its two input bytes. The oracle observes the output byte, bidirectional output-enable bits and actively driven data bits. Candidate originals must agree on at least 90% fully defined reference samples, including all normal cycles, with an observable change. A candidate with any source mismatch on the qualifying reference samples fails. The fixed sequence verifies a bounded interface contract. It does not validate every function of the design.

## Mutation procedure

Each matched triplet starts from the unchanged pinned design. Candidate expressions are selected before detector scoring. A native edit replaces an explicitly sized literal or primary-input bit index at one site. Its benign arm has an equivalent numeric representation; the fault changes the selected value. Candidates with no fully defined dormant-then-divergent witness within the fixed trace are skipped. For a design with no usable candidate in the first 28 proposals, a separately labeled interface wrapper applies an identity or one-bit transformation at a designated input. The wrapper is a fallback construction with a different source footprint. The admission report splits the controls by construction alongside the pooled frozen checks.

Each accepted triplet has a local SAT proof for its benign expression. On every comparison cycle the original and benign source/mapped outputs agree with the independent published reference. The fault has the same source and mapped output, a matching normal window, and a recorded first divergent transaction. Unknown reference cycles are outside the declared domain. Source and mapped outputs are not required to diverge on every transaction after activation. Synthetic labels describe these intentional witnessed faults, without a claim about attack prevalence.

The edge case involving a wildcard case literal was identified during verification. A partial token before a question mark is ineligible for the ordinary numeric-literal rule. The corrected candidate was regenerated before scoring. One scratch reference was restored and matched against its pre-edit hash. One replay was given a longer timeout; a continuing failure stays in the failure manifest. Frozen frontend or reset failures are not counted as verified.

## Scoring

Both comparisons remain mandatory. Fitted controls hold out an entire family. All available host-level scores are resampled with replacement using the **exact** percentile bootstrap. Rather than allocate an n-to-the-n array, the recurrence accumulates integer multiplicities on the rational score lattice and takes the same inverted-CDF percentiles. The runner reproduces every saved interval for the initial six before scoring. If a mapped arm has zero cells, node and edge counts are independently zero. Source, scalar and source-origin controls still cover that host. The gate-graph probes use complete families only, explicitly naming the missing top. No empty graph is manufactured for a learned probe.

The intervals are pointwise, conditional on the TrustHub reference panel, the selected families, and the fitted out-of-fold scores. A hold is returned for any verification failure, hard-stop crossing, margin failure, excessive gate-type difference or unresolved representation. The verified-only control decision is recorded separately. No detector is fitted.

## Materials

The versioned catalog links the new manifest to the previous six-family dataset. The ZIP contains byte-exact edit recipes, provenance and observations. Where a recognized upstream license is available it includes the original source and notice; otherwise the original is retrieved from its pinned URL. Run the following from the repository root to reconstruct all verified new source sets and verify their hashes:

```powershell
python experiments/precision_v1/bundle.py --fetch
```

The raw source, gate, and simulation artifacts use the paths in the intake and manifests. The inventory and acquisition tools are separate from the generator. To repeat scoring with those artifacts and the existing six-anchor run, use the existing project environment:

```powershell
.\trusthub\venv\Scripts\python.exe experiments/precision_v1/score.py
```

The six-family estimator called for 63 more families. Of 79 new attempts, 67 triplets verified. Eleven originals or arms failed synthesis and one mapped replay timed out after a retry. The combined scalar cohort has 73 families and 219 arms. The gate-graph cohort has 72 families because one verified fault maps to zero cells. The new bundle carries 201 verified source sets, including 50 native-mutation and 17 fallback families. Original bytes for 66 of the 67 families are included; one requires a pinned fetch on a fresh machine.

Nineteen of the original 29 marginal intervals now pass. Seven estimates remain in-band with intervals crossing a margin. Three source-line origin estimates lie outside the band. All ten remaining intervals exclude 0.5 pointwise. Three other origin intervals (cell count for each arm) newly fail the precision rule, for 13 current margin failures. No pooled score reaches 0.90 in either direction. The fallback subgroup alone gives a perfect cell-count ranking on all 17 hosts for both comparisons. Among the 50 new native edits the corresponding rankings are 0.51 and 0.52. Fifteen gate-type comparisons exceed 5%, eight typed comparisons remain inconclusive or unavailable, and the cone rule has nonzero features on only nine records. The eligible verified-only cohort also fails the gate. Training remains on hold.

The original panel, supplementary panel, failures, and final bundle should be kept together. Variants and submissions from the same family are never additional bootstrap units.
