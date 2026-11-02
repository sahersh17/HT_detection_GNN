"""Regression checks for header directives and Verilog lexical boundaries."""
import unittest

from prepare import transform


class LexicalControlsTest(unittest.TestCase):
    def test_preserves_includes_literals_and_strings(self):
        source = ('`include "inc.h"\nmodule uart; // benchmark clue\n'
                  'parameter LO = 1\'b0; wire state; assign state = LO;\n'
                  '$display("state LO"); endmodule\n')
        changed, comments, renamed = transform(source, True, True)
        self.assertEqual(len(source), len(changed))
        self.assertEqual(source.count("\n"), changed.count("\n"))
        self.assertIn('`include "inc.h"', changed)
        self.assertIn("module hneg", changed)
        self.assertIn("parameter YB", changed)
        self.assertIn("1'b0", changed)
        self.assertIn('"state LO"', changed)
        self.assertNotIn("benchmark clue", changed)
        self.assertEqual(comments, 1)
        self.assertGreater(renamed, 0)

    def test_preserves_macro_directive(self):
        source = '`define DEBUG\nmodule uart; endmodule\n'
        changed, _, _ = transform(source, False, True)
        self.assertTrue(changed.startswith('`define DEBUG\n'))


if __name__ == "__main__":
    unittest.main()
