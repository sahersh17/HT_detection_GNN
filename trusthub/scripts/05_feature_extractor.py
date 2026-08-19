from pathlib import Path
import json
import torch

from feature_extractor import FeatureExtractor

# ==========================================================
# CONFIG
# ==========================================================

PARSED_ROOT = Path(r"C:\HT_detection_GNN\trusthub\parsed")
GRAPH_ROOT = Path(r"C:\HT_detection_GNN\trusthub\graphs")
FEATURES_ROOT = Path(r"C:\HT_detection_GNN\trusthub\features")

FEATURES_ROOT.mkdir(parents=True, exist_ok=True)
(FEATURES_ROOT / "data").mkdir(exist_ok=True)
(FEATURES_ROOT / "metadata").mkdir(exist_ok=True)

# ==========================================================
# Locate every (json, gpickle) pair
# ==========================================================

json_files = sorted(PARSED_ROOT.rglob("*.json"))
pairs = []

for json_file in json_files:
    relative = json_file.relative_to(PARSED_ROOT)
    gpickle_path = (GRAPH_ROOT / relative).with_suffix(".gpickle")

    if not gpickle_path.exists():
        print(f"SKIP (no graph found): {relative}")
        continue

    graph_id = str(relative.with_suffix("")).replace("\\", "/")
    pairs.append((json_file, gpickle_path, relative, graph_id))

print(f"\nFound {len(pairs)} graphs with matching parsed netlists\n")

# ==========================================================
# PASS 1 — fit gate-class vocabulary across the WHOLE dataset
# ==========================================================

print("Fitting gate-class vocabulary...")
extractor = FeatureExtractor()
extractor.fit_vocab([gp for _, gp, _, _ in pairs])
extractor.save_vocab(FEATURES_ROOT / "gate_vocab.json")
print(f"Vocabulary size (incl. UNK): {extractor.vocab_size}")
print(f"Gate classes found: {extractor.gate_classes}")
print("Node feature layout: [one-hot gate class] + [in_deg, out_deg, controllability, observability]\n")

# ==========================================================
# PASS 2 — extract features for every graph
# ==========================================================

manifest = []
success = 0
failed = 0

for json_file, gpickle_path, relative, graph_id in pairs:

    print("-" * 70)
    print(relative)

    try:
        with open(json_file, "r") as f:
            parsed = json.load(f)
        label = parsed["label"]

        data, metadata = extractor.extract(gpickle_path, label, graph_id)

        data_path = (FEATURES_ROOT / "data" / relative).with_suffix(".pt")
        meta_path = (FEATURES_ROOT / "metadata" / relative).with_suffix(".json")
        data_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.parent.mkdir(parents=True, exist_ok=True)

        torch.save(data, data_path)
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        manifest.append({
            "graph_id": graph_id,
            "label": label,
            "num_nodes": metadata["num_nodes"],
            "num_edges": metadata["num_edges"],
            "data_path": str(data_path),
            "metadata_path": str(meta_path),
        })

        print(f"Nodes : {metadata['num_nodes']}  Edges : {metadata['num_edges']}  Label : {label}")
        success += 1

    except Exception as e:
        print("FAILED")
        print(e)
        failed += 1

with open(FEATURES_ROOT / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

print("\n" + "=" * 70)
print("Feature extraction complete")
print(f"Successful : {success}")
print(f"Failed     : {failed}")
print(f"Manifest   : {FEATURES_ROOT / 'manifest.json'}")
print("=" * 70)