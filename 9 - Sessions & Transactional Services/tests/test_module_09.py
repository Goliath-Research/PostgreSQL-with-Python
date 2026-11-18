from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from module_09_services import run_lab


class ServiceTests(unittest.TestCase):
    def test_commit(self):
        outcome = run_lab()["transaction"]
        self.assertEqual(outcome["outcome"], "committed")
        self.assertTrue(outcome["persisted_attempt"])
        self.assertEqual(outcome["committed_id"], outcome["id_after_flush"])
        self.assertEqual((outcome["total_orders"], outcome["total_lines"]), (4, 5))

    def test_partial_flush_rolls_back_entire_order(self):
        outcome = run_lab(invalid=True)["transaction"]
        self.assertEqual(outcome["outcome"], "rolled back")
        self.assertEqual(outcome["lines_flushed"], 1)
        self.assertFalse(outcome["persisted_attempt"])
        self.assertEqual((outcome["total_orders"], outcome["total_lines"]), (3, 3))

    def test_loading(self):
        for invalid, expected in ((False, 5), (True, 4)):
            with self.subTest(invalid=invalid):
                report = run_lab(invalid)
                self.assertEqual(report["lazy"]["orders"], report["selectin"]["orders"])
                self.assertEqual(report["lazy"]["select_count"], expected)
                self.assertEqual(report["selectin"]["select_count"], 2)
