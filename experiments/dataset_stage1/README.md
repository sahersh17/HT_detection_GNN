# Stage 1: locked dataset inventory and development split

Status: completed on 2026-11-03. This stage makes no model or accuracy claim.

## Artifacts

- `data/dataset_stage1/records.csv` and `records.json`: one row per circuit with
  role, host, benchmark, label, source project and owner, source revision, edit
  generator, mechanism family, synthesis-flow identifier, graph size, and RTL
  character, line, and CodeBERT chunk counts. Each row retains the existing
  prepared-tensor, semantic-tensor, mapped-netlist, and source-bundle hashes.
- `data/dataset_stage1/folds.json`: five deterministic development folds. All
  circuits from a host, repository, and repository owner stay in one fold.
  Cohort and mechanism are balanced where possible. The ten previously
  inspected PIC16F84/memctrl circuits are absent from these folds.
- `data/dataset_stage1/protocol.json`: input manifest hashes, roles, reserved
  project candidates, primary development metrics, controls, and final-test
  policy. The lock script refuses to replace these files with different
  content or to proceed after a locked input manifest changes.
- `data/dataset_stage1/summary.json`: compact audit findings and fold sizes.

Run `trusthub/venv/Scripts/python.exe experiments/dataset_stage1/lock.py` from
the repository root to verify and reproduce the lock. It hashes 195 prepared
records and 450 distinct source paths, checks the legacy and semantic manifest
alignment, and reconstructs model-view text from the original sources and the
recorded sanitizer. The previously saved semantic verifier is required to be
complete. The script does not load the larger semantic tensors or inspect
the two reserved project candidates.

## Inventory and split

The development pool has 185 records, 60 hosts, 60 source repositories and 57
repository owners. It contains 120 negative and 65 positive circuits: 18
baseline, 147 native edits, 16 four-project revisions, and four original
Trust-Hub RS232 records. Among the 49 native-edit hosts, 41 use a literal edit
and eight use an input-pin index edit. The five development folds contain 12
hosts each and 36–38 validation records each. Every development record occurs
once as validation; no host, source project, or source owner crosses a fold.

The PIC16F84/memctrl diagnostic has ten records from two already inspected
hosts. Its five positive mechanisms are marked unknown because the local
provenance does not independently document their attack category. This
diagnostic may be reported descriptively but cannot select a model,
hyperparameter, feature, or threshold. There is **no admitted untouched final
test set**. The existing SERV and wb2axip repositories remain reserved
project candidates; their variants were not opened or scored in this stage.

Three repository owners appear in more than one development host:
`alexforencich`, `secworks`, and `ultraembedded`. Owner-grouped folds keep
those related hosts together. The 49 native hosts all come from the Tiny
Tapeout source collection and the same mutation procedure; owner grouping
cannot make that cohort independent of its generator. A later generator or
mechanism holdout remains a separate stress test.

## Provenance issue found

Twelve saved, human-readable `.v` model-view copies from four native hosts
do not byte-match the sanitized-text hash in the training manifest. Diffing
them against text reconstructed from the original source and the recorded
sanitizer shows Unicode encoding substitutions. The reconstructed text
matches the recorded hash, while each prepared `.pt` tensor matches its
manifest hash. The row-level character and line counts in this stage use the
reconstructed manifest-matching text. Stage 2 should read the frozen `.pt`
embeddings and these locked metadata records; it should not re-embed from
the twelve divergent `.v` copies. Rebuilding all RTL embeddings under one
explicit UTF-8 rule would be a separate, versioned experiment.

## Stage 2 boundary

The next stage may fit CPU baselines using only the 185 development records
and the five locked folds. It should report equal-host AUROC, within-host
ranking, balanced log loss, and accuracy at a threshold selected entirely
within each training fold, beside size, RTL-length, and chunk-count controls.
The inspected diagnostic and reserved project candidates remain outside
model selection. A new final host set must be sourced and frozen before any
final generalization claim.
