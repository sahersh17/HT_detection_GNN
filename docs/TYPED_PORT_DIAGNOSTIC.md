# Typed-port graph diagnostic, exploratory

The earlier gate-only synthetic graphs omit primary inputs, real outputs, pin
identity, and constants. `experiments/port_aware_v2/build.py` constructs a
separate graph version for the same four-host G1c pilot. It keeps ordered gate
nodes and their constructed labels, then adds primary-input, real-output,
one-bit primitive input-pin, constant, and undriven-source nodes. Original
gate-to-gate edges remain for cells whose wide ports are not expanded.
Instance and top-level port names do not enter numeric node features.

Typing every bit of wide AES memory/arithmetic cells would produce hundreds
of thousands of extra nodes without representing the inserted one-bit trigger
more faithfully. Pin nodes are therefore limited to one-bit Yosys primitives.
The manifest records typed and untyped cell counts for each design. All 12
graphs passed source/graph hash, label-order, shape, role, and paired-count
checks. Three of the four hosts have no undriven source; PIC16F84 has one.

| Held-out-host control | Clean vs Trojan | Decoy vs Trojan |
| --- | ---: | ---: |
| Graph statistics | 0.50 | 0.50 |
| Directed WL, 2 rounds | 0.50 | 0.50 |
| Directed WL, 8 rounds | 0.25 | 0.75 |

Values are equal-host pairwise AUROC over four already inspected hosts. AES
and RS232 have equal WL8 histograms across all matched variants. PIC16F84
first differs at round 7 and memctrl at round 6. The previous port-aware
view first differed one round earlier for those two hosts; adding explicit
pin nodes lengthens paths. This comparison does not prove the two graph views
are equivalent, and it does not establish generalization.

The unchanged output-cone equivalence rule still solves the underlying G1c
task: it uses the source netlist and real output relation. The typed view
therefore **does not clear the benchmark no-go gate** or justify model
training. The graph representation is more complete, but the repeated XOR
mechanism remains a transparent shortcut.

Compact, hash-recorded outputs are in `data/port_aware_v2/`. Large tensors
are in `runs/port_aware_v2/`. Reproduce with:

```powershell
$py = '.\trusthub\venv\Scripts\python.exe'
& $py experiments/port_aware_v2/build.py
& $py experiments/port_aware_v2/verify.py
& $py experiments/port_aware_v2/probe.py
```
