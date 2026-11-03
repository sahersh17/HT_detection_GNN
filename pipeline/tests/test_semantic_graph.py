"""Semantic graph regression tests for constants, memory state and bit ordering."""
import copy
import sys
import unittest
from collections import Counter
from pathlib import Path

import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"provenance"))
from build import graph_from_json
from semantic import decode_vector, semantic_graph_from_json, verify_semantic_values, NODE_DIM, VALUE_START


def memory_design(data="0010"):
    return {"modules":{"top":{
        "ports":{"q":{"direction":"output","bits":[10,11]}},
        "memories":{"m":{"width":2,"size":2,"start_offset":-1}},
        "cells":{
            "initialize":{"type":"$meminit","port_directions":{"ADDR":"input","DATA":"input"},
                "connections":{"ADDR":["0"],"DATA":list(reversed(data))},
                "parameters":{"MEMID":"m","WIDTH":"10","WORDS":"10"}},
            "read":{"type":"$memrd_v2","port_directions":{"ADDR":"input","DATA":"output"},
                "connections":{"ADDR":["0"],"DATA":[10,11]},
                "parameters":{"MEMID":"m","INIT_VALUE":"xz","WIDTH":"10"}}
        }}}}


def histogram(graph):
    return Counter(tuple(row) for row in graph.x.tolist())


class SemanticGraphTests(unittest.TestCase):
    def test_memory_flip_survives_features_and_binds_state(self):
        left,right=memory_design("0010"),memory_design("0000")
        a,_=graph_from_json(left,"top","id",0)
        b,_=graph_from_json(right,"top","id",0)
        self.assertTrue(torch.equal(a.x,b.x))
        self.assertTrue(torch.equal(a.edge_index,b.edge_index))
        a,meta=semantic_graph_from_json(left,"top","id",0)
        b,_=semantic_graph_from_json(right,"top","id",0)
        self.assertNotEqual(histogram(a),histogram(b))
        self.assertEqual(len(meta["memory_nodes"]),1)
        self.assertEqual(len({r["memory"] for r in meta["memory_bindings"]}),1)
        edge_set=set(map(tuple,a.edge_index.T.tolist()))
        for row in meta["memory_bindings"]:
            self.assertIn((row["cell"],row["memory"]),edge_set)

    def test_bit_swap_same_population_remains_distinct(self):
        a,_=semantic_graph_from_json(memory_design("0010"),"top","id",0)
        b,_=semantic_graph_from_json(memory_design("0100"),"top","id",0)
        self.assertNotEqual(histogram(a),histogram(b))

    def test_roundtrip_parameters_direction_and_four_states(self):
        document=memory_design("01xz")
        graph,meta=semantic_graph_from_json(document,"top","id",0)
        for row in meta["vectors"]:
            if row["kind"]=="parameter":
                cell=meta["node_names"][row["owner"]]
                self.assertEqual(decode_vector(graph,row),
                                 document["modules"]["top"]["cells"][cell]["parameters"][row["name"]])
            elif row["kind"]=="memory_field":
                self.assertEqual(decode_vector(graph,row),
                                 document["modules"]["top"]["memories"]["m"][row["name"]])
            else:
                source=(document["modules"]["top"]["cells"][meta["node_names"][row["owner"]]]["connections"][row["name"]]
                        if row["owner"]<graph.n_cell else document["modules"]["top"]["ports"][row["name"]]["bits"])
                expected=[v if isinstance(v,str) else None for v in source]
                self.assertEqual(decode_vector(graph,row),expected)

    def test_constant_only_design_and_net_initial_state(self):
        document={"modules":{"top":{"cells":{},"ports":{"q":{"direction":"output","bits":["0","1","x","z"]}},
                                    "netnames":{"state":{"bits":[7],"attributes":{"init":"1"}}}}}}
        graph,meta=graph_from_json(document,"top","id",0,representation="semantic_v1")
        self.assertEqual(graph.x.shape[1],NODE_DIM)
        self.assertEqual(graph.n_cell,0)
        self.assertEqual(len(meta["initial_bits"]),1)
        self.assertEqual(decode_vector(graph,meta["vectors"][0]),["0","1","x","z"])

    def test_names_ids_labels_and_permutation_do_not_create_difference(self):
        original=memory_design()
        renamed=copy.deepcopy(original)
        module=renamed["modules"]["top"]
        module["cells"]={f"changed_{i}":v for i,v in enumerate(reversed(list(module["cells"].values())))}
        module["memories"]["other"]=module["memories"].pop("m")
        for cell in module["cells"].values():
            cell["parameters"]["MEMID"]="other"
        a,_=semantic_graph_from_json(original,"top","first",0)
        b,_=semantic_graph_from_json(renamed,"top","second",1)
        self.assertEqual(histogram(a),histogram(b))
        torch.manual_seed(4)
        permutation=torch.randperm(a.num_nodes)
        self.assertEqual(histogram(a),Counter(tuple(row) for row in a.x[permutation].tolist()))

    def test_fail_closed_on_unsupported_parameters(self):
        document=memory_design()
        document["modules"]["top"]["cells"]["read"]["parameters"]["INIT_VALUE"]="not-bits"
        with self.assertRaisesRegex(ValueError,"Unsupported semantic parameter"):
            semantic_graph_from_json(document,"top","id",0)

    def test_initialization_attributes_and_escaped_memory_binding(self):
        document=memory_design()
        module=document["modules"]["top"]
        module["cells"]["read"]["parameters"]["MEMID"]="\\m"
        module["cells"]["read"]["attributes"]={"init":"xz"}
        module["memories"]["m"]["attributes"]={"init":"01xz"}
        graph,metadata=semantic_graph_from_json(document,"top","id",0)
        checked=verify_semantic_values(document,"top",graph,metadata)
        self.assertEqual(checked["memory_states"],1)
        self.assertTrue(any(r["kind"]=="cell_initial" for r in metadata["vectors"]))

    def test_value_checker_rejects_a_lost_constant(self):
        document=memory_design()
        graph,metadata=semantic_graph_from_json(document,"top","id",0)
        record=next(r for r in metadata["vectors"] if r["kind"]=="connection" and r["name"]=="DATA"
                    and r["owner"]==0)
        node=record["bit_nodes"][0]
        graph.x[node,VALUE_START:VALUE_START+4]=torch.tensor([0.,1.,0.,0.])
        with self.assertRaisesRegex(ValueError,"Constant connection bit mismatch"):
            verify_semantic_values(document,"top",graph,metadata)


if __name__=="__main__":
    unittest.main()
