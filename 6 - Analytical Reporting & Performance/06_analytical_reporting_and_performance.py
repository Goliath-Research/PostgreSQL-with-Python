import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import duckdb
    import marimo as mo
    from statistics import median
    from time import perf_counter
    return duckdb, median, mo, perf_counter


@app.cell
def _(duckdb, median, perf_counter):
    def report(con, size):
        if type(size) is not int or not 1 <= size <= 100_000:
            raise ValueError("size must be an integer from 1 to 100000")
        return con.sql(f"""
            WITH lines AS (
                SELECT i AS line_id, i % 8 AS category_id,
                       (i % 5 + 1) * (100 + i % 900) AS line_cents
                FROM range({size}) AS r(i)
            )
            SELECT *, CAST(sum(line_cents) OVER (
                PARTITION BY category_id ORDER BY line_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS BIGINT) AS running_cents,
            dense_rank() OVER (
                PARTITION BY category_id ORDER BY line_cents DESC
            ) AS revenue_rank
            FROM lines ORDER BY category_id, line_id
        """)

    def benchmark(size):
        with duckdb.connect(":memory:") as con:
            relation = report(con, size)
            methods = {"pandas": relation.df, "Arrow table": relation.fetch_arrow_table}
            timings = {name: [] for name in methods}
            for materialize in methods.values():
                materialize()
            for repeat in range(6):
                names = list(methods)
                for name in (names if repeat % 2 == 0 else names[::-1]):
                    start = perf_counter()
                    result = methods[name]()
                    timings[name].append((perf_counter() - start) * 1000)
                    count = len(result) if name == "pandas" else result.num_rows
                    if count != size:
                        raise RuntimeError("Unexpected row count")
                    del result
            return [dict(format=name, rows=size, median_ms=round(median(samples), 3),
                         min_ms=round(min(samples), 3), max_ms=round(max(samples), 3))
                    for name, samples in timings.items()]

    return benchmark, report


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Module 6: Analytical Reporting & Performance
    Each row is a synthetic order line. A running total preserves that grain
    while accumulating cents within each category. Dense rank gives equal
    amounts the same rank and leaves no gaps. Rank order and report order differ.
    """)
    return


@app.cell
def _(mo):
    bench_form = mo.ui.dropdown({"1,000": 1000, "10,000": 10000,
                                 "100,000": 100000}, value="10,000").form()
    bench_form
    return (bench_form,)


@app.cell
def _(bench_form, benchmark, mo):
    mo.stop(bench_form.value is None, mo.md("Submit a row count to benchmark."))
    mo.ui.table(benchmark(bench_form.value))
    return


@app.cell
def _(duckdb, mo, report):
    with duckdb.connect(":memory:") as _con:
        _frame = report(_con, 64).df()
        _csv = _frame.to_csv(index=False).encode("utf-8")
        _parquet = _frame.to_parquet(index=False, engine="pyarrow")
    mo.vstack([
        mo.md("### Fixed 64-row report sample and exports"),
        mo.ui.table(_frame),
        mo.download(data=_csv, filename="module06-report.csv", mimetype="text/csv", label="Download CSV"),
        mo.download(data=_parquet, filename="module06-report.parquet", mimetype="application/octet-stream", label="Download Parquet"),
    ])
    return


if __name__ == "__main__":
    app.run()
