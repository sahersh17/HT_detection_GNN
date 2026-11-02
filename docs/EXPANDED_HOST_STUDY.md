# Expanded host study: development evidence

## Data and provenance

The local TrustHub archives contained seven previously unprocessed paired mapped-netlist variants: s15850-T100, s35932-T100/T200/T300, and s38417-T100/T200/T300. Their archive and extracted-source hashes passed `verify_extra_archives.py`; all 14 new graph tensors passed saved-Yosys-JSON reconstruction. The versioned detection protocol `data/lofo_expanded/protocol.json` contains 94 graphs, 47 pairs, and ten host families. It leaves the original 80-record protocol untouched. These newly inspected hosts are development data, not a prospective final test.

Eleven RS232-T1000–T2000 archives contain 90nm and 180nm mapped sources but no clean member in those packages. They are inventoried in `data/localization_gate_audit/rs232_archive_inventory.json`. All 22 technology-specific Trojan-only graphs parsed and verified as `rs232_gate_v1` (5,299 nodes total). Their instance names contain no `trojan` marker, so no labels are recoverable from that rule; they remain outside paired detection and scored localization. Group any future mapped and RTL RS232 records as one host family. MultPyramid-T100/T200 contain DEF layout files rather than RTL or gate netlists. Incomplete b19 multipart volumes remain excluded; complete b19-T300/T400/T500 single-volume VHDL pairs were synthesized separately into six `new_vhdl_v1` graphs. Their clean graphs have 142,734 nodes each; Trojan graphs have 143,934–146,982 nodes. All six passed saved-JSON reconstruction. The expanded b19 protocol is versioned in `data/lofo_expanded_b19/protocol.json` and contains 100 graphs, 50 pairs, and 11 hosts. Both expanded manifests passed graph/source hash and pairing checks. b19 uses GHDL-to-Yosys conversion and is not part of the same-format mapped model comparison.

## Paired size diagnostic

Across the original frozen 40 pairs, “larger graph is Trojan” is correct for 34 pairs; the saved GNN ranks the Trojan higher in 25. Their signs agree in 21 pairs. The size sign is negative for all four B15 pairs and positive for all s38584, PIC16F84, RS232, and AES pairs; MC8051 is mixed. This contradicts a simple claim that the GNN's inverted PIC16F84 and RS232 rankings are caused by following graph size. The descriptive seven-host bootstrap interval for equal-host GNN pair ranking is 0.294–0.878.

## Same-format mapped detection comparison

The mapped cohort contains 28 graphs, 14 pairs, and five held-out host families (b15, s15850, s35932, s38417, s38584). The GNN used scaled features, source-balanced weights, 25 epochs, and seeds 42–46. Each held-out family was excluded from its training fold. Baselines used the same folds. These results are development evidence; B15's mapped source and cell vocabulary differ from the ISCAS netlists.

| Method | Equal-host mean AUROC | Descriptive host bootstrap 95% interval |
|---|---:|---:|
| Scaled GNN, five-seed mean | 0.787 | 0.667–0.907 |
| Graph statistics | 0.567 | 0.200–0.900 |
| Directed WL histogram | 0.567 | 0.400–0.800 |
| Size-only | 0.333 | 0.000–0.733 |

The GNN minus statistics and GNN minus WL mean differences are each +0.220 AUROC. Their paired host-and-seed bootstrap intervals are -0.200 to +0.653 and -0.140 to +0.520, respectively. **Neither clears the proposed superiority gate.** GNN equal-host means range from 0.600 to 1.000 across seeds. At the fixed 0.5 threshold, every seed has 50% pooled accuracy. The ranking signal does not yet deliver useful calibrated detection. s15850 has one pair; all five hosts have been inspected.

The mapped results include s38584-T300 as a graph-labeled Trojan. Its source has a trigger-to-payload connection discrepancy described in `LOCALIZATION_LABEL_AUDIT.md`. Exclude or repair that variant under a versioned, predeclared sensitivity analysis before using this cohort for a functional-Trojan claim.

## Localization status and next experiments

The three new ISCAS hosts yielded inserted-cell candidate labels by graph instance diff. s15850-T100 and s35932-T300 have one more added cell than published Trojan counts and are flagged. Seven variants across three hosts passed the stricter correspondence gate for exploratory structural controls. Gate-class rarity reached 0.767 equal-host AUROC against these **unreviewed** candidate labels, with a descriptive three-host interval of 0.629–0.839. No node model is trained or scored as a localization claim.

Next, complete the blinded cell review and engineering checks, obtain additional independent clean hosts and insertion generators, then freeze a host and generator split before node-model training. Keep all labels and predictions source-hash aligned and exclude instance names and label-derived fields from model inputs. Compare per-host AP, AUROC, tie-aware hit@k, recall at a fixed inspection budget, and label coverage. A gain on these inspected hosts is development evidence; only new frozen hosts can support a generalization claim.

Reproduce the work from the repository root:

```powershell
trusthub/venv/Scripts/python.exe pipeline/provenance/prepare_gate_expansion.py
trusthub/venv/Scripts/python.exe pipeline/provenance/verify_extra_archives.py
trusthub/venv/Scripts/python.exe pipeline/provenance/synth_gate_netlists.py --family s15850
trusthub/venv/Scripts/python.exe pipeline/provenance/synth_gate_netlists.py --family s35932
trusthub/venv/Scripts/python.exe pipeline/provenance/synth_gate_netlists.py --family s38417
trusthub/venv/Scripts/python.exe pipeline/provenance/verify.py runs/new_gate_v1
trusthub/venv/Scripts/python.exe pipeline/build_lofo_expansion.py
trusthub/venv/Scripts/python.exe pipeline/lofo_graph_baselines.py --manifest data/lofo_expanded/protocol.json --cohort mapped
trusthub/venv/Scripts/python.exe pipeline/run_lofo_seeds.py --manifest data/lofo_expanded/protocol.json --cohort mapped --features scaled
trusthub/venv/Scripts/python.exe pipeline/report_mapped_expansion.py
trusthub/venv/Scripts/python.exe pipeline/size_delta_diagnostic.py
trusthub/venv/Scripts/python.exe pipeline/provenance/inventory_rs232_gate.py
trusthub/venv/Scripts/python.exe pipeline/provenance/prepare_rs232_gate.py
trusthub/venv/Scripts/python.exe pipeline/provenance/synth_rs232_gate.py
trusthub/venv/Scripts/python.exe pipeline/provenance/verify.py runs/rs232_gate_v1
trusthub/venv/Scripts/python.exe pipeline/provenance/prepare_b19_complete.py
trusthub/venv/Scripts/python.exe pipeline/provenance/synth_vhdl.py --family b19
trusthub/venv/Scripts/python.exe pipeline/provenance/verify.py runs/new_vhdl_v1
trusthub/venv/Scripts/python.exe pipeline/build_lofo_expansion.py --include-b19
trusthub/venv/Scripts/python.exe pipeline/verify_lofo_expansion.py
```
