# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "psycopg[binary]>=3.1,<4",
#     "python-dotenv>=1,<2",
# ]
# ///

import marimo

app = marimo.App(
    width="medium",
    app_title="Module 1: PostgreSQL Environment, Connections & Access Control",
)


@app.cell
def _():
    from datetime import datetime, timezone
    import importlib.metadata
    import json
    import os
    from pathlib import Path
    import re
    import marimo as mo

    return Path, datetime, importlib, json, mo, os, re, timezone


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # Module 1: PostgreSQL Environment, Connections & Access Control
        ## PostgreSQL with Python: Analytics, ORM, and Database Applications — Goliath Research Academy

        Establish a reproducible client/server PostgreSQL environment, configure credentials without exposing secrets, verify separate application (`course_app`) and analytical (`course_analyst`) identities using **Psycopg 3**, test authorization boundaries against `lab.connection_probe` inside rollback-only transactions, and export a secret-free readiness report.

        > **Scope Boundary:** The e-commerce schema and data migration belong in **Module 2**. Opening this notebook does **not** connect to PostgreSQL automatically or launch/destroy containers. Connection diagnostics and privilege tests each require an explicit action below.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## 1.1 From Embedded SQLite to a Database Server

        ```text
        Introductory course
        Marimo / Python
            │
         sqlite3 (in-process library)
            │
        SQLite database (:memory: or local file)

        Advanced course
        Marimo / Python
            │
        PostgreSQL client driver (Psycopg 3 / DuckDB 2.0 / SQLAlchemy 2.0)
            │
        Host + port + authentication
            │
        PostgreSQL server
            │
        Database (goliath_ecommerce) → schemas (commerce, lab) → tables and other objects
        ```

        - **What remains transferable:** Relations, primary and foreign keys, constraints (`CHECK`, `UNIQUE`, `NOT NULL`), joins, result-grain reasoning, ACID transactions, and window functions.
        - **What becomes explicit:** Server lifecycle, network endpoint (`host`, `port`), connection timeouts, login authentication (`session_user`), role ownership (`current_user`), schema namespaces, and multi-layered privileges.
        - **Why changing a connection string alone does not complete a migration:** Swapping `sqlite3.connect()` for `psycopg.connect()` does not establish non-superuser roles, schema boundaries, default privileges, or PostgreSQL native types (`TIMESTAMPTZ`, `NUMERIC`, identity sequences).
        """
    )
    return


@app.cell
def _(mo):
    arch_q1 = mo.ui.dropdown(
        options=[
            "Select an answer...",
            "Transferable relational concept",
            "New client/server configuration or implementation concern",
        ],
        value="Transferable relational concept",
        label="1. Ensuring an order header and its line items commit or roll back together:",
    )
    arch_q2 = mo.ui.dropdown(
        options=[
            "Select an answer...",
            "Transferable relational concept",
            "New client/server configuration or implementation concern",
        ],
        value="New client/server configuration or implementation concern",
        label="2. Separating the schema owner (`course_owner`) from the runtime login (`course_app`):",
    )
    arch_q3 = mo.ui.dropdown(
        options=[
            "Select an answer...",
            "Transferable relational concept",
            "New client/server configuration or implementation concern",
        ],
        value="New client/server configuration or implementation concern",
        label="3. Qualifying `lab.connection_probe` and managing `search_path` across roles:",
    )
    mo.vstack([mo.md("### Exercise 1.1: Classify Transition Responsibilities"), arch_q1, arch_q2, arch_q3])
    return arch_q1, arch_q2, arch_q3


@app.cell(hide_code=True)
def _(arch_q1, arch_q2, arch_q3, mo):
    _ok = (
        arch_q1.value == "Transferable relational concept"
        and arch_q2.value == "New client/server configuration or implementation concern"
        and arch_q3.value == "New client/server configuration or implementation concern"
    )
    mo.callout(
        mo.md(
            "**Exercise 1.1 Checked:** Atomic multi-table transactions carry over conceptually from SQLite, while role separation (`course_owner` vs. `course_app` / `course_analyst`) and schema-qualified namespaces (`lab.connection_probe`) require explicit server setup."
            if _ok
            else "Review the three prompts above to distinguish transferable relational concepts from new PostgreSQL client/server responsibilities."
        ),
        kind="success" if _ok else "warn",
    )
    return


@app.cell(hide_code=True)
def _(Path, mo):
    _here = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    _root = _here.parent if _here.name == "1 - PostgreSQL Environment" else _here
    _expected_files = [
        ("compose.yaml", _root / "compose.yaml"),
        (".env.example", _root / ".env.example"),
        ("bootstrap.sql", _root / "bootstrap.sql"),
        ("bootstrap/01_roles_and_database.sql", _root / "bootstrap" / "01_roles_and_database.sql"),
        ("bootstrap/02_schemas_and_probe.sql", _root / "bootstrap" / "02_schemas_and_probe.sql"),
    ]
    _rows = [
        {
            "artifact": label,
            "present": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
        for label, path in _expected_files
    ]
    mo.vstack(
        [
            mo.md(
                """
                ## 1.2 Establish a Reproducible Laboratory

                ```text
                PostgreSQL-with-Python/
                ├── compose.yaml
                ├── .env.example
                ├── .gitignore
                ├── pyproject.toml
                ├── README.md
                ├── bootstrap.sql
                ├── bootstrap/
                │   ├── 01_roles_and_database.sql
                │   └── 02_schemas_and_probe.sql
                └── 1 - PostgreSQL Environment/
                    ├── 01_postgresql_environment.py
                    └── 01_content.md
                ```

                ### Lifecycle Commands (Run in Terminal, Never Auto-Executed by Notebook Cells)
                - **Start container & wait for readiness:** `docker compose up -d && docker compose ps`
                - **Stop without deleting data (`goliath_pgdata` preserved):** `docker compose stop`
                - **Restart existing environment:** `docker compose start`
                - **Destructive reset (deletes volume and re-runs bootstrap on next `up`):** `docker compose down -v`
                """
            ),
            mo.ui.table(_rows, selection=None),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## 1.3 Understand Database Namespaces & 1.4 Role Separation

        ### Course Naming Convention
        | Object | Name | Purpose |
        | :--- | :--- | :--- |
        | **Database** | `goliath_ecommerce` | Authoritative course database |
        | **Schema** | `commerce` | Business tables migrated in Module 2 |
        | **Schema** | `lab` | Disposable diagnostic objects for Module 1 (`lab.connection_probe`) |

        Always prefer schema-qualified names such as `SELECT * FROM lab.connection_probe;`. When a query omits the schema (`SELECT * FROM connection_probe;`), PostgreSQL searches the schemas in `search_path`; if `lab` is not on the active `search_path`, PostgreSQL raises `UndefinedTable` (`relation "connection_probe" does not exist`, SQLSTATE `42P01`).

        ### Four-Role Access Model
        | Role | Login? | Intended Responsibility | Later Interface |
        | :--- | :---: | :--- | :--- |
        | `course_owner` | No | Own course schemas (`commerce`, `lab`) and objects | Assumed via `SET ROLE` during migration |
        | `course_migrator` | Yes | Perform controlled schema changes through `course_owner` | Module 2 migration & Module 10 Alembic |
        | `course_app` | Yes | Execute permitted application reads and writes | Psycopg 3 & SQLAlchemy (`Stage C`) |
        | `course_analyst` | Yes | Read approved data for analytical work | DuckDB 2.0 read-only analytics (`Stage B`) |
        """
    )
    return


