"""Paths for the integrated, portable 2026-10-31 data package."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("HT_DATA_ROOT", ROOT / "data"))
RUNS = Path(os.environ.get("HT_RUNS_ROOT", ROOT / "runs"))

PAIRED_MANIFEST = DATA / "integrated" / "paired_manifest.json"
FOLDS = DATA / "integrated" / "group_folds.json"
GRAPH_ZIP = DATA / "HT_data_2026-10-31_b40cc08.zip"
EMB_ROOT = DATA / "integrated" / "embeddings"

SEED = 42
NODE_DIM = 20
RTL_DIM = 768
# Position of DFF in the packaged gate_vocab.json.
DFF_COL = 4
