# Six-family original RTL overlap intake

The original-only preflight was committed on ver2 at 956c157 before the first variant synthesis. The parent admission protocol remains the one frozen at 7e7e7d0. Six external families enter this run as a separate cohort. Prior TrustHub derivatives, Tier 1/2 designs and both Tier 3 designs contribute zero families to its sample count.

## Original screen

The reference comprises the clean RTL of the inspected AES, RS232, PIC16F84 and memory-controller families. Normalized token counts range from 1,343 to 20,907. The same file-based lexer, keyword treatment and family weighting are used for both domains. Counts include the contents of selected compilation files, including conditional code and alternative configurations within those files. They exclude separate testbenches. Individual range overlap means membership in the observed min-to-max interval. It does not imply an exact nearest-neighbor match.

| Family and top | Upstream | Normalized tokens |
| --- | --- | ---: |
| Binary64 divider, double_divider | dawsonjon/fpu | 1,407 |
| Capture instrument, wbscope | ZipCPU/wbscope | 1,853 |
| SHA-224/256, sha256_core | secworks/sha256 | 3,056 |
| AXI-Lite I2C controller, i2c_master_axil | alexforencich/verilog-i2c | 5,738 |
| JPEG Huffman decoder, jpeg_dht | ultraembedded/core_jpeg | 12,516 |
| Processor, picorv32 | YosysHQ/picorv32 | 17,780 |

Each top and its dependencies came from a different pinned repository. The manifest identifies each commit and checked Git source blob. No RTL file hash is shared across these six designs. The Wishbone instrument is a capture peripheral, and the processor is an upstream implementation distinct from the earlier teaching core. These are engineering provenance checks. Statistical independence across the wider hardware population is unestablished. Candidates were intentionally selected for length and testability. Four successively larger clean reference families do not provide a representative sample of all hardware designs.

The original-token origin rank was 0.500. Its exact six-host percentile bootstrap interval was [0.333, 0.667], inside the existing [0.30, 0.70] practical band. The archive data is an inspected development cohort; selection on this metric precludes a blind source-transfer claim.

## Construction and verification

Each family has an unmodified original, an algebraically equivalent source edit, and one intentional fault. Use the source bundle and materializer below to reconstruct byte-exact standalone triplets. Upstream license notices are included. Synthetic lineage is explicit in the manifest and in the bundle index.

| Host | Normal and directed observations |
| --- | --- |
| Divider | 6.0 / 3.0 returns 2.0. Dividing -1.0 by negative infinity returns positive zero on the original and negative zero on the fault. |
| Capture instrument | The control register retains the low holdoff value. The fault loses the top bit of 0x81234 on write/read. |
| SHA-2 | SHA-256 of abc matches its reference. A changed SHA-224 initialization constant alters the SHA-224 digest. |
| I2C controller | AXI-Lite prescaler writes/readbacks agree when both bytes match. The fault returns 0x4545 after a write of 0x8145. |
| JPEG decoder | The tested default luminance DC codebook has twelve valid symbols. The fault returns symbol 10 in place of 11 on the final nine-bit code. |
| Processor | A short program stores two XOR results. The normal store is 7; the overlapping-bit case stores 7 in place of 6. |

All six local benign-expression SAT proofs passed at the tested default parameters. Each changed expression is the only substantive source change at a unique site. The full original/benign/fault top was simulated in both source and mapped Verilog. Every expected observation matched in the negative arms, and each positive arm had exactly the designated differing observation. These are bounded digital-fault witnesses. No activation-frequency or broad stealth claim follows. The installed YoWASP frontend needed a larger execution stack for the original JPEG lookup tables; the same binary and synthesis commands were used for all hosts.

## Frozen decision

Hold training. All 12 gate-type distance comparisons were within 5% (maximum 1.05%). Typed feature invariants distinguish both opposite-label pairs on all six hosts. No control point estimate crossed 0.90 in either direction. There were 29 scalar-class or origin intervals outside the required equivalence band. For example, the cell-count paired interval against the genuine original is [0.250, 0.917]. The normalized-token origin score on synthetic positives is 0.470 [0.292, 0.656]. The input fanout control has nonzero features on all 18 rows. The output-XOR and cone-equivalence probes have zero coverage. The six-family count, semantics, and size-overlap successes alone do not open the training gate.

The report gives all family scores and pointwise intervals. Resampling is conditional on the inspected reference panel and the held-out probe predictions. A hard stop crossing and failure to demonstrate practical equivalence are separate outcomes.

## Use and reproduction

For source use alone, run the bundle command with the system Python. It reconstructs all arms and verifies their hashes without network access.

```powershell
python experiments/overlap_six_v1/bundle.py
```

For a fresh full experiment, run the following from the repository root with the existing reference artifacts, installed project environment, Icarus, and Git. The fetch flag obtains the pinned upstream commits if the local source directories are missing.

```powershell
.\trusthub\venv\Scripts\python.exe experiments/overlap_six_v1/intake.py --fetch
python experiments/overlap_six_v1/generate.py
python experiments/overlap_six_v1/verify.py
python experiments/overlap_six_v1/bundle.py --pack
.\trusthub\venv\Scripts\python.exe experiments/overlap_six_v1/score.py
```
