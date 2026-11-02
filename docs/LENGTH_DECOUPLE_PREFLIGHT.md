# Length-decoupling intervention: failed preflight

Status: **no-go for detector retraining**, 2026-11-02. The intervention was
tested on AES-T100 and RS232-T2100 only. It is a construction check, not a
measurement of RTL semantic detection.

The pilot appended an uninstantiated, synthesizable module to both class
sides. It tried to match character count, line count, and CodeBERT window
count while retaining each original source. Both sides received padding so
the mere presence of a module would not indicate class.

| Pair | Characters matched | Lines matched | Windows matched | Top port/cell inventory retained |
| --- | --- | --- | --- | --- |
| AES-T100 | Yes | Yes | No: 38 clean, 39 Trojan | Both sides |
| RS232-T2100 | Yes | Yes | Yes: 12 each | Clean only |

The number of padding assignment lines was greater on the clean side of both
pairs (199 versus 37; 44 versus 37). A transparent rule using that artifact
therefore solves both pilot pairs. On RS232-T2100, the padded Trojan also
changed the synthesized top cell-type inventory by one OR cell. The unused
module was pruned, but that inventory check does not prove full functional
equivalence. Accordingly no CodeBERT retraining or semantic-signal claim was
made. Inputs, generated padding hashes, synthesis hashes, and checks are in
`data/length_decouple_v1/preflight.json` and
`experiments/length_decouple_v1/preflight.py`.

The proposed clean-only padding has a structural problem: if the original
Trojan is longer, exact length matching tends to require more added text on
the clean side. An RTL classifier can potentially identify that added text.
Changing the padding to look like host code is insufficient by itself; the
editing operation, edit magnitude, and resulting tokenizer windows must all
be tested for class information.

## Next valid intervention

Use a class-independent source transformation that rewrites **both** sides
under the same sampled policy, with a declared budget and multiple source
styles. Include benign code in the actual top design only if sequential or
combinational equivalence to the original is independently established for
each side. Use real functionality-preserving rewrites rather than an unused
module. Record the edit seed, transformation family, source and synthesized
hashes, and pair identity. A held-out transformation family must be used for
the final RTL comparison.

Before training the Trojan detector, run transparent probes on source length,
line count, tokenizer windows, edit count, module/assignment count, and
transformation ID. Also train a padding-versus-unpadded probe and a
clean-versus-Trojan metadata probe on host-grouped splits. A chance result
with only two pairs would be inconclusive; the probe needs several independent
hosts, confidence intervals, and a predetermined maximum shortcut effect.
Then verify the no-edit and edited designs with formal equivalence or a
bounded, explicitly described state domain. Only after those checks pass
should RTL-only be retrained. Fusion requires a separately verified matched
graph view of the edited source.
