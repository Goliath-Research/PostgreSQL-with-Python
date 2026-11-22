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

    _path = str(Path(__file__).resolve().parent)
    if _path not in sys.path:
        sys.path.insert(0, _path)
    import module_10_lab as lab
    return lab, mo


@app.cell
def _(mo):
    mo.md("""
    # Module 10: Migrations, Testing & Capstone

    Run two Alembic revisions in a throwaway SQLite database. Verify that an
    existing order gets a status on upgrade and retains its amount on downgrade.
    Then use the companion guide to build two deliverables on the same PostgreSQL
    laboratory database: read-only reporting and transactional order services.
    Opening this notebook requests your lab database if you do not already have one.
    The migration exercise below uses SQLite and does not connect to PostgreSQL.
    """)
    launch = mo.ui.run_button(label="Run disposable migration lab")
    launch
    return (launch,)


@app.cell
def _(lab, launch, mo):
    mo.stop(not launch.value, mo.md("Run the migration lab to see revision evidence."))
    mo.json(lab.migration_lab())
    return


if __name__ == "__main__":
    app.run()
