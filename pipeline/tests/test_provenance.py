"""Structural checks for the versioned Yosys JSON to graph conversion."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "provenance"))
from build import graph_from_json
from embed_rtl import line_spans


class ProvenanceGraphTest(unittest.TestCase):
    def test_chunk_offsets_cross_source_file_boundary(self):
        locations = [{"file": "a.v", "start": 0, "end": 5, "content": "a\nb\nc"},
                     {"file": "b.v", "start": 7, "end": 10, "content": "x\ny"}]
        spans = line_spans([(2, 3), (7, 8)], locations)
        self.assertEqual(spans, [{"file": "a.v", "start_line": 2, "end_line": 3},
                                 {"file": "b.v", "start_line": 1, "end_line": 1}])

    def test_edges_and_source_ranges_follow_exact_node_order(self):
        document = {"modules": {"top": {"cells": {
            "z_gate": {"type": "$_AND_", "port_directions": {"A": "input", "Y": "output"},
                       "connections": {"A": [5], "Y": [6]}, "attributes": {"src": "rtl.v:10.1-10.8"}},
            "a_gate": {"type": "$_NOT_", "port_directions": {"A": "input", "Y": "output"},
                       "connections": {"A": [1], "Y": [5]}, "attributes": {"src": "rtl.v:3.1-3.9"}},
            "meta": {"type": "$scopeinfo", "port_directions": {}, "connections": {}, "attributes": {}},
        }}}}
        graph, metadata = graph_from_json(document, "top", "test/top", 1)
        self.assertEqual(metadata["node_names"], ["a_gate", "z_gate"])
        self.assertEqual(graph.edge_index.tolist(), [[0], [1]])
        self.assertEqual(metadata["source_ranges"], [[("rtl.v", 3, 3)], [("rtl.v", 10, 10)]])
        self.assertEqual(graph.x.shape, (2, 20))
        self.assertEqual(metadata["source_covered_nodes"], 2)

    def test_rejects_ambiguous_gate_drivers(self):
        document = {"modules": {"top": {"cells": {
            name: {"type": "$_NOT_", "port_directions": {"Y": "output"},
                   "connections": {"Y": [7]}, "attributes": {}}
            for name in ("a", "b")}}}}
        with self.assertRaisesRegex(ValueError, "Multiple gate drivers"):
            graph_from_json(document, "top", "test/top", 0)


if __name__ == "__main__":
    unittest.main()
