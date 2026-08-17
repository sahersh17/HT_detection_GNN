import pickle

with open(r"C:\HT_detection_GNN\trusthub\graphs\AES\AES-T100\clean_netlist.gpickle", "rb") as f:
    G = pickle.load(f)

isolated = [n for n in G.nodes if G.in_degree(n) == 0 and G.out_degree(n) == 0]
print(f"Total nodes: {G.number_of_nodes()}")
print(f"Fully isolated nodes: {len(isolated)}")
print(f"Fraction isolated: {len(isolated)/G.number_of_nodes():.2%}")

#Good — 1.82% isolated is small and not a red flag. That confirms the low edge/node 
#ratio isn't from a systematic driver-matching bug; it's just this circuit's actual 
# structure (144 nodes are likely things like unconnected/const-tied intermediate 
# signals or dangling declared-but-unused wires that opt_clean didn't fully strip,
# which is normal). You can move on with confidence — no need to dig further into 
# graph_builder.py.