@app.cell
def _(mo):
    role_duckdb = mo.ui.dropdown(
        options=["course_owner", "course_migrator", "course_app", "course_analyst", "postgres"],
        value="course_analyst",
        label="Identity that DuckDB 2.0 analytical sessions (Modules 4–6) should use:",
    )
    role_sqlalchemy = mo.ui.dropdown(
        options=["course_owner", "course_migrator", "course_app", "course_analyst", "postgres"],
        value="course_app",
        label="Identity that SQLAlchemy transactional sessions (Modules 7–10) should use:",
    )
    mo.vstack([mo.md("### Exercise 1.4: Map Course Interfaces to PostgreSQL Identities"), role_duckdb, role_sqlalchemy])
    return role_duckdb, role_sqlalchemy


@app.cell(hide_code=True)
def _(mo, role_duckdb, role_sqlalchemy):
    _valid = role_duckdb.value == "course_analyst" and role_sqlalchemy.value == "course_app"
    mo.callout(
        mo.md(
            "**Role Mapping Verified:** DuckDB connects as `course_analyst` (read-only), and SQLAlchemy application services connect as `course_app` (read/write on permitted tables, no DDL ownership)."
            if _valid
            else "Select `course_analyst` for DuckDB analytical sessions and `course_app` for SQLAlchemy transactional application sessions."
        ),
        kind="success" if _valid else "warn",
    )
    return


