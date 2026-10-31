# Evidence-linked explanation format

An explanation JSON has a `benchmark` and a list of `claims`. Each claim has a `kind` (`where`, `trigger`, `payload`, or `fix`), `text`, and at least one RTL citation with `file`, one-based `line`, and an exact `quote` from that line. Run `python pipeline/explanations/validate.py explanation.json <trojan-rtl-folder>` to reject nonexistent citations.

This validator establishes that citations point to real source lines. It does not prove that a cited line supports a trigger, payload, or fix claim. Compare those claims with the held-out benchmark descriptions in `data/localization_reference/`, and have a hardware engineer review a sample. The descriptions must not be given to a model when generating the explanations being scored.
