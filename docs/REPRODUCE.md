# Reproduce the source-traced pilot and small cross-host diagnostic

The saved prediction artifacts are in `results/provenance_clean_pilot/` and `results/external_diagnostic/`. The large generated graphs, RTL embeddings, and model checkpoints stay under gitignored `runs/`. The Trust-Hub source archives are local project inputs and may need to be obtained separately if absent. All commands below run from the repository root on Windows PowerShell.

## Environment

Create a Python virtual environment, then install `trusthub/requirements.txt`. The validated run used Python 3.13.5, PyTorch 2.13.0, PyTorch Geometric 2.8.0.post1, transformers 5.15.1, and YoWASP Yosys 0.69.0.0.post1233. CodeBERT is pinned to Hugging Face revision `3b0952feddeffad0063f274080e3c23d75e7eb39` in `pipeline/provenance/embed_rtl.py`; the model files must be available in the local Hugging Face cache. PIC extraction requires [7-Zip](https://www.7-zip.org/download.html) on PATH or an explicit `--seven-zip` path.

Use `& .\trusthub\venv\Scripts\python.exe` in place of `python` below if that is where the environment is installed.

## Development set

```powershell
python pipeline\provenance\build.py --all-paired
python pipeline\provenance\verify.py runs\provenance_v1
python pipeline\provenance\embed_rtl.py
python pipeline\provenance\verify_rtl.py
python pipeline\train_cv.py --dataset provenance_clean --model rtl
python pipeline\train_cv.py --dataset provenance_clean --model gnn --epochs 25
python pipeline\train_cv.py --dataset provenance_clean --model fusion --epochs 25
python pipeline\length_baseline.py
python pipeline\length_baseline.py --graph-size
python pipeline\provenance\publish_pilot.py --dataset provenance_clean
python pipeline\verify_artifact.py --pilot provenance_clean_pilot
```

CodeBERT embedding generation can take several minutes on a CPU. The graph version deliberately omits ABC; do not attach its metadata to the supplied `HT_data_2026-10-31_b40cc08.zip` tensors. The original packaged RTL embeddings included testbenches and are not used in this corrected comparison. The development folds have been inspected and are not an untouched final test.

## New-host diagnostic

The host selection, seed, training duration, and threshold were fixed in `docs/EXTERNAL_DIAGNOSTIC_PROTOCOL.md` before evaluating these models. The diagnostic has now been inspected and cannot be used as an untouched final test again.

```powershell
python pipeline\provenance\prepare_memctrl.py
python pipeline\provenance\prepare_pic.py
python pipeline\provenance\build.py --benchmark memctrl-T100 --out runs\expansion_graphs
python pipeline\provenance\build.py --benchmark PIC16F84-T100 --benchmark PIC16F84-T200 --benchmark PIC16F84-T300 --benchmark PIC16F84-T400 --out runs\expansion_pic_graphs
python pipeline\provenance\verify.py runs\expansion_graphs
python pipeline\provenance\verify.py runs\expansion_pic_graphs
python pipeline\provenance\embed_rtl.py --expansion-only
python pipeline\provenance\verify_rtl.py --expansion
python pipeline\train_external.py --model rtl
python pipeline\train_external.py --model gnn
python pipeline\train_external.py --model fusion
python pipeline\train_external.py --model length
python pipeline\provenance\publish_external.py
python pipeline\provenance\publish_external.py --verify
```

`pipeline/train_external.py` refuses any exact RTL text overlap between development and diagnostic manifests. The publisher hashes inputs and rechecks every prediction and metric. There are only two independent new clean host designs, so this is a diagnostic rather than a powered external evaluation.

## Source-linked candidate rankings

```powershell
python pipeline\provenance\export_attention_scores.py --node-outputs runs\provenance_clean_fusion\node_outputs --out runs\provenance_clean_fusion\attention_scores
python pipeline\provenance\export_review.py runs\provenance_v1\AES-T100\trojan
```

The attention exporter validates the exact graph row order; the reviewer sheet is blinded as described in `docs/ANNOTATION_GUIDE.md`. Neither output is gate-level ground truth. There are no independent reviewers at present, so no localization or explanation accuracy metric is reported.
