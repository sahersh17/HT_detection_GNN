"""Run: python -m unittest discover -s tests   (from the pipeline folder). stdlib only."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "localization"))

import metrics
import rtl_diff
import label_nodes
import eval_loc


class MetricsTest(unittest.TestCase):
    def test_matches_known_notebook_numbers(self):
        # pooled RTL-only result from the notebook: TN=26 FP=0 FN=6 TP=20
        y = [0] * 26 + [1] * 26
        p = [0] * 26 + [0] * 6 + [1] * 20
        s = metrics.summarize(y, p)
        self.assertAlmostEqual(s["accuracy"], 46 / 52)
        self.assertAlmostEqual(s["macro_f1"], 0.8831, places=3)
        self.assertEqual((s["fp"], s["fn"]), (0, 6))

    def test_auroc(self):
        self.assertEqual(metrics.auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]), 1.0)
        self.assertEqual(metrics.auroc([0, 1], [0.5, 0.5]), 0.5)
        self.assertIsNone(metrics.auroc([1, 1], [0.1, 0.2]))


class DiffTest(unittest.TestCase):
    def test_finds_inserted_trojan_lines_and_new_identifiers(self):
        with tempfile.TemporaryDirectory() as d:
            c, t = Path(d, "clean"), Path(d, "troj")
            c.mkdir(); t.mkdir()
            (c / "aes.v").write_text("module aes(clk);\n  reg [3:0] round;\n  // note\nendmodule\n")
            (t / "aes.v").write_text("module aes(clk);\n  reg [3:0] round;\n  reg [15:0] trojan_counter;\n"
                                     "  // changed comment\nendmodule\n")
            (t / "test_aes.v").write_text("module tb; endmodule\n")
            lines, texts = rtl_diff.trojan_lines(c, t)
            self.assertEqual(lines, {"aes.v": [3]})
            self.assertEqual(rtl_diff.new_identifiers(c, t, texts), ["trojan_counter"])


class LabelTest(unittest.TestCase):
    def test_src_and_name_evidence(self):
        j = {"modules": {"top": {"attributes": {"top": 1}, "cells": {
            "c1": {"attributes": {"src": "aes.v:3.3-3.20"}},
            "c2": {"attributes": {"src": "aes.v:9.1-9.5"}},
            "trojan_counter_reg": {"attributes": {}},
        }}}}
        diff = {"lines": {"aes.v": [3]}, "new_identifiers": ["trojan_counter"]}
        out = label_nodes.label(j, diff)
        self.assertEqual(out["nodes"], {"c1": 1, "c2": 0, "trojan_counter_reg": 1})
        self.assertEqual(out["coverage"]["trojan_by_name_only"], 1)

    def test_multi_range_src(self):
        self.assertEqual(label_nodes.src_ranges("a/b.v:12.3-14.5|c.v:7.1-7.9"), [("b.v", 12, 14), ("c.v", 7, 7)])


class LocEvalTest(unittest.TestCase):
    def test_perfect_and_random_reference(self):
        gt = [0, 0, 1, 1, 0, 0, 0, 0, 0, 0]
        r = eval_loc.evaluate([0.1, 0.1, 0.9, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1], gt)
        self.assertEqual(r["precision_at_|GT|"], 1.0)
        self.assertEqual(r["iou_at_|GT|"], 1.0)
        self.assertEqual(r["first_trojan_rank"], 1)
        self.assertAlmostEqual(r["random_precision"], 0.2)
        self.assertIsNone(eval_loc.evaluate([0.5] * 3, [0, 0, 0]))


if __name__ == "__main__":
    unittest.main()