@app.cell
def _(Path, importlib, os, re):
    def check_dependencies() -> list[dict[str, object]]:
        packages = [
            ("marimo", "marimo"),
            ("psycopg", "psycopg"),
            ("python-dotenv", "python-dotenv"),
        ]
        results: list[dict[str, object]] = []
        for label, dist_name in packages:
            try:
                version = importlib.metadata.version(dist_name)
                results.append({"package": label, "installed": True, "version": version})
            except importlib.metadata.PackageNotFoundError:
                results.append({"package": label, "installed": False, "version": "missing"})
        return results

    def parse_env_file(env_path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        if not env_path.is_file():
            return values
        try:
            from dotenv import dotenv_values  # type: ignore

            raw = dotenv_values(env_path)
            return {k: str(v) for k, v in raw.items() if k and v is not None}
        except Exception:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                values[key.strip()] = val.strip().strip("'").strip('"')
            return values

    def redact_text(message: str, secrets: list[str]) -> str:
        redacted = str(message)
        for secret in secrets:
            if secret and len(secret) >= 2:
                redacted = redacted.replace(secret, "[REDACTED]")
        redacted = re.sub(
            r"(password\s*=\s*)([^\s'\"&]+)",
            r"\1[REDACTED]",
            redacted,
            flags=re.IGNORECASE,
        )
        redacted = re.sub(
            r"(postgresql(?:\+\w+)?://[^:/\s]+:)([^@\s]+)(@)",
            r"\1[REDACTED]\3",
            redacted,
            flags=re.IGNORECASE,
        )
        return redacted

    def load_lab_config(root_dir: Path, overrides: dict[str, str] | None = None) -> dict[str, object]:
        env_path = root_dir / ".env"
        file_values = parse_env_file(env_path)
        merged: dict[str, str] = {}
        for key in (
            "PGHOST",
            "PGPORT",
            "PGDATABASE",
            "PGCONNECT_TIMEOUT",
            "COURSE_MIGRATOR_USER",
            "COURSE_MIGRATOR_PASSWORD",
            "COURSE_APP_USER",
            "COURSE_APP_PASSWORD",
            "COURSE_ANALYST_USER",
            "COURSE_ANALYST_PASSWORD",
        ):
            if overrides and key in overrides and overrides[key] != "":
                merged[key] = str(overrides[key]).strip()
            elif key in os.environ and os.environ[key].strip() != "":
                merged[key] = os.environ[key].strip()
            elif key in file_values and file_values[key].strip() != "":
                merged[key] = file_values[key].strip()
            else:
                merged[key] = ""

        # Apply safe non-secret defaults if not explicitly set
        host = merged["PGHOST"] or "127.0.0.1"
        port_raw = merged["PGPORT"] or "54329"
        database = merged["PGDATABASE"] or "goliath_ecommerce"
        timeout_raw = merged["PGCONNECT_TIMEOUT"] or "5"
        app_user = merged["COURSE_APP_USER"] or "course_app"
        analyst_user = merged["COURSE_ANALYST_USER"] or "course_analyst"
        migrator_user = merged["COURSE_MIGRATOR_USER"] or "course_migrator"

        issues: list[str] = []
        try:
            port = int(port_raw)
            if not (1 <= port <= 65535):
                issues.append("PGPORT must be an integer between 1 and 65535.")
        except ValueError:
            port = -1
            issues.append(f"PGPORT is not a valid integer: {port_raw!r}")

        try:
            connect_timeout = int(timeout_raw)
            if not (1 <= connect_timeout <= 60):
                issues.append("PGCONNECT_TIMEOUT must be between 1 and 60 seconds.")
        except ValueError:
            connect_timeout = 5
            issues.append(f"PGCONNECT_TIMEOUT is not a valid integer: {timeout_raw!r}")

        if not host:
            issues.append("PGHOST is missing.")
        if not database:
            issues.append("PGDATABASE is missing.")
        if not merged["COURSE_APP_PASSWORD"]:
            issues.append("COURSE_APP_PASSWORD is missing (set in .env or environment).")
        if not merged["COURSE_ANALYST_PASSWORD"]:
            issues.append("COURSE_ANALYST_PASSWORD is missing (set in .env or environment).")

        secrets = [
            merged["COURSE_APP_PASSWORD"],
            merged["COURSE_ANALYST_PASSWORD"],
            merged["COURSE_MIGRATOR_PASSWORD"],
        ]

        redacted_summary = [
            {"field": "Configuration Source", "value": ".env present" if env_path.is_file() else "environment / defaults (.env not found)"},
            {"field": "Host", "value": host},
            {"field": "Port", "value": str(port) if port > 0 else f"INVALID ({port_raw})"},
            {"field": "Database", "value": database},
            {"field": "Connect Timeout (s)", "value": str(connect_timeout)},
            {"field": "Application Role", "value": app_user},
            {
                "field": "Application Password",
                "value": "configured, not displayed" if merged["COURSE_APP_PASSWORD"] else "MISSING",
            },
            {"field": "Analyst Role", "value": analyst_user},
            {
                "field": "Analyst Password",
                "value": "configured, not displayed" if merged["COURSE_ANALYST_PASSWORD"] else "MISSING",
            },
            {"field": "Migrator Role", "value": migrator_user},
            {
                "field": "Migrator Password",
                "value": "configured, not displayed" if merged["COURSE_MIGRATOR_PASSWORD"] else "not configured (optional in Module 1)",
            },
        ]

        return {
            "env_file_exists": env_path.is_file(),
            "host": host,
            "port": port,
            "database": database,
            "connect_timeout": connect_timeout,
            "app_user": app_user,
            "app_password": merged["COURSE_APP_PASSWORD"],
            "analyst_user": analyst_user,
            "analyst_password": merged["COURSE_ANALYST_PASSWORD"],
            "migrator_user": migrator_user,
            "migrator_password": merged["COURSE_MIGRATOR_PASSWORD"],
            "secrets": [s for s in secrets if s],
            "issues": issues,
            "valid": len(issues) == 0,
            "redacted_summary": redacted_summary,
        }

    return check_dependencies, load_lab_config, parse_env_file, redact_text


@app.cell
def _(Path, check_dependencies, load_lab_config, mo):
    _here = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    repo_root = _here.parent if _here.name == "1 - PostgreSQL Environment" else _here
    dependency_status = check_dependencies()
    lab_config = load_lab_config(repo_root)

    mo.vstack(
        [
            mo.md(
                """
                ## 1.5 Configure Credentials Without Exposing Them

                The notebook reads connection settings from environment variables or a local `.env` file in the repository root and displays **only a redacted summary**. Passwords, raw DSN strings, and unredacted exception parameters are never printed.
                """
            ),
            mo.md("### Python Dependency Check"),
            mo.ui.table(dependency_status, selection=None),
            mo.md("### Redacted Configuration Summary"),
            mo.ui.table(lab_config["redacted_summary"], selection=None),
            mo.callout(
                mo.md(
                    "All required configuration fields are present and validated."
                    if lab_config["valid"]
                    else "Configuration incomplete:\n- " + "\n- ".join(lab_config["issues"])
                ),
                kind="success" if lab_config["valid"] else "warn",
            ),
        ]
    )
    return dependency_status, lab_config, repo_root


@app.cell
def _( redact_text):
    def classify_db_error(exc: Exception, secrets: list[str]) -> dict[str, str]:
        sqlstate = getattr(exc, "sqlstate", None) or ""
        raw_msg = redact_text(str(exc), secrets).strip()
        lower = raw_msg.lower()

        if sqlstate == "28P01" or "password authentication failed" in lower:
            category = "Authentication failed (28P01)"
            guidance = "Verify the role name and password in your local .env against the provisioning script."
        elif sqlstate == "3D000" or ("database" in lower and "does not exist" in lower):
            category = "Database does not exist (3D000)"
            guidance = "Verify PGDATABASE=goliath_ecommerce and confirm that bootstrap.sql created the database."
        elif sqlstate == "42501" and "schema" in lower:
            category = "Permission denied for schema (42501)"
            guidance = "Verify whether the role has USAGE (or CREATE, if expected) on the target schema."
        elif sqlstate == "42501":
            category = "Permission denied for object/operation (42501)"
            guidance = "Verify table/sequence privileges or object ownership; do not grant superuser to fix routine privilege denials."
        elif sqlstate == "42P01" or ("relation" in lower and "does not exist" in lower):
            category = "Relation does not exist (42P01)"
            guidance = "Confirm that the object exists and use a schema-qualified name such as lab.connection_probe."
        elif "timeout expired" in lower or "timed out" in lower:
            category = "Connection timeout"
            guidance = "Check whether the host/port endpoint is reachable from this Python process and not blocked by a firewall."
        elif "connection refused" in lower or "could not connect to server" in lower:
            category = "Connection refused"
            guidance = "Check that the PostgreSQL server/container is running and listening on the configured host and port."
        else:
            category = f"Database error ({type(exc).__name__})"
            guidance = "Inspect the SQLSTATE code and redacted message to isolate endpoint, identity, or object state."

        return {
            "category": category,
            "sqlstate": sqlstate or "N/A",
            "redacted_message": raw_msg.splitlines()[0] if raw_msg else type(exc).__name__,
            "guidance": guidance,
        }

    def connect_role(cfg: dict[str, object], role_key: str):
        import psycopg
        from psycopg.rows import dict_row

        user = str(cfg[f"{role_key}_user"])
        password = str(cfg[f"{role_key}_password"])
        return psycopg.connect(
            host=str(cfg["host"]),
            port=int(cfg["port"]),
            dbname=str(cfg["database"]),
            user=user,
            password=password,
            connect_timeout=int(cfg["connect_timeout"]),
            autocommit=False,
            row_factory=dict_row,
        )

    def run_connection_diagnostics(cfg: dict[str, object]) -> dict[str, object]:
        if not cfg["valid"]:
            return {
                "ok": False,
                "error": "Configuration is incomplete: " + "; ".join(cfg["issues"]),
                "sessions": [],
                "schemas": [],
                "server_version": None,
            }

        sessions: list[dict[str, object]] = []
        schemas: list[dict[str, object]] = []
        server_version: str | None = None
        errors: list[dict[str, str]] = []

        for role_key, expected_role in (("app", cfg["app_user"]), ("analyst", cfg["analyst_user"])):
            conn = None
            try:
                conn = connect_role(cfg, role_key)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            current_database() AS database_name,
                            current_user AS effective_role,
                            session_user AS login_role,
                            current_schema() AS current_schema,
                            current_setting('server_version') AS server_version,
                            current_setting('search_path') AS search_path
                        """
                    )
                    row = cur.fetchone()
                    assert row is not None
                    server_version = str(row["server_version"])

                    cur.execute(
                        """
                        SELECT
                            n.nspname AS schema_name,
                            pg_catalog.pg_get_userbyid(n.nspowner) AS owner_role
                        FROM pg_catalog.pg_namespace n
                        WHERE n.nspname = ANY(%s)
                        ORDER BY n.nspname
                        """,
                        (["commerce", "lab"],),
                    )
                    if not schemas:
                        schemas = [dict(r) for r in cur.fetchall()]

                    cur.execute(
                        """
                        SELECT COUNT(*) AS probe_rows
                        FROM lab.connection_probe
                        WHERE actor_role IS NOT NULL
                        """
                    )
                    probe_row = cur.fetchone()
                    probe_count = int(probe_row["probe_rows"]) if probe_row else 0

                conn.rollback()
            except Exception as exc:
                diag = classify_db_error(exc, list(cfg["secrets"]))
                diag["role"] = str(expected_role)
                errors.append(diag)
            finally:
                if conn is not None:
                    conn.close()
                    closed_ok = conn.closed
                else:
                    closed_ok = True

            if conn is not None and not errors:
                sessions.append(
                    {
                        "configured_role": str(expected_role),
                        "database_name": row["database_name"],
                        "login_role": row["login_role"],
                        "effective_role": row["effective_role"],
                        "current_schema": row["current_schema"],
                        "search_path": row["search_path"],
                        "probe_rows_visible": probe_count,
                        "connection_closed": closed_ok,
                    }
                )

        return {
            "ok": len(errors) == 0 and len(sessions) == 2,
            "server_version": server_version,
            "sessions": sessions,
            "schemas": schemas,
            "errors": errors,
        }

    return classify_db_error, connect_role, run_connection_diagnostics


@app.cell
def _(mo):
    diag_button = mo.ui.run_button(label="Run connection diagnostics (course_app & course_analyst)")
    mo.vstack(
        [
            mo.md(
                """
                ## 1.6 Connect from Python with Psycopg 3

                Click the button below to open short-lived, read-only diagnostic connections as `course_app` and `course_analyst`, run parameterized catalog queries (`current_database()`, `current_user`, `session_user`, `current_schema()`), inspect schema ownership (`commerce`, `lab`), and explicitly close every connection.
                """
            ),
            diag_button,
        ]
    )
    return (diag_button,)


@app.cell
def _(diag_button, lab_config, mo, run_connection_diagnostics):
    if not diag_button.value:
        diag_result = None
        _view = mo.callout(
            mo.md("Connection diagnostics have not been triggered yet. Click **Run connection diagnostics** above when your PostgreSQL instance is running."),
            kind="neutral",
        )
    else:
        diag_result = run_connection_diagnostics(lab_config)
        if diag_result["ok"]:
            _view = mo.vstack(
                [
                    mo.callout(
                        mo.md(f"**Connected successfully** to PostgreSQL `{diag_result['server_version']}` as both `course_app` and `course_analyst`. All diagnostic connections closed cleanly."),
                        kind="success",
                    ),
                    mo.md("### Session Identity Verification"),
                    mo.ui.table(diag_result["sessions"], selection=None),
                    mo.md("### Verified Course Schemas (`commerce`, `lab`)"),
                    mo.ui.table(diag_result["schemas"], selection=None),
                ]
            )
        else:
            _view = mo.vstack(
                [
                    mo.callout(
                        mo.md(
                            "**Connection diagnostics reported an issue.** Review the redacted error details below."
                            if diag_result.get("errors")
                            else f"**Cannot connect yet:** {diag_result.get('error', 'Unknown configuration issue')}"
                        ),
                        kind="danger",
                    ),
                    mo.ui.table(diag_result.get("errors", []), selection=None)
                    if diag_result.get("errors")
                    else mo.md(""),
                ]
            )
    _view
    return (diag_result,)


@app.cell
def _(classify_db_error, connect_role):
    def run_privilege_test_suite(cfg: dict[str, object]) -> dict[str, object]:
        if not cfg["valid"]:
            return {
                "ok": False,
                "tests": [],
                "error": "Configuration is incomplete: " + "; ".join(cfg["issues"]),
            }

        specs = [
            {
                "test_id": 1,
                "test_name": "Application reads the probe table",
                "role_key": "app",
                "expect_allowed": True,
                "sql": "SELECT probe_id, actor_role, probe_note FROM lab.connection_probe ORDER BY probe_id LIMIT %s",
                "params": (5,),
            },
            {
                "test_id": 2,
                "test_name": "Application inserts a diagnostic record",
                "role_key": "app",
                "expect_allowed": True,
                "sql": "INSERT INTO lab.connection_probe (probe_note) VALUES (%s) RETURNING probe_id, actor_role",
                "params": ("Rollback-only privilege check from course_app",),
            },
            {
                "test_id": 3,
                "test_name": "Analyst reads the probe table",
                "role_key": "analyst",
                "expect_allowed": True,
                "sql": "SELECT probe_id, actor_role, probe_note FROM lab.connection_probe ORDER BY probe_id LIMIT %s",
                "params": (5,),
            },
            {
                "test_id": 4,
                "test_name": "Analyst inserts a diagnostic record",
                "role_key": "analyst",
                "expect_allowed": False,
                "sql": "INSERT INTO lab.connection_probe (probe_note) VALUES (%s)",
                "params": ("Unauthorized analyst write attempt",),
            },
            {
                "test_id": 5,
                "test_name": "Application creates a permanent table in commerce",
                "role_key": "app",
                "expect_allowed": False,
                "sql": "CREATE TABLE commerce.unauthorized_app_table (id integer PRIMARY KEY)",
                "params": None,
            },
            {
                "test_id": 6,
                "test_name": "Ordinary application session performs owner-only DDL",
                "role_key": "app",
                "expect_allowed": False,
                "sql": "DROP TABLE lab.connection_probe",
                "params": None,
            },
        ]

        results: list[dict[str, object]] = []
        for spec in specs:
            conn = None
            passed = False
            observed = ""
            sqlstate = "00000"
            detail = ""
            closed_after = False
            try:
                conn = connect_role(cfg, str(spec["role_key"]))
                # Always wrap in a rollback-only transaction so even allowed or unexpectedly
                # permitted changes never persist after the privilege check finishes.
                with conn.transaction(force_rollback=True):
                    with conn.cursor() as cur:
                        if spec["params"] is not None:
                            cur.execute(spec["sql"], spec["params"])
                        else:
                            cur.execute(spec["sql"])
                observed = "Allowed (rolled back via force_rollback=True)"
                passed = bool(spec["expect_allowed"]) is True
                detail = "Operation succeeded inside rollback-only transaction." if passed else "UNEXPECTED: Operation was permitted but should have been denied!"
            except Exception as exc:
                diag = classify_db_error(exc, list(cfg["secrets"]))
                sqlstate = diag["sqlstate"]
                observed = f"Denied ({sqlstate})"
                passed = (not bool(spec["expect_allowed"])) and sqlstate == "42501"
                detail = diag["redacted_message"]
            finally:
                if conn is not None:
                    conn.close()
                    closed_after = bool(conn.closed)

            results.append(
                {
                    "test_id": spec["test_id"],
                    "test": spec["test_name"],
                    "identity": cfg[f"{spec['role_key']}_user"],
                    "expected": "Allowed" if spec["expect_allowed"] else "Denied (42501)",
                    "observed": observed,
                    "passed": passed and closed_after,
                    "connection_closed": closed_after,
                    "detail": detail,
                }
            )

        return {
            "ok": len(results) == 6 and all(bool(r["passed"]) for r in results),
            "tests": results,
        }

    return (run_privilege_test_suite,)


@app.cell
def _(mo):
    priv_button = mo.ui.run_button(label="Run access-control tests (isolated force_rollback=True transactions)")
    mo.vstack(
        [
            mo.md(
                """
                ## 1.7 Verify Privileges with a Diagnostic Table (`lab.connection_probe`)

                Each test below opens an isolated connection, enters `conn.transaction(force_rollback=True)` so no test writes or accidental DDL ever persist, verifies whether the operation is **Allowed** or **Denied (`42501`)**, and closes the connection in `finally:`.
                """
            ),
            priv_button,
        ]
    )
    return (priv_button,)


@app.cell
def _(lab_config, mo, priv_button, run_privilege_test_suite):
    if not priv_button.value:
        priv_result = None
        _priv_view = mo.callout(
            mo.md("Access-control tests have not been executed yet. Click **Run access-control tests** above to verify `course_app` and `course_analyst` permissions."),
            kind="neutral",
        )
    else:
        priv_result = run_privilege_test_suite(lab_config)
        _priv_view = mo.vstack(
            [
                mo.callout(
                    mo.md(
                        "**All 6 privilege boundary tests passed** (`course_app` read/write allowed, `course_analyst` read-only enforced, unauthorized schema/table DDL rejected, and all connections closed)."
                        if priv_result["ok"]
                        else f"**Privilege test suite failed or incomplete:** {priv_result.get('error', 'Review failed rows below.')}"
                    ),
                    kind="success" if priv_result["ok"] else "danger",
                ),
                mo.ui.table(priv_result["tests"], selection=None)
                if priv_result["tests"]
                else mo.md(""),
            ]
        )
    _priv_view
    return (priv_result,)


@app.cell
def _(classify_db_error, mo):
    fault_selector = mo.ui.dropdown(
        options=[
            "Connection refused (wrong port 59999)",
            "Authentication failed (SQLSTATE 28P01)",
            "Database does not exist (SQLSTATE 3D000)",
            "Permission denied for schema commerce (SQLSTATE 42501)",
            "Permission denied for table connection_probe (SQLSTATE 42501)",
            "Relation does not exist — unqualified connection_probe (SQLSTATE 42P01)",
        ],
        value="Relation does not exist — unqualified connection_probe (SQLSTATE 42P01)",
        label="Simulate a single configuration or SQL fault:",
    )

    class _SimulatedPGError(Exception):
        def __init__(self, message: str, sqlstate: str = ""):
            super().__init__(message)
            self.sqlstate = sqlstate

    _sample_secret = "super_secret_lab_password_123"
    _simulated_map = {
        "Connection refused (wrong port 59999)": _SimulatedPGError(
            f"connection to server at '127.0.0.1', port 59999 failed: Connection refused (password={_sample_secret})"
        ),
        "Authentication failed (SQLSTATE 28P01)": _SimulatedPGError(
            f'FATAL: password authentication failed for user "course_app" using password={_sample_secret}',
            "28P01",
        ),
        "Database does not exist (SQLSTATE 3D000)": _SimulatedPGError(
            'FATAL: database "goliath_wrong_db" does not exist',
            "3D000",
        ),
        "Permission denied for schema commerce (SQLSTATE 42501)": _SimulatedPGError(
            "ERROR: permission denied for schema commerce",
            "42501",
        ),
        "Permission denied for table connection_probe (SQLSTATE 42501)": _SimulatedPGError(
            "ERROR: permission denied for table connection_probe",
            "42501",
        ),
        "Relation does not exist — unqualified connection_probe (SQLSTATE 42P01)": _SimulatedPGError(
            'ERROR: relation "connection_probe" does not exist',
            "42P01",
        ),
    }
    _sim_diag = classify_db_error(_simulated_map[fault_selector.value], [_sample_secret])

    mo.vstack(
        [
            mo.md(
                """
                ## 1.8 Troubleshooting as a Diagnostic Sequence

                Classify failures by their connection stage and SQLSTATE before changing settings. Never grant `SUPERUSER` or `GRANT ALL` to mask a namespace or privilege error.
                """
            ),
            fault_selector,
            mo.ui.table([_sim_diag], selection=None),
        ]
    )
    return (fault_selector,)


@app.cell
def _(
    Path,
    classify_db_error,
    datetime,
    dependency_status,
    diag_result,
    json,
    lab_config,
    load_lab_config,
    mo,
    priv_result,
    redact_text,
    timezone,
):
    # Built-in self-checks for configuration validation and secret redaction (always safe, no DB connection)
    _bad_port_cfg = load_lab_config(Path("."), overrides={"PGPORT": "99999", "COURSE_APP_PASSWORD": "pw1", "COURSE_ANALYST_PASSWORD": "pw2"})
    _redaction_probe = redact_text(
        "postgresql://course_app:my_secret_pw@127.0.0.1:54329/goliath_ecommerce password=my_secret_pw",
        ["my_secret_pw"],
    )
    _self_tests_ok = (not _bad_port_cfg["valid"]) and ("my_secret_pw" not in _redaction_probe) and ("[REDACTED]" in _redaction_probe)

    _deps_ok = all(bool(d["installed"]) for d in dependency_status)
    _diag_ok = bool(diag_result and diag_result.get("ok"))
    _schemas_found = {s["schema_name"]: s["owner_role"] for s in (diag_result.get("schemas", []) if diag_result else [])}
    _schemas_ok = _schemas_found.get("commerce") == "course_owner" and _schemas_found.get("lab") == "course_owner"
    _priv_tests = {t["test_id"]: bool(t["passed"]) for t in (priv_result.get("tests", []) if priv_result else [])}
    _app_rw_ok = _priv_tests.get(1, False) and _priv_tests.get(2, False)
    _analyst_ro_ok = _priv_tests.get(3, False) and _priv_tests.get(4, False)
    _owner_ddl_rejected = _priv_tests.get(5, False) and _priv_tests.get(6, False)
    _all_closed = (
        all(bool(s.get("connection_closed")) for s in (diag_result.get("sessions", []) if diag_result else []))
        and all(bool(t.get("connection_closed")) for t in (priv_result.get("tests", []) if priv_result else []))
        and (_diag_ok or _priv_tests != {})
    )

    readiness_rows = [
        {"check": "1. Required Python packages available (marimo, psycopg, python-dotenv)", "passed": _deps_ok, "detail": "All installed" if _deps_ok else "Missing package(s)"},
        {"check": "2. Configuration validator & secret redactor self-tests", "passed": _self_tests_ok, "detail": "Invalid port rejected; passwords redacted"},
        {"check": "3. Server reachable", "passed": _diag_ok, "detail": f"Connected to {lab_config['host']}:{lab_config['port']}" if _diag_ok else "Run connection diagnostics"},
        {"check": "4. Server version recorded", "passed": bool(diag_result and diag_result.get("server_version")), "detail": str(diag_result.get("server_version")) if diag_result and diag_result.get("server_version") else "Pending connection"},
        {"check": "5. Intended database and login identities verified", "passed": _diag_ok, "detail": f"Database={lab_config['database']}, roles={lab_config['app_user']}, {lab_config['analyst_user']}" if _diag_ok else "Pending connection"},
        {"check": "6. Expected schemas (commerce, lab) present and owned by course_owner", "passed": _schemas_ok, "detail": f"Found: {_schemas_found}" if _schemas_found else "Pending connection"},
        {"check": "7. Application probe read/write successful (rollback-only)", "passed": _app_rw_ok, "detail": "Tests 1 & 2 passed" if _app_rw_ok else "Run access-control tests"},
        {"check": "8. Analyst read successful and write rejected (42501)", "passed": _analyst_ro_ok, "detail": "Tests 3 & 4 passed" if _analyst_ro_ok else "Run access-control tests"},
        {"check": "9. Owner-only DDL rejected for application role (42501)", "passed": _owner_ddl_rejected, "detail": "Tests 5 & 6 passed" if _owner_ddl_rejected else "Run access-control tests"},
        {"check": "10. Connections closed after checks", "passed": _all_closed, "detail": "All connections verified closed" if _all_closed else "Pending test execution"},
    ]

    _overall_ready = all(bool(r["passed"]) for r in readiness_rows)
    _report_payload = {
        "course": "PostgreSQL with Python: Analytics, ORM, and Database Applications",
        "module": "Module 1: PostgreSQL Environment, Connections & Access Control",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_ready_for_module_2": _overall_ready,
        "configuration": {row["field"]: row["value"] for row in lab_config["redacted_summary"]},
        "dependencies": dependency_status,
        "server_version": diag_result.get("server_version") if diag_result else None,
        "schemas": diag_result.get("schemas", []) if diag_result else [],
        "readiness_checks": readiness_rows,
        "privilege_tests": priv_result.get("tests", []) if priv_result else [],
    }
    report_bytes = json.dumps(_report_payload, indent=2).encode("utf-8")

    mo.vstack(
        [
            mo.md(
                """
                ## 1.9 Readiness Report and Practical Assessment

                Once all checks below pass, download the secret-free JSON readiness report to complete Module 1 and proceed to **Module 2: Migrating the E-Commerce Database from SQLite to PostgreSQL**.
                """
            ),
            mo.ui.table(readiness_rows, selection=None),
            mo.callout(
                mo.md(
                    "**Environment Ready for Module 2:** All connectivity, schema, role-separation, and rollback-only privilege checks passed."
                    if _overall_ready
                    else "Complete both **Run connection diagnostics** (Section 1.6) and **Run access-control tests** (Section 1.7) against your provisioned PostgreSQL instance so all 10 readiness checks pass."
                ),
                kind="success" if _overall_ready else "warn",
            ),
            mo.download(
                data=report_bytes,
                filename="module_01_readiness_report.json",
                mimetype="application/json",
                label="Download secret-free readiness report (JSON)",
            ),
            mo.md(
                """
                ### Student Submission & Assessment Rubric
                - **Reproducible setup and lifecycle (25%):** Secret-free configuration summary and restart instructions that preserve data (`docker compose stop` / `start` vs. `down -v`).
                - **Safe configuration and Python connectivity (25%):** Verified `course_app` and `course_analyst` connections with finite timeouts and explicit connection closure.
                - **Role separation and privilege tests (30%):** Explanation of the four roles (`course_owner`, `course_migrator`, `course_app`, `course_analyst`) plus evidence of allowed and denied (`42501`) operations.
                - **Diagnostics and documentation (20%):** Completed readiness report and troubleshooting note.
                """
            ),
        ]
    )
    return readiness_rows, report_bytes


if __name__ == "__main__":
    app.run()
