"""Small semantic and tensor checks for the experimental representation."""
import unittest

import torch
from torch_geometric.data import Data

from model import TypedFusion, training_loss
from prepare import EDGE_DIM, NODE_DIM, alignment, graph_view, rtl_features
from calibrate import choose_threshold


class TypedPipelineTest(unittest.TestCase):
    def setUp(self):
        self.document = {"modules": {"top": {"ports": {
            "in": {"direction": "input", "bits": [2]},
            "clk": {"direction": "input", "bits": [4]},
            "out": {"direction": "output", "bits": [5]},
        }, "cells": {
            "and": {"type": "$_AND_", "port_directions": {"A": "input", "B": "input", "Y": "output"},
                    "connections": {"A": [2], "B": ["1"], "Y": [3]}},
            "ff": {"type": "$_DFF_P_", "port_directions": {"D": "input", "C": "input", "Q": "output"},
                   "connections": {"D": [3], "C": [4], "Q": [5]}},
        }}}}
        self.metadata = {"top": "top", "graph_id": "tiny", "node_names": ["and", "ff"],
                         "source_ranges": [[("a.v", 1, 2)], [("a.v", 4, 5)]]}
        x = torch.zeros((2, 20)); x[0, 0] = 1; x[1, 4] = 1
        self.base = Data(x=x, edge_index=torch.tensor([[0], [1]]), y=torch.tensor([1]))
        self.base.graph_id = "tiny"

    def test_graph_roles_and_clock(self):
        graph = graph_view(self.document, self.metadata, self.base)
        self.assertEqual(graph.x.shape, (7, NODE_DIM))
        self.assertEqual(graph.edge_attr.shape, (10, EDGE_DIM))
        self.assertEqual(graph.n_cell, 2)
        self.assertEqual(int(graph.x[3, 21]), 1)  # primary input
        self.assertEqual(int(graph.x[4, 22]), 1)  # real output
        self.assertEqual(int(graph.x[6, 24]), 1)  # constant one
        self.assertGreater(float(graph.x[1, 29]), 0)  # clock pin fraction
        self.assertGreater(float(graph.x[1, 28]), 0)  # real-output fraction

    def test_rtl_features_ignore_names_and_comments(self):
        a = rtl_features("// secret\n always @(posedge clk) if (foo == 8'h01) bar <= foo;")
        b = rtl_features("// benign\n always @(posedge clk) if (renamed == 8'h01) other <= renamed;")
        self.assertTrue(torch.equal(a, b))

    def test_alignment_and_fusion_backward(self):
        record = {"chunks": [
            {"chunk": 0, "source_spans": [{"file": "rtl/a.v", "start_line": 1, "end_line": 2}]},
            {"chunk": 1, "source_spans": [{"file": "rtl/a.v", "start_line": 4, "end_line": 5}]},
        ]}
        links, weights = alignment(self.metadata, record)
        self.assertEqual(links.tolist(), [[0, 1], [0, 1]])
        graph = graph_view(self.document, self.metadata, self.base)
        item = {"graph": graph, "rtl": torch.randn(2, 768), "struct": torch.randn(2, 16),
                "links": links, "weights": weights}
        net = TypedFusion(hidden=24)
        for arm in ("graph", "rtl", "structured", "fusion"):
            out = net(item, arm)
            self.assertTrue(torch.isfinite(out["logit"]))
            loss = training_loss(out, 1, arm)
            loss.backward()
            net.zero_grad(set_to_none=True)
        self.assertEqual(len(net(item, "fusion")["region_logits"]), 2)

    def test_training_threshold_is_between_separated_classes(self):
        threshold, balanced = choose_threshold([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])
        self.assertEqual(threshold, 0.5)
        self.assertEqual(balanced, 1.0)


if __name__ == "__main__":
    unittest.main()
