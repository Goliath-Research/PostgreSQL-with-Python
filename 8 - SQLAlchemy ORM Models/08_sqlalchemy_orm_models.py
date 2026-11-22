import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


with app.setup(hide_code=True):
    import sys as _course_sys
    from pathlib import Path as _CoursePath

    _course_here = _CoursePath.cwd().resolve()
    for _course_candidate in (_course_here, *_course_here.parents):
        if (_course_candidate / "course_lab.py").is_file():
            _course_root = str(_course_candidate)
            if _course_root not in _course_sys.path:
                _course_sys.path.insert(0, _course_root)
            break
    else:
        raise RuntimeError("Open this notebook from the course repository.")
    import course_lab

    if course_lab.autostart_enabled():
        course_lab.attach()


@app.cell(hide_code=True)
def _(mo):
    _lab_panel, leave_lab = course_lab.leave_controls(mo)
    _lab_panel
    return (leave_lab,)


@app.cell(hide_code=True)
def _(leave_lab, mo):
    _lab_message = course_lab.release_if_requested(leave_lab.value)
    mo.stop(_lab_message is None)
    mo.md(_lab_message)
    return


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
