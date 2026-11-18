import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys
    from pathlib import Path
    import marimo as mo

    module_dir = Path(__file__).resolve().parent
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    import module_04_support as lab

    return lab, mo, module_dir


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Module 4: DuckDB PostgreSQL Connection

    Attach your course database as `course_analyst`, compare attached and
    server-executed SQL, then aggregate a bounded sample after detaching.
    Opening this notebook does not connect to PostgreSQL or install extensions.
    """)
    return


@app.cell
def _(lab, mo):
    mo.md("### Attached scan\n\n```sql\n" + lab.SCAN + "\n```")
    return


@app.cell
def _(mo, module_dir):
    form = mo.ui.dictionary({
        "action": mo.ui.dropdown(
            options=["Run read-only lab", "Install / load extension"],
            value="Run read-only lab",
        ),
        "env": mo.ui.text(value=str(module_dir.parent / ".env"), label=".env path"),
        "limit": mo.ui.number(start=1, stop=500, step=1, value=25, label="Sample row cap"),
    }).form(submit_button_label="Run selected action")
    form
    return (form,)


@app.cell
def _(form, lab, mo):
    import json

    mo.stop(form.value is None, mo.md("Submit an action to begin."))
    _values = form.value
    try:
        if _values["action"] == "Install / load extension":
            _result = lab.install_extension()
        else:
            _result = lab.run(_values["env"], int(_values["limit"]))
        _display = mo.md("```json\n" + json.dumps(_result, indent=2) + "\n```")
    except lab.LabError as _error:
        _display = mo.md(str(_error))
    _display
    return


@app.cell(hide_code=True)
def _(lab, mo):
    mo.md("### Local aggregation after detach\n\n```sql\n" + lab.LOCAL + "\n```")
    return


if __name__ == "__main__":
    app.run()
