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
