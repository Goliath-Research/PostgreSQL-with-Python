import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import duckdb
    import marimo as mo
    return duckdb, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Module 5: Pythonic Relational Analytics

    Build a DuckDB query one step at a time over a small in-memory fixture.
    Each input row is an order line. Each output row summarizes a category.
    No PostgreSQL connection or extension is needed.
    """)
    return


@app.cell
def _(duckdb):
    def build_lab(con, minimum_quantity=2):
        if type(minimum_quantity) is not int or not 1 <= minimum_quantity <= 5:
            raise ValueError("Minimum quantity must be an integer from 1 to 5")
        con.execute("CREATE TABLE order_items (product_id INTEGER, quantity INTEGER, unit_price_cents INTEGER)")
        con.execute("INSERT INTO order_items VALUES (1, 2, 500), (1, 1, 500), (2, 3, 200), (3, 2, 1000)")
        con.execute("CREATE TABLE products (product_id INTEGER PRIMARY KEY, category VARCHAR)")
        con.execute("INSERT INTO products VALUES (1, 'Books'), (2, 'Books'), (3, 'Games')")
        filtered = con.table("order_items").filter(f"quantity >= {minimum_quantity}")
        projected = filtered.project("product_id, quantity, CAST(unit_price_cents AS BIGINT) * quantity AS line_cents")
        joined = projected.join(con.table("products"), "product_id", how="inner")
        return joined.aggregate(
            "category, count(*) AS line_count, sum(quantity) AS units, sum(line_cents) AS revenue_cents",
            "category",
        ).order("category")

    def inspect_and_fetch(minimum_quantity, fetch):
        with duckdb.connect(":memory:") as con:
            relation = build_lab(con, minimum_quantity)
            generated_sql = relation.sql_query()
            if not fetch:
                return generated_sql, None, None
            rows = relation.fetchall()
            con.execute("INSERT INTO order_items VALUES (3, 5, 1000)")
            return generated_sql, rows, relation.fetchall()

    return build_lab, inspect_and_fetch


@app.cell
def _(mo):
    minimum = mo.ui.slider(1, 5, value=2, label="Minimum quantity")
    fetch = mo.ui.checkbox(label="Fetch rows and demonstrate re-execution")
    mo.vstack([minimum, fetch])
    return fetch, minimum


@app.cell
def _(fetch, inspect_and_fetch, minimum, mo):
    _sql, _before, _after = inspect_and_fetch(minimum.value, fetch.value)
    mo.vstack([
        mo.md("### Generated SQL"),
        mo.as_html(_sql),
        mo.md("### Materialized rows (category, line count, units, revenue in cents)"),
        mo.as_html("Nothing fetched yet." if _before is None else f"First fetch: {_before}\nAfter inserting an eligible Games line: {_after}"),
    ])
    return


if __name__ == "__main__":
    app.run()
