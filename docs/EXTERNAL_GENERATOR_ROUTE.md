# Independent benchmark route and decision gate

Status: pinned framework run on four development hosts; **benchmark intake
failed**. See `docs/INDEPENDENT_BENCHMARK_V2.md` and
`data/independent_benchmark_v2/decision.json` for the versioned evidence.
Decision date: **2026-11-16**. If the intake below cannot produce at least six
new independent hosts passing semantic and shortcut gates by then, use the
audit-paper route and do not present a new detector as the main contribution.

## Route A: published framework

The public [Kumar et al. DATE 2025 insertion framework](https://github.com/gkaggarwal/HT_Benchmark_HT_Insertion_Framework_DATE_2025/blob/c7a1269c2c6fd4ebfaec2245c7613dba84fd0228/README.md)
offers combinational and sequential insertion, trigger activation checks, and
output-corruption checks. Its pinned commit is
`c7a1269c2c6fd4ebfaec2245c7613dba84fd0228`; its
[MIT license](https://github.com/gkaggarwal/HT_Benchmark_HT_Insertion_Framework_DATE_2025/blob/c7a1269c2c6fd4ebfaec2245c7613dba84fd0228/LICENSE)
permits integration with attribution and license retention.

Its supplied gate-level hosts include c2670, c3540, c5315, c6288, s13207,
s1423, s15850, and s35932. The last two overlap hosts already used here; the
first six are **candidates**, not six validated independent hosts. The
framework outputs infected gate netlists and summaries, but does not by
itself provide matched benign decoys, original paired RTL, or independently
validated node labels for our graph representation. Do not add its outputs to
the RTL/fusion comparison without a genuine paired RTL modality.

A local archive download stalled, but 21 individual text files from the pinned
commit were fetched into an ignored vendor directory and verified against their
upstream Git blob hashes. Six candidate hosts were file-deduplicated. The four
development hosts were generated; c6288 and s13207 remain ungenerated final
candidates. The v2 rerun is byte-reproducible, but two combinational variants
fail an independent top-level output-difference SAT check, two sequential
s1423 variants fail the independent tested trace, and source gate count and
graph node count rank all 16 Trojan variants above their clean counterparts.
No benign decoys or second generator were supplied. These failures keep the
model and final-host gates closed.

## Intake protocol

1. Obtain the pinned commit and retain the upstream MIT notice and DATE
   citation. Hash every input host and generated file. Deduplicate against
   the existing Trust-Hub hosts by source and structural fingerprints.
2. Select combinational and sequential mechanisms under fixed parameters.
   Keep generator outputs grouped by clean host and insertion seed. Generate
   matched benign decoys using an **independent** construction, then test
   decoy equivalence and Trojan-on divergence with explicit witnesses or
   bounded traces. Audit trigger reachability and output observability.
3. Keep both the original and mapped gate netlists. Rebuild graph rows with
   source-to-cell lineage. Map injected gates to the final graph; set merged,
   deleted, or ambiguous cells to `-1`. Test every graph/label order hash.
4. Run the complete transparent control ladder from
   `experiments/audit_v1/protocol.json`, including output-cone and generator-ID
   probes. Keep host, mechanism, and generator splits separate. Fix generator
   leakage using controls only, before opening the model comparison.
5. Reserve a genuinely new host set and an independent generator or mechanism
   family for final claims. The DATE framework is one generator, not a
   leave-one-generator-out evaluation by itself.

An additional [25-host gate-level corpus](https://data.mendeley.com/datasets/37fdy2k7cj/1)
was published on 2026-10-28 under CC BY 4.0. Its repository description
reports 283 circuits, four inserted Trojan families, and a second synthesis
library. It is a **candidate** independent data source, not yet a validated
second generator: the downloadable file contents, construction code, host
overlap, licenses of embedded netlists, and output witnesses have not been
inspected here. A [NETLAM repository](https://github.com/shubhishukla10/NETLAM)
also has insertion scripts but centers on AES/Trust-Hub hosts already in the
project, so it is a weaker choice for independent-host evaluation. A direct
request for the Mendeley file inventory returned HTTP 401 in this environment;
the public landing-page metadata alone cannot establish usable file contents.

## Supported paper route

If this intake fails the date or controls, lead with the observed cross-modal
shortcut and benchmark audit. If it succeeds, report a benchmark with
transparent baselines first. A learned-method superiority claim requires a
later locked comparison on untouched hosts and a held-out generator, with
host-level uncertainty and all failures visible.
