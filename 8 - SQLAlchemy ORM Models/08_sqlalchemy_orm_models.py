import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys
    from pathlib import Path
    import marimo as mo

    _module_dir = str(Path(__file__).resolve().parent)
    if _module_dir not in sys.path:
        sys.path.insert(0, _module_dir)
    import module_08_models as models
    return models, mo


@app.cell
def _(mo):
    mo.md("""
    # Module 8: SQLAlchemy ORM Models

    `Customer.customer_id` identifies a customer; `Order.customer_id` is a
    foreign key. The `orders` and `customer` relationships let you navigate
    between Python objects. Select a customer, predict the results of the
    identity comparisons, then submit to check your predictions.

    This SQLite fixture is recreated on each submission. The mappings are in
    `module_08_models.py`; they are not migrations for the course database.
    """)
    return


@app.cell
def _(mo):
    customer_form = mo.ui.dropdown(
        {"Ada (two orders)": 1, "Lin (no orders)": 2, "Missing customer": 99},
        value="Ada (two orders)", label="Customer",
    ).form()
    customer_form
    return (customer_form,)


@app.cell
def _(customer_form, models, mo):
    mo.stop(customer_form.value is None, mo.md("Submit a customer to inspect the mapping."))
    mo.json(models.run_lab(customer_form.value))
    return


if __name__ == "__main__":
    app.run()
