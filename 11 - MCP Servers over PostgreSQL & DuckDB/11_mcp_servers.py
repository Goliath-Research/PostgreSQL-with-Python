import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Module 11: MCP Servers over PostgreSQL & DuckDB

    Run the companion Python client in your terminal. It starts the server
    over stdio and discovers two read-only tools. Read the reporting resource,
    predict the summary for order 101 (two lines), and compare it with the
    date-bounded category rollup (top category: Books, 1,500 cents).

    The notebook does not launch the server, install dependencies, or open a
    database connection. See `11_content.md` for the fixture, protocol tests,
    and opt-in PostgreSQL privilege checks.
    """)
    return


if __name__ == "__main__":
    app.run()
