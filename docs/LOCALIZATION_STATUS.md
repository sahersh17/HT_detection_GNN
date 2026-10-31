# Localization and explanation evidence audit

Generated from the packaged 2026-10-31 data and the original Trust-Hub source folders. Run `python pipeline/localization/build_reference.py` and `python pipeline/localization/audit_reference.py` to refresh the machine-readable records in `data/localization_reference/`.

## What is available

| Evidence | Count | Status |
|---|---:|---|
| Paired clean/Trojan benchmarks | 21 (17 AES, 4 RS232) | Available |
| Original RTL on both sides | 21 | Available |
| Candidate changed RTL lines | 21 | Computed; needs review |
| Benchmark Trojan descriptions | 21 | Extracted as reference text; needs factual annotation |
| Ordered gate-to-source mappings for the new graph tensors | 0 | Missing |
| Verified gate-level ground truth | 0 | Blocked by missing mappings |

The 94-graph archive contains PyTorch Geometric objects with features, edges, a graph label, and a graph ID. It does not contain ordered gate names or source locations. Its `manifest.json` mentions metadata paths on another machine, but no metadata files are packaged. The older repo's graph node counts do not match any of the 42 paired samples in this archive, so assigning old metadata by node index would be invalid.

The linked `Hardware-Trojan-Detection/main/results/gnn/features/metadata` is also the older export: its `AES-T100/clean_netlist.json` has 7,903 nodes, compared with 240,258 in the supplied ZIP; its `RS232-T2100/tjin_netlist.json` has 78 nodes, compared with 121 in the ZIP. The linked `main/src/llm` generates RTL embeddings and does not establish node order or source locations for these newer graphs.

## Earlier-graph fallback

The original netlists under `trusthub/netlists/` preserve some Yosys `src` attributes on wires, and `trusthub/features/metadata/` provides the ordered gate names for their **earlier** graph version. `pipeline/localization/build_legacy_gate_candidates.py` maps each gate's output wire to an RTL source range and intersects it with the original RTL diff. Across the 21 Trojan-side graphs it found source ranges for 60,009 of 135,801 nodes (44.2%) and at least one candidate Trojan gate in 20 designs. AES-T2500 has none. The remaining nodes are unknown, not clean.

The 21 candidate files were checked against their corresponding earlier `.pt` graph tensors: graph IDs, node counts, and edge counts matched the metadata. This validates file alignment, not the correctness of the candidate labels.

These are review candidates only. A wire's source attribute can cover a declaration or broad expression rather than the Trojan operation, and some synthesis stages drop provenance. They cannot be transferred to the newer ZIP's graphs. Before using this fallback for scientific metrics, manually review candidate positives and a sample of negatives, check source line alignment, and define an exclusion rule for insufficiently covered variants.

## Required next input

For each new `.pt` graph, provide an ordered `node_names` list aligned exactly to `Data.x` rows, plus the RTL file and source line range for each node. The graph-generation script and any source-attributed Yosys JSON would allow the mapping to be regenerated and verified. If no such artifact exists, regenerate the graph tensors and mappings together from the original RTL using one fixed Yosys flow, then rerun graph, embedding, and pair audits.

Only after reviewing source coverage and a sample of Trojan/clean labels should a gate-level evaluation run. The scorer in `pipeline/localization/score_localization.py` requires reviewed labels and identical node order between labels and predictions. Unknown cells use label `-1` and are excluded from metrics.

The explanation citation validator in `pipeline/explanations/validate.py` rejects nonexistent RTL citations and out-of-folder paths. Citation validity alone does not establish that a claim is factually correct. The benchmark descriptions are a separate reference set and must remain hidden from any explanation generator under evaluation.

## Claim gate

- Detection: a three-model comparison has now run on the earlier, smaller graphs with the new CodeBERT embeddings; see `docs/BASELINE_RESULTS.md`. Fusion did not improve on the RTL-only baseline. Full cross-validation on the newer ~240,000-node AES graphs remains outstanding.
- RTL localization: changed-line candidates exist, but have not been manually validated against Trojan behavior.
- Gate localization: no valid metrics can be reported until node mappings and reviewed labels exist.
- Explanations: benchmark descriptions can serve as held-out references, not as inference input. Trigger, payload, location, and fix claims need evidence-linked evaluation; no explanation accuracy or engineer-study result exists yet.
- RTL chunk alignment: the packaged CodeBERT tensors contain chunk embeddings but no token-to-line offsets. Cross-attention can rank chunks, but it cannot identify exact RTL lines from those tensors alone. Regenerate and save tokenizer overflow offsets alongside embeddings before claiming attention-based line localization.
- Robustness: no obfuscated test set is present in this repository. It must be supplied or generated under a documented, held-out protocol.
