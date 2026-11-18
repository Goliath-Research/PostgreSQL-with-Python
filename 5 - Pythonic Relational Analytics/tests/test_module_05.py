import ast
from pathlib import Path
import unittest
import duckdb

# Run the notebook's lab functions without importing or starting Marimo.
path = Path(__file__).resolve().parents[1] / "05_pythonic_relational_analytics.py"
cell = next(node for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, ast.FunctionDef) and any(
                isinstance(item, ast.FunctionDef) and item.name == "build_lab"
                for item in node.body))
namespace = {"duckdb": duckdb}
exec(compile(ast.Module(body=[node for node in cell.body if isinstance(node, ast.FunctionDef)],
                        type_ignores=[]), str(path), "exec"), namespace)
run_lab = namespace["inspect_and_fetch"]


class AnalyticsTests(unittest.TestCase):
    def test_sql_only(self):
        sql, before, after = run_lab(2, False)
        for clause in ("JOIN", "WHERE", "GROUP BY"):
            self.assertIn(clause, sql.upper())
        self.assertIsNone(before)
        self.assertIsNone(after)

    def test_grouped_totals_and_refetch(self):
        _, before, after = run_lab(2, True)
        self.assertEqual(before, [("Books", 2, 5, 1600), ("Games", 1, 2, 2000)])
        self.assertEqual(after, [("Books", 2, 5, 1600), ("Games", 2, 7, 7000)])

    def test_empty_first_fetch(self):
        _, before, after = run_lab(5, True)
        self.assertEqual(before, [])
        self.assertEqual(after, [("Games", 1, 5, 5000)])

    def test_invalid_threshold(self):
        with self.assertRaises(ValueError):
            run_lab("2 OR 1=1", False)
