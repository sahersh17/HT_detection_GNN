# Hardware Trojan detection

This repository contains a research pipeline for classifying circuit designs as clean or Trojan-inserted. The original Trust-Hub processing work is under `trusthub/`. The later Colab experiment is preserved in `research/capstone.ipynb`. The runnable comparison code is under `pipeline/`, and its matching 2026-10-31 data package is under `data/`.

## Data versions

- `trusthub/features/` contains the earlier 93-graph dataset and should not be mixed with the newer data.
- `data/HT_data_2026-10-31_b40cc08.zip` contains 94 newer graph tensors and 94 CodeBERT embeddings. Keep this large archive locally at that path; it is excluded from Git. Its portable pair list marks 60 usable. The integrated comparison uses the **42 clean/Trojan samples from 21 paired benchmarks**; 18 usable but unpaired samples are omitted so each benchmark has both labels.
- The AES graphs in the new package are much larger than the earlier ones. Training the graph and fusion models needs substantial RAM and is best run with a GPU.

## Run

Use the Python environment in `trusthub/venv` (with PyTorch and PyTorch Geometric). From the repository root:

```powershell
& .\trusthub\venv\Scripts\python.exe pipeline\prepare_data.py
& .\trusthub\venv\Scripts\python.exe pipeline\audit_data.py
& .\trusthub\venv\Scripts\python.exe pipeline\train_cv.py --model rtl
& .\trusthub\venv\Scripts\python.exe pipeline\train_cv.py --model gnn --epochs 25
& .\trusthub\venv\Scripts\python.exe pipeline\train_cv.py --model fusion --epochs 25
& .\trusthub\venv\Scripts\python.exe pipeline\report.py rtl=runs\rtl\predictions.json gnn=runs\gnn\predictions.json fusion=runs\fusion\predictions.json
```

`prepare_data.py` writes portable manifests and extracts only the small embedding files. Graphs remain in the compressed archive. The three evaluation folds group benchmarks by identical clean RTL text, avoiding overlap of repeated clean designs between training and test data. All models use the same folds.

## Interpretation and remaining research work

`research/capstone.ipynb` is a record of an earlier Colab experiment with its own absolute paths and data version. Its reported 52-sample fusion result is not a measurement of this integrated dataset. The `pipeline/` scripts are the canonical path for new runs.

The localization helpers under `pipeline/localization/` can compare original clean/Trojan RTL and create node labels from synthesis source attributes. The supplied data archive does not include those source-attributed graph mappings, so attention scores alone are not verified Trojan locations. To evaluate localization, regenerate source-attributed netlists, align their node names with the model graphs, then score against ground truth and a random baseline.
