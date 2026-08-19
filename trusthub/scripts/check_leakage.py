from pathlib import Path
import json
from collections import defaultdict

# ==========================================================
# CONFIG
# ==========================================================

METADATA_ROOT = Path(r"C:\HT_detection_GNN\trusthub\features\metadata")
MANIFEST_PATH = Path(r"C:\HT_detection_GNN\trusthub\features\manifest.json")

SUSPICIOUS_NAME_SUBSTRINGS = ["trojan", "tsc", "trigger", "malicious", "backdoor"]

# ==========================================================
# LOAD MANIFEST
# ==========================================================

with open(MANIFEST_PATH, "r") as f:
    manifest = json.load(f)

print(f"Checking {len(manifest)} graphs for leakage\n")

# ==========================================================
# CHECK 1 — gate types that appear in only one label class
# ==========================================================

# gate_type -> {0: set(graph_ids), 1: set(graph_ids)}
type_presence = defaultdict(lambda: {0: set(), 1: set()})

# ==========================================================
# CHECK 2 — suspicious substrings in node names
# ==========================================================

name_hits = []  # (graph_id, label, substring, [example node names])

# ==========================================================
# CHECK 3 — node/edge count separability by label
# ==========================================================

counts_by_label = defaultdict(list)  # label -> [(num_nodes, num_edges), ...]

# ==========================================================
# WALK ALL METADATA
# ==========================================================

for entry in manifest:
    graph_id = entry["graph_id"]
    label = entry["label"]

    if label not in (0, 1):
        continue  # skip any leftover -1s if present

    meta_path = Path(entry["metadata_path"])
    with open(meta_path, "r") as f:
        meta = json.load(f)

    # ---- Check 1 ----
    for gt in set(meta["node_gate_classes"]):   # was: meta["node_types"]
        type_presence[gt][label].add(graph_id)

    # ---- Check 2 ----
    lower_names = [(n, n.lower()) for n in meta["node_names"]]
    for substr in SUSPICIOUS_NAME_SUBSTRINGS:
        matches = [orig for orig, low in lower_names if substr in low]
        if matches:
            name_hits.append((graph_id, label, substr, matches[:5]))  # cap examples shown

    # ---- Check 3 ----
    counts_by_label[label].append((meta["num_nodes"], meta["num_edges"]))

# ==========================================================
# REPORT — CHECK 1
# ==========================================================

print("=" * 70)
print("CHECK 1 — Gate types present in only one label class")
print("=" * 70)

leaky_types = []
for gt, presence in sorted(type_presence.items()):
    only_0 = presence[0] and not presence[1]
    only_1 = presence[1] and not presence[0]
    if only_0 or only_1:
        leaky_types.append((gt, presence))

if not leaky_types:
    print("None found — every gate type appears in both classes.\n")
else:
    for gt, presence in leaky_types:
        only_label = 0 if presence[0] else 1
        graphs = presence[only_label]
        print(f"  '{gt}'  -> ONLY in label {only_label}  ({len(graphs)} graph(s))")
        for g in sorted(graphs)[:5]:
            print(f"       {g}")
        if len(graphs) > 5:
            print(f"       ... and {len(graphs) - 5} more")
    print(f"\n  {len(leaky_types)} potentially leaky gate type(s) found. "
          f"Consider excluding or investigating these before training.\n")

# ==========================================================
# REPORT — CHECK 2
# ==========================================================

print("=" * 70)
print("CHECK 2 — Suspicious substrings in node names")
print("=" * 70)

if not name_hits:
    print("None found.\n")
else:
    by_label = defaultdict(int)
    for graph_id, label, substr, examples in name_hits:
        by_label[label] += 1
        print(f"  {graph_id}  label={label}  substring='{substr}'")
        for ex in examples:
            print(f"       {ex}")

    print(f"\n  Hits by label: {dict(by_label)}")
    if 0 not in by_label or by_label.get(0, 0) == 0:
        print("  -> All hits are in label 1 only. This is a strong name-based leak signal —")
        print("     though note: your current feature vector (gate_type + degree) does NOT")
        print("     encode node names, so the GNN itself can't exploit this directly.")
        print("     This matters more if node names ever get used as/alongside features later.\n")
    else:
        print()

# ==========================================================
# REPORT — CHECK 3
# ==========================================================

print("=" * 70)
print("CHECK 3 — Node/edge count separability by label")
print("=" * 70)

for label, vals in sorted(counts_by_label.items()):
    nodes = [v[0] for v in vals]
    edges = [v[1] for v in vals]
    print(f"  Label {label}  (n={len(vals)}):")
    print(f"    nodes  min={min(nodes)}  max={max(nodes)}  avg={sum(nodes)/len(nodes):.1f}")
    print(f"    edges  min={min(edges)}  max={max(edges)}  avg={sum(edges)/len(edges):.1f}")

if len(counts_by_label) == 2:
    max0 = max(v[0] for v in counts_by_label[0])
    min1 = min(v[0] for v in counts_by_label[1])
    max1 = max(v[0] for v in counts_by_label[1])
    min0 = min(v[0] for v in counts_by_label[0])
    if max0 < min1 or max1 < min0:
        print("\n  WARNING: node counts for the two labels don't overlap at all.")
        print("  A trivial 'count the nodes' rule would perfectly separate your classes.")
        print("  This is expected to some degree (Trojans add gates), but total separability")
        print("  is worth being aware of when interpreting your GNN's accuracy later.")

print("\n" + "=" * 70)
print("Leakage check complete")
print("=" * 70)