# Tier 3 and shared-host admission experiment

The protocol in this directory was committed at 7e7e7d0 before variant construction. All hosts are inspected development families. The Tier 3 dataset contains three labeled arms of each of two new designs. The separate shared-host cohort extends the RS232 pilot to AES-T100 and PIC16F84-T100. Regenerate native-host edits from the existing TrustHub sources with the builder. The source files in the original TrustHub archive are unchanged.

| Family | Baseline contract | Benign edit | Synthetic functional fault |
| --- | --- | --- | --- |
| RV32 pipeline | Three stages with branch flush, dependency handling, word load/store and a subset of integer, branch and jump instructions | Reverse the operands and comparison direction of BLTU | Compare the operands as signed values for BLTU |
| Wishbone interconnect | Two masters and two slaves, one outstanding classic transfer, stable grant during wait states, round-robin contention | Equivalent Boolean expression for the next owner | Regrant the previous owner under sustained contention |
| AES | Existing AES-128 core and native known-answer bench | Identity on an output byte equal to 0x32 | Return 0x33 for that byte |
| PIC16F84 | Existing core fetching sequential NOP instructions from reset | Identity on fetch address 13 | Expose address 12 at that fetch |

The new CPU supports ADDI, XORI, ANDI, ADD, SUB, XOR, OR, LUI, LW, SW, BEQ, BNE, BLTU, JAL and JALR on its declared aligned, zero-wait interface. This is a teaching subset. The test program checks retired PCs, destinations, results, stores, a dependent load, branch flushing, jumps and a backward loop. The interconnect bench checks grants, acknowledgments, address, byte selects and both read/write paths across waits, reset, isolated requests and sustained contention.

## Verification and dataset use

The original Tier 3 sources are independently runnable RTL files. Each sibling includes the whole design. The manifest groups every derivative under its original family and identifies whether it belongs to Tier 3 or the shared-host experiment. Native derivatives are reproducible local build products with retained source notices. The catalog references the previous dataset and tracks admission separately from inventory.

The two Tier 3 benign arms receive whole-module Yosys equivalence checks. In the two native arms, only the output expression changes and SAT checks that expression over all upstream bit values. The simulations compare source and mapped outputs. For PIC source simulation only, two procedural temporary declarations must be changed from wire to reg for Icarus. The original source is used for synthesis and source controls. PIC's original and both derivatives expose unknown fetch addresses throughout the 160-sample mapped trace following a power-on reset pulse. Their RTL traces are diagnostic only.

## Reproduction

Run from the project root with the original local TrustHub source trees, the retained typed-fusion reference manifest, the project Python environment and cached CodeBERT tokenizer. Yosys and Icarus are the same tools used for earlier development cohorts.

```powershell
python experiments/tier3_admission_v1/build_cohort.py
python experiments/tier3_admission_v1/verify.py
.\trusthub\venv\Scripts\python.exe experiments/tier3_admission_v1/admission.py
```

Source hashes and DUT tops are in the manifest. The admission report contains each per-family paired score, empirical host-bootstrap intervals, gate-type deltas, typed distinguishability checks, motif coverage, and within-label origin rankings. Family bootstrap intervals condition on the inspected TrustHub reference panel and the fitted fold scores. With only two families per cohort, they are descriptive. Corpus-format controls use both raw text and a deterministic lexical projection that strips comments and whitespace and substitutes identifiers while preserving a fixed keyword list. That projection is used for measurement only.

## Gate-type overlap

The metric is the sum of absolute gate-type count differences divided by the number of gates in the negative arm. The frozen maximum is 5% in each comparison. Gates are counted after the same synthesis flow, excluding scope metadata.

| Family | Original / benign / fault cells | Distance vs original | Distance vs benign | Mapped replay |
| --- | --- | ---: | ---: | --- |
| RV32 pipeline | 2710 / 2886 / 2710 | 0.15% | 6.10% | Passed |
| Wishbone interconnect | 184 / 184 / 183 | 0.54% | 0.54% | Passed |
| AES | 15680 / 15698 / 15698 | 0.11% | 0.00% | Passed |
| PIC16F84 | 2222 / 2246 / 2246 | 1.54% | 0.00% | Failed on all arms |

The RV32 signedness fault changes the retired PC from 0x28 to 0x2c at the first divergent instruction. The Wishbone fault gives the contested grant to master 1 when the oracle expects master 0. The AES trigger changes the last ciphertext byte from 0x32 to 0x33. The PIC source witness maps fetch address 13 to 12.

## Admission outcome

Hold training. All six Tier 3 arms passed behavioral verification, but on both new hosts the fault had fewer cells and fewer edges than the benign edit. On the two native families the fault was larger than the original on both. The descriptive two-family results meet the frozen shortcut stop rule. They do not establish population-level effects.

The frozen neutral-identifier score did not perfectly separate the new Tier 3 host sources from TrustHub. Normalized token count and CodeBERT window count did: every Tier 3 file scored lower than every same-label member of the inspected four-family reference panel. Within the shared native families, the fault arms also scored lower in normalized token count than all same-family native Trojan references. The output-cone rule had zero nonzero vectors on both cohorts. Typed feature invariants distinguished all eight opposite-label pairs, including the structurally measurable PIC pairs that failed mapped behavioral verification. The experiment has four development families against a minimum of six evaluation families. No records were admitted and no detector was trained.
