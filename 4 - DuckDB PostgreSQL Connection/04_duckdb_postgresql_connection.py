# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo>=0.11,<1",
#     "duckdb>=2.0.0",
#     "psycopg[binary]>=3.2,<4",
#     "python-dotenv>=1,<2",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="Module 4: DuckDB PostgreSQL Connection")


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
    from contextlib import contextmanager
    from dataclasses import dataclass, field
    import json
    import os
    from pathlib import Path
    from types import SimpleNamespace
    import marimo as mo

    module_dir = Path(__file__).resolve().parent

    MAX_ROWS = 500
    REMOTE = """SELECT current_user::text AS pg_role,
 current_database()::text AS pg_database,
 current_setting('server_version_num')::integer AS pg_version,
 current_setting('transaction_read_only') = 'on' AS pg_read_only"""
    SCAN = """SELECT count(*) AS matching_lines
FROM course_pg.commerce.order_items WHERE quantity >= 2"""
    SAMPLE = """SELECT order_item_id, unit_price_cents, quantity
FROM commerce.order_items ORDER BY order_item_id LIMIT {limit}"""
    LOCAL = """SELECT count(*) AS sampled_lines,
 sum(CAST(unit_price_cents AS HUGEINT) * CAST(quantity AS HUGEINT)) AS sampled_cents
FROM line_sample"""

    class LabError(RuntimeError):
        pass

    @dataclass(frozen=True)
    class Settings:
        host: str
        port: int
        password: str = field(repr=False)
        sslmode: str = "prefer"
        sslrootcert: str = ""

        @classmethod
        def load(cls, path):
            from dotenv import dotenv_values

            values = {**dotenv_values(path, interpolate=False), **os.environ}
            host = values.get("PGHOST", "127.0.0.1")
            port = int(values.get("PGPORT", "54329"))
            password = values.get("COURSE_ANALYST_PASSWORD")
            mode = values.get("PGSSLMODE", "prefer")
            if (
                not host
                or not 1 <= port <= 65535
                or not password
                or password.startswith("REPLACE_")
                or values.get("PGDATABASE", "goliath_ecommerce") != "goliath_ecommerce"
                or values.get("COURSE_ANALYST_USER", "course_analyst") != "course_analyst"
                or mode not in ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
            ):
                raise LabError(
                    "Check the course database, analyst credentials, endpoint and TLS settings."
                )
            return cls(host, port, password, mode, values.get("PGSSLROOTCERT") or "")

    def sql_string(value):
        if "\x00" in value:
            raise ValueError("NUL is not valid in a SQL string")
        return "'" + value.replace("'", "''") + "'"

    def sample_sql(limit):
        if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
            raise ValueError("Sample size must be an integer from 1 to 500.")
        return SAMPLE.format(limit=limit)

    @contextmanager
    def local():
        import duckdb

        conn = duckdb.connect(
            ":memory:",
            config={
                "autoinstall_known_extensions": "false",
                "autoload_known_extensions": "false",
            },
        )
        try:
            yield conn
        finally:
            conn.close()

    def install_extension():
        try:
            with local() as db:
                version = db.execute("SELECT version()").fetchone()[0]
                db.execute("INSTALL postgres")
                db.execute("LOAD postgres")
                return {"duckdb_version": version, "postgres_extension": "loaded"}
        except Exception:
            raise LabError(
                "Could not install or load the official postgres extension. Check your DuckDB version, platform and extension download access."
            ) from None

    def remote(sql):
        return "SELECT * FROM postgres_query('course_pg', " + sql_string(sql) + ")"

    def run(path, limit):
        source = sample_sql(limit)
        stage = "configuration"
        try:
            from psycopg.conninfo import make_conninfo

            cfg = Settings.load(path)
            options = dict(
                host=cfg.host,
                port=cfg.port,
                dbname="goliath_ecommerce",
                user="course_analyst",
                password=cfg.password,
                sslmode=cfg.sslmode,
                connect_timeout=5,
                application_name="goliath_module04",
                options="-c default_transaction_read_only=on -c statement_timeout=10000",
            )
            if cfg.sslrootcert:
                options["sslrootcert"] = cfg.sslrootcert
            dsn = make_conninfo(**options)
            stage = "extension load (install it explicitly first)"
            with local() as db:
                version = db.execute("SELECT version()").fetchone()[0]
                db.execute("LOAD postgres")
                stage = "attachment or PostgreSQL identity check"
                db.execute(
                    "ATTACH "
                    + sql_string(dsn)
                    + " AS course_pg (TYPE postgres, READ_ONLY, SCHEMA 'commerce')"
                )
                role, database, pg_version, read_only = db.execute(remote(REMOTE)).fetchone()
                if (role, database, read_only) != (
                    "course_analyst",
                    "goliath_ecommerce",
                    True,
                ) or not 180000 <= pg_version < 200000:
                    raise LabError(
                        "Expected PostgreSQL 19 (or 18), goliath_ecommerce, course_analyst and a read-only transaction."
                    )
                stage = "attached scan (check that Module 2 migrated order_items and granted SELECT)"
                plan = "\n".join(
                    str(row[-1]) for row in db.execute("EXPLAIN " + SCAN).fetchall()
                )
                matching = db.execute(SCAN).fetchone()[0]
                stage = "bounded extraction and local aggregation"
                db.execute("CREATE TEMP TABLE line_sample AS " + remote(source))
                db.execute("DETACH course_pg")
                rows, cents = db.execute(LOCAL).fetchone()
                if rows > limit:
                    raise LabError("Sample exceeded its requested bound.")
                return {
                    "duckdb_version": version,
                    "postgres_version_num": pg_version,
                    "postgres_role": role,
                    "postgres_read_only": read_only,
                    "attached_matching_lines": matching,
                    "attached_plan_mentions_postgres_scan": "POSTGRES_SCAN" in plan.upper(),
                    "sample_limit": limit,
                    "sampled_lines": rows,
                    "sampled_cents": cents,
                    "local_aggregate_after_detach": True,
                }
        except LabError:
            raise
        except Exception:
            raise LabError(
                "Module 4 could not complete: "
                + stage
                + ". Raw errors are withheld because they may contain credentials."
            ) from None

    lab = SimpleNamespace(
        MAX_ROWS=MAX_ROWS,
        REMOTE=REMOTE,
        SCAN=SCAN,
        SAMPLE=SAMPLE,
        LOCAL=LOCAL,
        LabError=LabError,
        Settings=Settings,
        sql_string=sql_string,
        sample_sql=sample_sql,
        local=local,
        install_extension=install_extension,
        remote=remote,
        run=run,
    )

    return json, lab, mo, module_dir


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Module 4: DuckDB PostgreSQL Connection

    Attach your course database as `course_analyst`, compare attached and
    server-executed SQL, then aggregate a bounded sample after detaching.
    Opening this notebook requests your lab database if you do not already have one.
    It does not connect to PostgreSQL or install extensions.
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
def _(form, json, lab, mo):
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
