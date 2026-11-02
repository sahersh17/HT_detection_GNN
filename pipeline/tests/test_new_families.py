"""Regression checks for mapped library interfaces and VHDL compatibility."""
import sys
import unittest
from types import SimpleNamespace
import torch
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "provenance"))
from synth_gate_netlists import cell_ports, stubs_for
from embed_new_vhdl import cached_embed


class GateInterfaceTests(unittest.TestCase):
    def test_window_cache_preserves_order_and_masked_pooling(self):
        def tokenizer(text, **kwargs):
            return {"input_ids": [[2, 4, 99], [8, 6, 99], [2, 4, 99]],
                    "attention_mask": [[1, 1, 0]] * 3,
                    "offset_mapping": [[(0, 1), (1, 2), (0, 0)]] * 3}
        class Model:
            calls = 0
            def __call__(self, input_ids, attention_mask):
                self.calls += 1
                return SimpleNamespace(last_hidden_state=input_ids.float().unsqueeze(-1))
        model, windows = Model(), {}
        first = cached_embed("a", tokenizer, model, windows)
        second = cached_embed("a", tokenizer, model, windows)
        self.assertEqual(first[0].flatten().tolist(), [3.0, 7.0, 3.0])
        self.assertTrue(torch.equal(first[0], second[0]))
        self.assertEqual(model.calls, 1)

    def test_unused_output_union_and_adder_mux_directions(self):
        source = """module top(input x, output y);
FADDX1 a (.A(x), .B(x), .CI(x), .S(y), .CO(z));
FADDX1 b (.A(x), .B(x), .CI(x), .CO(q));
MUX21X1 c (.IN1(x), .IN2(x), .S(x), .Q(y));
endmodule
"""
        self.assertEqual(cell_ports(source)["FADDX1"], {"A", "B", "CI", "S", "CO"})
        class Source:
            def read_text(self, **kwargs):
                return source
        with patch("synth_gate_netlists.source_path", return_value=Source()):
            stubs, _ = stubs_for("b15-T100")
        adder, mux = stubs.splitlines()
        self.assertIn("output S", adder)
        self.assertIn("input S", mux)
        self.assertIn("output Q", mux)

    def test_unknown_output_convention_fails_closed(self):
        class Source:
            def read_text(self, **kwargs):
                return "module top();\nUNKNOWN a (.A(x), .UNRECOGNIZED(y));\nendmodule"
        with patch("synth_gate_netlists.source_path", return_value=Source()):
            with self.assertRaisesRegex(ValueError, "Unclassified cell ports"):
                stubs_for("b15-T100")


if __name__ == "__main__":
    unittest.main()
