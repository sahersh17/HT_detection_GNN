# New Trust-Hub data engineering

The November 2026 expansion preserves distinct source formats. Downloads remain in their original folders; extracted sources and generated tensors are under `runs/`. The reproducible cohort is written to `data/new_trusthub/cohort_manifest.json` by the final audit.

Completed validation: 28 graphs containing 298,362 nodes; 17 VHDL embedding records containing 9,600 chunks from 11 unique source texts; 16 passing regression tests. Every graph passed reconstruction, source/hash checks and an untrained GNN forward pass. Both sides of MC8051-T200 passed full fusion forward checks with all their RTL chunks. See [cohort audit](../data/new_trusthub/cohort_manifest.json) and [archive/graph checks](../data/new_trusthub/engineering_checks.json). These are compatibility tests, not trained detection or localization scores.

| Family | Downloaded benchmarks | Processing |
|---|---:|---|
| B15 | 4 paired | Parse supplied mapped layout netlists into 8 directed gate graphs |
| s38584 | 3 paired | Parse supplied mapped gate netlists into 6 directed gate graphs |
| MC8051 | 7 paired | Synthesize the 46-file VHDL core configuration with GHDL, convert to Verilog, then build 14 Yosys graphs |
| BasicRSA | 3 Trojan only | Extract and embed VHDL; record synthesis failures; exclude from paired classification |
| PIC16F84 | 4 | Archive SHA256 matches the previously processed PIC archives; exclude duplicate copies |
| b19 partial downloads | 23 files | Incomplete/nonbenchmark volume files excluded; no reconstructable complete benchmark accepted |

Later inventory found three separate complete single-volume b19 archives (T300/T400/T500) in `trusthub/AES_zipped/`. These are distinct from the incomplete multipart downloads. Their six paired VHDL graphs were built and verified as `new_vhdl_v1`; see [the expanded host study](EXPANDED_HOST_STUDY.md). Three additional paired mapped ISCAS hosts (s15850, s35932, s38417) were also extracted and verified. The earlier cohort counts in this document refer to the original expansion stage.

## Family-specific synthesis

`synth_gate_netlists.py` handles B15 and s38584. Its library stubs specify port directions, including full-adder and multiplexer exceptions. They do not implement cell truth tables. The graph preserves supplied cell connectivity; this is not a functional equivalence proof. Source locations refer to gate-netlist lines, not original RTL.

`synth_vhdl.py` selects MC8051's `mc8051_core_struc_cfg`, excluding FPGA wrappers, simulation memory and testbenches. It resolves the clean core dependency list using GHDL and imports the corresponding files on both sides. GHDL uses VHDL-93, Synopsys packages, explicit overload resolution and latch support. Yosys applies `proc; opt; flatten; opt; techmap; opt` without ABC. MC8051-T500 needs one compatibility substitution: `Key sla 1` becomes `Key(6 downto 0) & Key(0)`. The original eight-bit arithmetic shift and replacement agreed for every one of 256 possible inputs in GHDL simulation. The adapted copy and hashes are retained; original archives and extracted files are unchanged. This proves that expression replacement only, not whole-design equivalence.

BasicRSA uses its own top `RSACypher` and source ordering (`modmult.vhd`, then `rsacypher.vhd`). All three sources currently fail GHDL synthesis with multiple assignments to `modreg`; logs also identify component binding and latch issues. Repairing these requires checking the intended benchmark behavior. No clean counterparts were supplied.

Generated MC8051 graph source spans currently point to generated Verilog. Original VHDL embeddings retain chunk-to-VHDL line spans, but these do not establish a gate-to-original-VHDL mapping. No reviewed Trojan gate labels have been added.

## Reproduce

From the repository root, use `trusthub/venv/Scripts/python.exe` as Python. Required local tools are YoWASP Yosys 0.69, 7-Zip, and GHDL 6.0.0. The scripts accept synthesis tool overrides. The official Windows mcode GHDL archive used here has SHA256 `c1562b2a4767e34d33159b536b5e36a8a38ebdb6e7672aa9969a4f4ac2cadffe`.

Run every stage with `trusthub/venv/Scripts/python.exe pipeline/provenance/run_new_pipeline.py`, or use the individual commands below. BasicRSA failures are recorded outcomes and remain excluded from graph cohorts.

```powershell
$py = '.\trusthub\venv\Scripts\python.exe'
& $py pipeline/provenance/prepare_new_archives.py
& $py pipeline/provenance/verify_new_archives.py
& $py pipeline/provenance/synth_gate_netlists.py --family b15
& $py pipeline/provenance/synth_gate_netlists.py --family s38584
& $py pipeline/provenance/synth_vhdl.py --family MC8051
& $py pipeline/provenance/synth_vhdl.py --family BasicRSA
& $py pipeline/provenance/verify.py runs/new_gate_v1
& $py pipeline/provenance/verify.py runs/new_vhdl_v1
& $py pipeline/provenance/embed_new_vhdl.py
& $py pipeline/provenance/verify_rtl.py --new-vhdl
& $py pipeline/provenance/audit_new_data.py
& $py -m unittest discover -s pipeline/tests
```

The embedding stage uses the same pinned CodeBERT revision and 512-token windows as the earlier pipeline, on original VHDL. Windows restart at each source-file boundary, allowing identical files to reuse cached encodings. This is a distinct embedding version from the earlier cross-file Verilog windows. Gate-only benchmarks have no original RTL modality. The final audit checks archive/source hashes, graph reconstruction, labels, feature dimensions, source spans, embeddings and an untrained GNN forward pass. Passing these checks establishes data integrity and model compatibility, not detection accuracy.

## Evaluation constraints

Keep all variants of each host family together in any split. The 14 new paired benchmarks represent three host families, with repeated clean designs. PIC copies add no independent evidence. B15's clean netlists are larger than its Trojan netlists, so size can become a shortcut. Mapped-cell graphs and GHDL graphs have different synthesis domains from the previous Verilog pilot and require controlled evaluation. Do not merge their node labels or order with old graph versions.

Before claiming improved detection, freeze a host-grouped evaluation protocol, measure size-only baselines, and test synthesis-domain effects. Before claiming localization accuracy, establish original-source mappings and validated Trojan gate labels. The current additions expand usable data engineering coverage; they do not by themselves make the paper publication ready.
