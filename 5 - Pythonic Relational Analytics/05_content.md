# Module 5: Pythonic Relational Analytics

Run from the repository root in your course virtual environment. DuckDB and Marimo are required. No credentials, extension installation, or persistent database is needed.

```powershell
python -m marimo check "5 - Pythonic Relational Analytics/05_pythonic_relational_analytics.py"
python -m marimo edit "5 - Pythonic Relational Analytics/05_pythonic_relational_analytics.py"
python -m unittest discover -s "5 - Pythonic Relational Analytics/tests" -v
```

## Follow the query

1. Filter order lines by minimum quantity (`WHERE`). At 2, three lines qualify.
2. Project the key and quantity plus a computed line total (`SELECT`). Keep money in integer cents.
3. Inner join to products by `product_id`. The primary key ensures each matching line is counted only once. An unmatched line would be excluded.
4. Group by category: count lines, sum units, and sum line totals. At 2, expect `('Books', 2, 5, 1600)` and `('Games', 1, 2, 2000)`, ordered by category. Line count is not order count.
5. Inspect `sql_query()` before fetching. Find the filter, join and grouping even if the generated SQL uses nested subqueries. This is query text, not a physical execution plan or evidence of PostgreSQL pushdown.
6. Enable fetching. `fetchall()` executes and returns Python rows. The lab inserts an eligible Games line and fetches the same relation again: Games becomes `('Games', 2, 7, 7000)`. The first Python result does not change. The fixture setup and insert are eager writes; lazy evaluation here describes the read relation, not every operation in the notebook.

## Practice

- Set the threshold to 3. Predict which category disappears on the first fetch and returns on the second.
- Add a filter after aggregation to keep groups with at least two line items. Explain how that differs from filtering input lines before grouping.
- Compare the generated query with a handwritten `SELECT ... JOIN ... WHERE ... GROUP BY ... ORDER BY`.

DuckDB documentation: [Relational API](https://duckdb.org/docs/stable/clients/python/relational_api.html).
