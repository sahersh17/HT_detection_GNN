# Gate and RTL annotation guide

## Purpose and threat model

The evaluated detector receives one suspect design, not its clean twin. A clean/Trojan pair may be used to create reference annotations, but the clean twin and Trust-Hub description must not be passed to a detector or explanation generator at inference. Record the exact source and graph versions for every annotation.

## Independent review

1. Generate a source-traced graph using `pipeline/provenance/build.py` and pass its folder to `pipeline/provenance/export_review.py`. Give each reviewer a separate copy of the CSV, the suspect RTL, the clean RTL, and the synthesis graph. Hide model predictions and any other reviewer's answers.
2. Reviewers mark `reviewed_label` as `1` for gates implementing trigger or payload logic, `0` for gates confidently unrelated to the Trojan, and `-1` when evidence is missing or ambiguous. Leave it blank if not examined. The automatic `candidate_label` is a search aid only; reviewers must inspect the circuit context. Record the source line or structural reason in `evidence_or_reason` and a stable reviewer ID.
3. Mark RTL lines separately as trigger, payload, both, unrelated, or uncertain. Record trigger condition, payload effect, and proposed fix in structured notes with exact source citations. A changed line is not automatically malicious, and synthesis may spread one RTL operation across many gates.
4. Compare the two independent reviews. Report agreement on jointly reviewed gates and line roles, plus coverage over all nodes. Adjudicate disagreements with a third reviewer or a documented joint decision. Keep unresolved cells at `-1`; never fill them with negatives merely to increase coverage.
5. Freeze the adjudicated files and their hashes before running localization scoring. A reviewed-label JSON must contain the exact graph ID and ordered node-name list from its graph metadata. `pipeline/localization/score_localization.py` rejects unreviewed or misaligned files.

## Minimum audit before using labels in a paper

- Check all proposed positive cells and a stratified sample of negatives and unknowns across gate class, source file, graph degree, and design family.
- Report node-source coverage and reviewed-label coverage separately. A high `src` coverage percentage does not establish label correctness; broad Yosys spans can include unrelated logic.
- Report variants with zero confirmed positives or poor coverage and specify exclusions before testing a method.
- Keep original Trust-Hub descriptions as held-out factual references for trigger and payload judgments. Do not derive an explanation and score it against the same text used to generate it.
- Record synthesis warnings, especially latches and driver conflicts, and determine whether they affect label validity.

The current CSV export and `candidate_labels.json` are **unreviewed**. No localization accuracy or explanation correctness result should be reported from them yet.
