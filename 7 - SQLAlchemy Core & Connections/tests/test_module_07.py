import ast
from pathlib import Path
import unittest
import sqlalchemy as sa

path = Path(__file__).resolve().parents[1] / "07_sqlalchemy_core_and_connections.py"
tree = ast.parse(path.read_text(encoding="utf8"))
function = next(f for cell in tree.body if isinstance(cell, ast.FunctionDef)
                for f in cell.body if isinstance(f, ast.FunctionDef) and f.name == "run_fixture")
ns = {"sa": sa}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), ns)


class CoreTests(unittest.TestCase):
    def test_commit_and_rollback(self):
        report = ns["run_fixture"](2)
        self.assertEqual(report["committed"], [{"id": 2, "quantity": 3}])
        self.assertEqual([r["id"] for r in report["inside_transaction"]], [2, 3])
        self.assertEqual(report["after_rollback"], report["committed"])

    def test_bound_parameter(self):
        first, second = [ns["run_fixture"](cutoff) for cutoff in (2, 5)]
        self.assertEqual(first["compiled_sql"], second["compiled_sql"])
        self.assertIn("?", second["compiled_sql"])
        self.assertEqual(second["bound_values"], {"minimum": 5})
        self.assertEqual(second["committed"], [])
        self.assertEqual(second["inside_transaction"], [{"id": 3, "quantity": 5}])
        self.assertEqual(second["after_rollback"], [])
