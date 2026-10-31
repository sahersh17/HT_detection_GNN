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

## Required next input

For each new `.pt` graph, provide an ordered `node_names` list aligned exactly to `Data.x` rows, plus the RTL file and source line range for each node. The graph-generation script and any source-attributed Yosys JSON would allow the mapping to be regenerated and verified. If no such artifact exists, regenerate the graph tensors and mappings together from the original RTL using one fixed Yosys flow, then rerun graph, embedding, and pair audits.

Only after reviewing source coverage and a sample of Trojan/clean labels should a gate-level evaluation run. The scorer in `pipeline/localization/score_localization.py` requires reviewed labels and identical node order between labels and predictions. Unknown cells use label `-1` and are excluded from metrics.

The explanation citation validator in `pipeline/explanations/validate.py` rejects nonexistent RTL citations and out-of-folder paths. Citation validity alone does not establish that a claim is factually correct. The benchmark descriptions are a separate reference set and must remain hidden from any explanation generator under evaluation.

## Claim gate

- Detection: RTL-only training and data audits have run; complete GNN/fusion cross-validation on the large AES graphs is outstanding.
- RTL localization: changed-line candidates exist, but have not been manually validated against Trojan behavior.
- Gate localization: no valid metrics can be reported until node mappings and reviewed labels exist.
- Explanations: benchmark descriptions can serve as held-out references, not as inference input. Trigger, payload, location, and fix claims need evidence-linked evaluation; no explanation accuracy or engineer-study result exists yet.
- Robustness: no obfuscated test set is present in this repository. It must be supplied or generated under a documented, held-out protocol.
