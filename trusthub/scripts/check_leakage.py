import json
from pathlib import Path
from collections import Counter

METADATA_ROOT = Path(r"C:\HT_detection_GNN\trusthub\features\metadata")

counts = Counter()
examples = {0: [], 1: []}

for meta_file in sorted(METADATA_ROOT.rglob("*.json")):
    with open(meta_file, encoding="utf-8") as f:
        data = json.load(f)

    label = data.get("label")

    if "$print" in data.get("node_types", []):
        counts[label] += 1

        if len(examples[label]) < 10:
            examples[label].append(
                str(meta_file.relative_to(METADATA_ROOT))
            )

print("\n$print occurrence by label:")
print(f"Label 0: {counts[0]}")
print(f"Label 1: {counts[1]}")

print("\nExamples:")
for label in [0, 1]:
    print(f"\nLabel {label}:")
    for example in examples[label]:
        print(f"  {example}")

print("\nTotal metadata files:")
print(sum(1 for _ in METADATA_ROOT.rglob("*.json")))