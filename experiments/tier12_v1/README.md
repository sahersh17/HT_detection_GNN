# Tier 1 and Tier 2 development pilot on ver2

The pilot has nine generated hosts and 27 RTL designs. Each host has one original, one function-preserving edit, and one intentionally faulty edit. All three use the same interface, formatting policy and neutral internal names. Each edit replaces one expression in the same host. Host descriptions and the directed inputs are in the witness files.

| Tier | Development hosts |
| --- | --- |
| 1 | SPI byte master, I2C byte writer, four-entry FIFO, SRAM controller, CRC32 |
| 2 | ALU, multiply-accumulator, three-tap FIR, PWM timer with wrap interrupt |

The SPI and I2C designs implement the byte transactions specified in their witnesses. The MAC covers multiplication and accumulation. This pilot uses one implementation source. Payloads corrupt data, suppress an acknowledgement status, or suppress an interrupt. Leakage, independent-generator transfer, and host independence from all historical designs have not been validated.

## Verification

The generator checks clean outputs against a separate cycle model. The CRC reference uses the standard library CRC32 implementation. The bounded normal workload has 640 random command cycles with byte values from 1 to 127 and a reset halfway through. A second trace starts at reset and demonstrates each Trojan effect at a top-level output. An additional post-gate stress replay exercises full-range byte operands for 1,536 random commands per host. Its differing-output counts are descriptive and do not affect the frozen shortcut threshold.

Across the 27 designs, 59,799 cycle outputs matched between RTL and mapped simulation. During full-byte random stress, the SPI Trojan diverged on four output cycles. The other eight had zero differing cycles in that replay. Every directed trigger produced a difference.

All three sides use the Verilog provenance flow through Yosys process lowering, optimization, flattening, technology mapping, and final optimization, without ABC. Yosys equivalence checks compare the benign and original designs. Icarus replays the stimulus on every RTL and mapped implementation, checking every output cycle. The witnesses establish reachability for these digital effects. Workload agreement describes only the exercised cycles.

## Decision

Retain the cohort for the benchmark audit. Source character count, graph node count, and graph edge count each put the Trojan above its original on all nine hosts. Each exceeds the threshold of 0.90 specified before scoring. In the benign-edit comparison, character count gives a tie-adjusted win rate of 0.500 and node and edge count each give 0.611. The unchanged output-XOR and output-cone controls tie on both comparisons. Neither result establishes that this cohort is free of other shortcuts.

The integrated ver2 catalog references the existing 42 paired records and the 27 generated development records. Zero generated rows are admitted to detector training. Results are reported separately. Further work should change the edit construction on these inspected hosts, verify both the ordinary and benign negatives, and repeat the controls before collecting any untouched evaluation set.

## Reproduce

From the repository root, with Icarus Verilog on PATH, the pinned CodeBERT tokenizer cached, and the project Python environment installed:

```powershell
python experiments/tier12_v1/build.py
.\trusthub\venv\Scripts\python.exe experiments/tier12_v1/audit.py
```

The first command generates the RTL, runs Yosys and both simulations, and writes the semantic manifest after all assertions pass. The second checks the source and netlist hashes, rebuilds the graph views, runs host-held-out transparent probes, and writes the decision and catalog. Fitted probes use the other eight hosts in each fold. The individual count rules require no fit. Scores award half credit for ties and weight hosts equally. Generated logs, simulator inputs and graph tensors are under the local runs directory and can be rebuilt.
