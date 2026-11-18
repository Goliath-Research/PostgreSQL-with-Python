import ast
import importlib.util
from pathlib import Path
from statistics import median
from time import perf_counter
import unittest

import duckdb

path = Path(__file__).resolve().parents[1] / "06_analytical_reporting_and_performance.py"
# Exercise the exact lab functions without starting Marimo.
tree = ast.parse(path.read_text(encoding="utf-8"))
functions = [f for cell in tree.body if isinstance(cell, ast.FunctionDef)
             for f in cell.body if isinstance(f, ast.FunctionDef)]
ns = dict(duckdb=duckdb, median=median, perf_counter=perf_counter)
exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), ns)


class ReportTests(unittest.TestCase):
    def test_window(self):
        with duckdb.connect() as con:
            rows = ns["report"](con, 9).fetchall()
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[:2], [(0, 0, 100, 100, 2), (8, 0, 432, 532, 1)])

    def test_limits(self):
        with duckdb.connect() as con:
            for value in (0, 100001, True):
                with self.assertRaises(ValueError):
                    ns["report"](con, value)

    @unittest.skipUnless(importlib.util.find_spec("pandas"), "pandas unavailable")
    def test_csv(self):
        from io import StringIO
        import pandas as pd
        with duckdb.connect() as con:
            frame = ns["report"](con, 64).df()
        pd.testing.assert_frame_equal(frame, pd.read_csv(StringIO(frame.to_csv(index=False))), check_dtype=False)

    @unittest.skipUnless(all(importlib.util.find_spec(x) for x in ("pandas", "pyarrow")), "pandas or pyarrow unavailable")
    def test_arrow_parquet_and_benchmark(self):
        from io import BytesIO
        import pandas as pd
        with duckdb.connect() as con:
            relation = ns["report"](con, 64)
            frame = relation.df()
            pd.testing.assert_frame_equal(frame, relation.fetch_arrow_table().to_pandas())
        pd.testing.assert_frame_equal(frame, pd.read_parquet(BytesIO(frame.to_parquet(index=False, engine="pyarrow"))))
        timings = ns["benchmark"](64)
        self.assertEqual({(row["format"], row["rows"]) for row in timings}, {("pandas", 64), ("Arrow table", 64)})
