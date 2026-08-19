from pathlib import Path
import json
import networkx as nx
import pickle


class GraphBuilder:

    # Non-hardware cells that Yosys/synthesis can leave behind — these have
    # no circuit function and would otherwise become spurious graph nodes.
    DEBUG_CELL_TYPES = {"$print", "$display"}

    def __init__(self):
        pass

    def _is_debug_cell(self, gate_type):
        return gate_type.lstrip("\\") in self.DEBUG_CELL_TYPES

    # ----------------------------------------------------
    # Build graph from parsed JSON
    # ----------------------------------------------------
    def build(self, json_file):

        json_file = Path(json_file)

        with open(json_file, "r") as f:
            data = json.load(f)

        G = nx.DiGraph()

        # Filter out debug/simulation-only cells before anything else touches
        # them — they must never become nodes, drivers, or edge endpoints.
        gates = [g for g in data["gates"] if not self._is_debug_cell(g["type"])]

        # ---------------------------------------------
        # Step 1 : Add every real gate as a node
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