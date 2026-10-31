# Localization and explanation evidence audit

Generated from the packaged 2026-10-31 data and the original Trust-Hub source folders. Run `python pipeline/localization/build_reference.py` and `python pipeline/localization/audit_reference.py` to refresh the machine-readable records in `data/localization_reference/`.

## What is available

| Evidence | Count | Status |
|---|---:|---|
| Paired clean/Trojan benchmarks | 21 (17 AES, 4 RS232) | Available |
| Original RTL on both sides | 21 | Available |
| Candidate changed RTL lines | 21 | Computed; needs review |
| Benchmark Trojan descriptions | 21 | Extracted as reference text; needs factual annotation |
| Ordered gate-to-source mappings for the supplied 2026-10-31 graph tensors | 0 | Missing |
| Newly regenerated paired graphs with aligned gate/source metadata | 42 | Built locally as separate `provenance_v1` version; unreviewed |
| Verified gate-level ground truth | 0 | Source mappings exist only for the rebuilt version; candidates are unreviewed |
| Corrected RTL embeddings with source-line chunk spans | 52 | Built and alignment-checked for development and diagnostic samples |

The 94-graph archive contains PyTorch Geometric objects with features, edges, a graph label, and a graph ID. It does not contain ordered gate names or source locations. Its `manifest.json` mentions metadata paths on another machine, but no metadata files are packaged. The older repo's graph node counts do not match any of the 42 paired samples in this archive, so assigning old metadata by node index would be invalid.

The linked `Hardware-Trojan-Detection/main/results/gnn/features/metadata` is also the older export: its `AES-T100/clean_netlist.json` has 7,903 nodes, compared with 240,258 in the supplied ZIP; its `RS232-T2100/tjin_netlist.json` has 78 nodes, compared with 121 in the ZIP. The linked `main/src/llm` generates RTL embeddings and does not establish node order or source locations for these newer graphs.

## Regenerated source-traced graph version

`pipeline/provenance/build.py` now invokes pinned YoWASP Yosys 0.69 and saves its JSON, graph tensor, ordered node metadata, source hashes, synthesis command, and unreviewed candidate labels together. `pipeline/provenance/verify.py` reconstructs every graph from saved Yosys JSON and checks tensors, row order, source hashes, and metadata. All 21 paired benchmarks (42 graphs) passed: **540,288 nodes**, of which **538,969** have a Yosys cell `src` span. The automatic RTL-diff intersection flagged **5,306 candidate nodes**, not confirmed Trojan gates. An annotation template can be exported with `pipeline/provenance/export_review.py`; see `docs/ANNOTATION_GUIDE.md`.

This is a new flow **without ABC**, because the Windows YoWASP build could not create ABC's temporary genlib file. Its graphs have different node counts and topology from both the supplied ZIP and the earlier `trusthub/features` graphs. The new metadata must never be attached to those other tensors. High source-span coverage does not establish label correctness: some Yosys spans cover broad RTL blocks, so candidate regions require independent hardware review. The regenerated data live under gitignored `runs/provenance_v1/` and can be rebuilt with `python pipeline/provenance/build.py --all-paired`.

## Earlier-graph fallback

The original netlists under `trusthub/netlists/` preserve some Yosys `src` attributes on wires, and `trusthub/features/metadata/` provides the ordered gate names for their **earlier** graph version. `pipeline/localization/build_legacy_gate_candidates.py` maps each gate's output wire to an RTL source range and intersects it with the original RTL diff. Across the 21 Trojan-side graphs it found source ranges for 60,009 of 135,801 nodes (44.2%) and at least one candidate Trojan gate in 20 designs. AES-T2500 has none. The remaining nodes are unknown, not clean.

The 21 candidate files were checked against their corresponding earlier `.pt` graph tensors: graph IDs, node counts, and edge counts matched the metadata. This validates file alignment, not the correctness of the candidate labels.

These are review candidates only. A wire's source attribute can cover a declaration or broad expression rather than the Trojan operation, and some synthesis stages drop provenance. They cannot be transferred to the newer ZIP's graphs. Before using this fallback for scientific metrics, manually review candidate positives and a sample of negatives, check source line alignment, and define an exclusion rule for insufficiently covered variants.

## Required next input

For the **supplied ZIP's** `.pt` graphs, the original ordered node names remain unavailable. Use the regenerated `provenance_v1` graphs for future source-traced work, or obtain the original ZIP's matching metadata. Corrected CodeBERT embeddings with chunk-to-source-line spans are now available as `rtl_clean_v1` and `rtl_expansion_v1` and pass `pipeline/provenance/verify_rtl.py`. Complete independent semantic validation of broad gate source spans and candidate labels before claiming gate or RTL Trojan localization.

Only after reviewing source coverage and a sample of Trojan/clean labels should a gate-level evaluation run. The scorer in `pipeline/localization/score_localization.py` requires reviewed labels and identical node order between labels and predictions. Unknown cells use label `-1` and are excluded from metrics.

The explanation citation validator in `pipeline/explanations/validate.py` rejects nonexistent RTL citations and out-of-folder paths. Citation validity alone does not establish that a claim is factually correct. The benchmark descriptions are a separate reference set and must remain hidden from any explanation generator under evaluation.

## Claim gate

- Detection: separate versioned comparisons exist. The corrected source-traced development pilot scores 1.00 fusion balanced accuracy on three clean-source groups, but an RTL-length-only control reaches 0.786 and all four models score 0.50 balanced accuracy on the two new host designs. See `docs/CURRENT_RESULTS.md`. Full cross-validation on the supplied ~240,000-node AES graphs remains outstanding.
- RTL localization: changed-line candidates exist, but have not been manually validated against Trojan behavior.
- Gate localization: no valid metrics can be reported until node mappings and reviewed labels exist.
- Explanations: benchmark descriptions can serve as held-out references, not as inference input. Trigger, payload, location, and fix claims need evidence-linked evaluation; no explanation accuracy or engineer-study result exists yet.
- RTL chunk alignment: the originally packaged CodeBERT tensors contain no token-to-line offsets and include testbench text. The corrected embeddings save checked chunk-to-line spans for synthesizable RTL. These permit source-linked candidate rankings; they do not establish that high-attention chunks contain Trojans.
- Robustness: no obfuscated test set is present in this repository. It must be supplied or generated under a documented, held-out protocol.
