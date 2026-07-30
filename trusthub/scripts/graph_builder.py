from pathlib import Path
import json
import networkx as nx
import pickle


class GraphBuilder:

    def __init__(self):
        pass

    # ----------------------------------------------------
    # Build graph from parsed JSON
    # ----------------------------------------------------
    def build(self, json_file):

        json_file = Path(json_file)

        with open(json_file, "r") as f:
            data = json.load(f)

        G = nx.DiGraph()

        gates = data["gates"]

        # ---------------------------------------------
        # Step 1 : Add every gate as a node
        # ---------------------------------------------

        for gate in gates:

            G.add_node(
                gate["name"],
                gate_type=gate["type"],
                ports=json.dumps(gate["ports"])
            )

        # ---------------------------------------------
        # Step 2 : Find drivers
        # ---------------------------------------------

        #
        # net -> gate
        #

        drivers = {}

        output_ports = {
            "Y",
            "Q",
            "QN",
            "Z",
            "ZN",
            "OUT",
            "O"
        }

        for gate in gates:

            for port, signal in gate["ports"].items():

                if port.upper() in output_ports:

                    drivers[signal] = gate["name"]

        # ---------------------------------------------
        # Step 3 : Connect consumers
        # ---------------------------------------------

        for gate in gates:

            for port, signal in gate["ports"].items():

                if port.upper() in output_ports:
                    continue

                if signal not in drivers:
                    continue

                source = drivers[signal]
                target = gate["name"]

                if source != target:

                    G.add_edge(
                        source,
                        target,
                        signal=signal
                    )

        return G

    # ----------------------------------------------------
    # Save graph
    # ----------------------------------------------------

    def save_graphml(self, graph, filename):

        nx.write_graphml(graph, filename)

    def save_gpickle(self, graph, filename):

        with open(filename, "wb") as f:
            pickle.dump(graph, f)