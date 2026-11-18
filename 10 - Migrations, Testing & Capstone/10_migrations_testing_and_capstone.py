import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


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
    This notebook never connects to PostgreSQL.
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
