from pathlib import Path
from graph_builder import GraphBuilder

# ============================================================
# CONFIG
# ============================================================

PARSED_ROOT = Path(r"C:\HT_detection_GNN\trusthub\parsed")
GRAPH_ROOT = Path(r"C:\HT_detection_GNN\trusthub\graphs")

GRAPH_ROOT.mkdir(parents=True, exist_ok=True)

builder = GraphBuilder()

success = 0
failed = 0

print("=" * 70)
print("Building Graphs")
print("=" * 70)

# ============================================================
# BUILD GRAPH FOR EVERY JSON
# ============================================================

json_files = sorted(PARSED_ROOT.rglob("*.json"))

print(f"\nFound {len(json_files)} parsed netlists\n")

for json_file in json_files:

    print("-" * 70)
    print(json_file.relative_to(PARSED_ROOT))

    try:

        graph = builder.build(json_file)

        # ----------------------------------------------------
        # Output paths
        # ----------------------------------------------------

        relative = json_file.relative_to(PARSED_ROOT)

        graphml_path = (GRAPH_ROOT / relative).with_suffix(".graphml")
        gpickle_path = (GRAPH_ROOT / relative).with_suffix(".gpickle")

        graphml_path.parent.mkdir(parents=True, exist_ok=True)

        # ----------------------------------------------------
        # Save graph
        # ----------------------------------------------------

        builder.save_graphml(graph, graphml_path)
        builder.save_gpickle(graph, gpickle_path)

        print(f"Nodes : {graph.number_of_nodes()}")
        print(f"Edges : {graph.number_of_edges()}")

        success += 1

    except Exception as e:

        print("FAILED")
        print(e)

        failed += 1

# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("Finished")
print(f"Successful : {success}")
print(f"Failed     : {failed}")
print("=" * 70)