"""Regression checks for omitted sequential cells and bit-level edges."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'provenance'))
from build import graph_from_json
from audit_completeness import audit

class CompletenessTest(unittest.TestCase):
    def setUp(self):
        self.document = {'modules': {'top': {'ports': {'clk': {'direction':'input','bits':[2]}, 'din': {'direction':'input','bits':[1]}}, 'cells': {
            'state_reg': {'type':'$_DFF_P_', 'port_directions':{'C':'input','D':'input','Q':'output'}, 'connections':{'C':[2],'D':[1],'Q':[3]}},
            'out_gate': {'type':'$_NOT_', 'port_directions':{'A':'input','Y':'output'}, 'connections':{'A':[3],'Y':[4]}}
        }}}}
        self.graph,self.meta=graph_from_json(self.document,'top','test/top',0)
        self.meta['top']='top'

    def test_preserves_flipflop_and_its_output_edge(self):
        result=audit(self.document,self.meta,self.graph)
        self.assertEqual(result['sequential_cells'],1)
        self.assertEqual(result['edges'],1)
        self.assertEqual(result['undriven_internal_bits'],[])

    def test_rejects_cell_omitted_by_parser(self):
        reduced=copy.deepcopy(self.document)
        del reduced['modules']['top']['cells']['state_reg']
        graph,meta=graph_from_json(reduced,'top','test/top',0)
        meta['top']='top'
        with self.assertRaisesRegex(ValueError,'exactly the synthesized'):
            audit(self.document,meta,graph)

    def test_rejects_missing_wire_connection(self):
        self.graph.edge_index=self.graph.edge_index[:,:0]
        with self.assertRaisesRegex(ValueError,'Connectivity mismatch'):
            audit(self.document,self.meta,self.graph)

    def test_rejects_lost_sequential_feature(self):
        self.graph.x[:,4]=0
        with self.assertRaisesRegex(ValueError,'Sequential cells'):
            audit(self.document,self.meta,self.graph)
