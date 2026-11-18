# Module 6 — Analytical Reporting & Performance

Use your course virtual environment with DuckDB, Marimo, pandas and pyarrow installed. No PostgreSQL connection, credentials or extension are required. The report uses deterministic synthetic order lines, not production data.

From the clone root in PowerShell:

```powershell
python -m marimo check "6 - Analytical Reporting & Performance/06_analytical_reporting_and_performance.py"
python -m marimo edit "6 - Analytical Reporting & Performance/06_analytical_reporting_and_performance.py"
python -m unittest discover -s "6 - Analytical Reporting & Performance/tests" -v
```

## 1. Read the windows

`PARTITION BY category_id` restarts each calculation for each category. The explicit `ROWS` frame includes all earlier lines and the current line in `line_id` order. Category 0 starts with line 0 (100 cents), then line 8 (432 cents), with running totals 100 and 532. `DENSE_RANK()` instead orders amounts highest-first within a category. Tied amounts share a rank without gaps. The final `ORDER BY` controls display, not rank.

## 2. Cross the materialization boundary

`report()` returns a relation; `.df()` executes it and produces a pandas DataFrame, while `.fetch_arrow_table()` executes it and produces an Arrow table. Both methods materialize the full result in this exercise; this is not a streaming comparison.

## 3. Export and verify

Download the 64-row sample as CSV or Parquet. CSV is text and readers infer or supply types; Parquet carries a schema. Open both in DuckDB with `read_csv_auto` and `read_parquet` and compare their row counts and `sum(line_cents)`. The download size stays fixed when you change benchmark size.

## 4. Measure before drawing conclusions

Submit 1,000, 10,000, and 100,000 rows in turn. Each comparison warms both methods once, alternates which goes first, and records six timings per format. Compare median and range. Timings include query execution plus conversion; they do not isolate conversion or measure export time, network transfer, or peak memory. Repeat a run if the ranges overlap. Do not treat this fixture as evidence of a universal winner.

Practice: change the window frame to `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`. Predict which rows will differ first, then verify the result.
