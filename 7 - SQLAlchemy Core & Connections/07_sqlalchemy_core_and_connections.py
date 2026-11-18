import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import sqlalchemy as sa
    return mo, sa


@app.cell
def _(sa):
    def run_fixture(minimum):
        engine = sa.create_engine("sqlite+pysqlite:///:memory:")
        metadata = sa.MetaData()
        items = sa.Table("items", metadata,
                         sa.Column("id", sa.Integer, primary_key=True),
                         sa.Column("quantity", sa.Integer, nullable=False))
        statement = (sa.select(items.c.id, items.c.quantity)
                     .where(items.c.quantity >= sa.bindparam("minimum", type_=sa.Integer()))
                     .order_by(items.c.id))

        def read(conn):
            return [dict(row) for row in conn.execute(statement, {"minimum": minimum}).mappings()]

        try:
            metadata.create_all(engine)
            with engine.begin() as conn:
                conn.execute(items.insert(), [{"id": 1, "quantity": 1}, {"id": 2, "quantity": 3}])
            with engine.connect() as conn:
                before = read(conn)
            with engine.connect() as conn:
                transaction = conn.begin()
                conn.execute(items.insert(), {"id": 3, "quantity": 5})
                pending = read(conn)
                transaction.rollback()
            with engine.connect() as conn:
                after = read(conn)
            return {"compiled_sql": str(statement.compile(dialect=engine.dialect)),
                    "bound_values": {"minimum": minimum}, "committed": before,
                    "inside_transaction": pending, "after_rollback": after}
        finally:
            engine.dispose()

    return (run_fixture,)


@app.cell
def _(mo):
    mo.md("""
    # Module 7: SQLAlchemy Core & Connections

    An Engine provides connections; a Connection executes statements and manages
    transactions. Build a Core SELECT, bind a quantity cutoff separately, then
    compare rows before, during, and after a rollback. This notebook uses a fresh
    SQLite fixture per submission. The guide includes a PostgreSQL companion lab.
    """)
    return


@app.cell
def _(mo):
    cutoff = mo.ui.slider(1, 5, value=2, label="Minimum quantity").form()
    cutoff
    return (cutoff,)


@app.cell
def _(cutoff, mo, run_fixture):
    mo.stop(cutoff.value is None, mo.md("Submit a cutoff to run the fixture."))
    mo.json(run_fixture(cutoff.value))
    return


if __name__ == "__main__":
    app.run()
