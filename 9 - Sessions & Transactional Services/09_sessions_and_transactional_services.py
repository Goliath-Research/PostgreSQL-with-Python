import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys
    from pathlib import Path
    import marimo as mo

    _directory = str(Path(__file__).resolve().parent)
    if _directory not in sys.path:
        sys.path.insert(0, _directory)
    import module_09_services as services
    return mo, services


@app.cell
def _(mo):
    mo.md("""
    # Module 9: Sessions & Transactional Services

    Submit a valid order or one with an invalid second line. Compare the ID
    assigned after flush with what a fresh Session reads after commit or rollback.
    Then compare the SELECT statements emitted by two relationship loading strategies.
    Each submission starts with a fresh SQLite fixture.
    """)
    return


@app.cell
def _(mo):
    scenario = mo.ui.dropdown({"Valid order": "valid", "Invalid second line": "invalid"},
                              value="Valid order", label="Scenario").form()
    scenario
    return (scenario,)


@app.cell
def _(mo, scenario, services):
    mo.stop(scenario.value is None, mo.md("Submit a scenario."))
    mo.json(services.run_lab(invalid=scenario.value == "invalid"))
    return


if __name__ == "__main__":
    app.run()
