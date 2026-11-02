# Separate harmonization pilot

This experimental implementation has its own directory, dataset ID and outputs. It does not change the original graph builders, graph tensors, LOFO inputs, training code, or running confounder study. Outputs are deliberately **not training eligible** until stronger whole-design validation is established.

## Scope

Two clean/Trojan pairs: AES-T100 and RS232-T2100. Each side is transformed and checked independently. The original provenance JSON and original source hashes are verified before processing. The pilot starts from that existing elaborated representation; it is not an independent validation of the original Verilog frontend.

The recipe is `memory_collect; memory_map; opt; techmap; opt; check -assert`. There is no ABC, retiming, scan constraint, reset conversion or assumed clock stimulus in conversion. Generic Yosys gate primitives are exported with automatic source spans. `$scopeinfo`, `$print` and `$display` are nonfunctional metadata/diagnostics excluded from graph nodes; other nonprimitive cells block export. Existing raw graph files remain unchanged.

## Three distinct checks

1. **Graph integrity:** exact tensor reconstruction from output JSON, source hashes and row/source-span alignment, plus cell inventory and graph-growth reporting.
2. **Post-lowering equivalence:** compares the already memory-lowered reference with the primitive-mapped result. Exact JSON identity suffices when identical. Otherwise structural equivalence and SAT are attempted, with a strict success check and a timeout. A failed proof remains unproved. This does not independently prove the memory-lowering pass or every possible initial-state behavior.
3. **Independent ROM simulation:** Icarus compares the original Verilog `S` and `xS` units with their lowered implementations on all 256 binary input addresses and checks output stability between clock edges. Both source sides are checked. This validates these ROM units and clock holds, not a whole-AES formal proof, arbitrary X states, writable RAM, or every sequential behavior.

The final report intentionally keeps the distinction between successful conversion, scoped checks and whole-design acceptance. No reviewed localization labels are produced.

## Run

From the repository root, with the existing local YoWASP Yosys and Icarus installations:

```powershell
python experiments/harmonization_v1/inventory.py
trusthub/venv/Scripts/python.exe experiments/harmonization_v1/pilot.py
python experiments/harmonization_v1/rom_validation.py
python experiments/harmonization_v1/report.py
```

Large tensors, JSON snapshots, synthesis/proof scripts and logs are saved to `runs/harmonization_v1/`. The compact shareable report is written to `experiments/harmonization_v1/results/summary.json`. The scripts require the existing local provenance dataset. Conversion/proof failures and timeouts are recorded rather than treated as success.

On this machine Icarus compilation crashes inside the restricted execution environment but succeeds outside it. Running the ROM validator may therefore require the desktop app's explicit execution approval. A compiler failure is never accepted merely because an older simulation executable exists.

## Mapped library inventory

`inventory.py` lists the original B15 and s38584 archive members and required cell types. No candidate `.lib`, `.db`, named library/standard-cell mapping, or synthesis-log files were found by its inventory filters. It does not establish that every possible filename convention has been exhaustively identified. The listed Verilog netlists still need matching functional library definitions before they can be remapped faithfully. Do not substitute guessed AO/OA, arithmetic, reset or clock-gating behavior.

## Remaining acceptance work

Before expanding or training: establish whole-design equivalence with explicit initial/reset assumptions, confirm every AES memory instance is covered by validated lowering semantics, and obtain/validate mapped-cell functions. Physical timing/layout effects require separate assessment; Boolean equivalence cannot certify them. Common primitives also do not guarantee identical optimization or remove all host/synthesis confounding.
