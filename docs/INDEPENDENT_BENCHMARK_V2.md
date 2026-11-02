# Independent insertion benchmark: reproducible development intake

Status (2026-11-02): **no-go for detector or localization model claims**. This
is an exploratory intake of the pinned [DATE 2025 insertion framework](https://github.com/gkaggarwal/HT_Benchmark_HT_Insertion_Framework_DATE_2025/tree/c7a1269c2c6fd4ebfaec2245c7613dba84fd0228),
not a validated new benchmark. The two final-candidate hosts remain ungenerated.

## What ran

The pinned upstream code and six candidate host netlists were fetched as 21
text files. Their local Git blob hashes were checked against the pinned
upstream tree. No exact or comment/whitespace-normalized duplicate of those
six host files was found in the local Trust-Hub Verilog tree. That file-level
check does not prove structural or functional independence.

The development hosts were c2670, c3540, c5315, and s1423. c6288 and s13207
were reserved before generation and have not been used for model selection or
benchmark construction. Each development host received two combinational and
two sequential variants, for 16 Trojan variants in total. The external
framework is **one insertion source**, even though it has two mechanisms.
There is no paired original RTL view and no benign-decoy class in this corpus.

An initial v1 run revealed that the documented random seed did not reproduce
byte-identical netlists across fresh Python processes. The separate v2 adapter
pins `PYTHONHASHSEED=0` at process startup. All eight host/mechanism runs then
matched byte-for-byte in independent repeats. v1 remains an exploratory
record and is not mixed with v2.

## Behavior and lineage gates

| Independent check | Result | Meaning |
| --- | ---: | --- |
| Deterministic repeats | 8/8 host/mechanism runs | Byte-identical generated source in separate processes |
| Combinational-host SAT output-difference witness | 4/6 variants | c2670 and c3540 pass; c5315 T0/T1 have no defined-input top-level difference in the Yosys two-state miter |
| Simplified sequential trace with natural scan-FF state advancement and an output witness | 6/8 variants | c2670, c3540, c5315 pass in this model; both s1423 variants fail from the tested zero state and held input |
| s1423 combinational-insertion variants | 0/2 independently checked | Upstream self-validation only; not admitted as behavior-verified |
| Graph and candidate-label lineage | 16/16 variants | Graphs rebuild from recorded Yosys JSON and ordered candidate labels rebuild from source instance diff |

The sequential checker treats each simplified scan flip-flop as one DIN-to-Q
update per cycle. It does **not** prove original RTL timing or full reachability
from all legal states. The s1423 failure does not prove that no trigger trace
exists. The c5315 SAT result is specific to the defined-input, two-state,
top-output miter; it is enough to reject those two variants from this intake.

The graph lineage has 236 positive candidate nodes, 25,299 negative candidate
nodes, and 23 unknown nodes across 16 infected graphs. Labels come from added
source instances and Yosys source spans; changed, merged, or missing spans are
unknown. They have **not** been independently reviewed and are not established
ground truth. The sequential graphs use a port-only scan-FF stub for graph
construction, so their topology is a provisional representation.

## Shortcut gate

A standalone source gate-instance count ranks the Trojan above its clean
counterpart in **16/16** pairs. Synthesized graph node count does the same in
**16/16**. Characters, lines, and XOR count also rank all 16 pairs correctly.
This paired test evaluates a count score available separately on each netlist;
it does not assume the clean twin is available at deployment. A gate-class
rarity ranking also yields mean AP 0.155 on the four SAT-witness variants and
0.410 on six simplified-trace variants against unreviewed candidate labels.
Those localization numbers are **diagnostics**, not a validated model result.
They make rare injected gate types an important control for any later method.

No benign decoys, independent second generator, or reviewed node labels were
available. The preregistered gate therefore rejects this cohort for learned
method claims. We did not train a detector on it or open the reserved hosts.
The next benchmark iteration needs equivalent benign decoys, independent
top-level witnesses for every admitted Trojan, and transparent controls that
cannot solve the classes before any model is fitted. It also needs a second
independent insertion source and more held-out hosts for generalization.

## Reproduction and evidence

Compact evidence is in `data/independent_benchmark_v2/`: `manifest.json`,
`formal_combinational.json`, `sequential_trace.json`, `graph_lineage.json`,
`graph_verification.json`, `shortcut_preflight.json`,
`localization_controls.json`, and `decision.json`. Raw generated netlists,
graphs, SAT witnesses, and logs are under ignored `runs/independent_benchmark_v2/`.
The pinned upstream text files are under ignored `runs/third_party/date2025_vendor/`.
They are not part of a clean clone; fetch the pinned upstream commit and verify
all recorded Git blob hashes before rerunning. The upstream MIT license and
DATE citation must be retained if this code is redistributed.

From the repository root, with the project's Python environment and YoWASP
Yosys installed, the evidence checks are:

```text
trusthub/venv/Scripts/python.exe experiments/independent_benchmark_v2/verify_graphs.py
python experiments/independent_benchmark_v2/shortcut_preflight.py
trusthub/venv/Scripts/python.exe experiments/independent_benchmark_v2/localization_controls.py
python experiments/independent_benchmark_v2/decision.py
```

This is a **local reproduction** of evidence already generated. A fresh-clone
reproduction still requires fetching the pinned external files and the
project's dependencies, then regenerating and hash-comparing the raw artifacts.
