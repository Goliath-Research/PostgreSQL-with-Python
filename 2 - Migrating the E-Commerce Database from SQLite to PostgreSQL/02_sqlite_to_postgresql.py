# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo>=0.11,<1", "psycopg[binary]>=3.2,<4", "python-dotenv>=1,<2"]
# ///

import marimo

app = marimo.App(width="medium", app_title="Module 2: SQLite to PostgreSQL Migration")


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
    import json
    from pathlib import Path
    import marimo as mo
    return Path, json, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md('# Module 2: SQLite to PostgreSQL Migration\n## Goliath Research Academy — PostgreSQL with Python\n\nThis initial executable draft migrates the six-table database from the first course.\nIt uses direct sqlite3/Psycopg access; DuckDB 2.0 analytics and SQLAlchemy persistence come later.\nOpening the notebook requests your lab database if you do not already have one. It does not connect on its own, build a source database, or change source files.\n\n### Before opening\nInstall the notebook dependencies in your Python environment. Place this file in\n`2 - Migrating the E-Commerce Database from SQLite to PostgreSQL/` in the course repository. Create a NEW baseline bundle\nexplicitly from the repository root if you do not already have an authorized live snapshot:\n\n```bash\npython "2 - Migrating the E-Commerce Database from SQLite to PostgreSQL/fixtures/intro_ecommerce/8 - Python Database Integration & Capstone/ecommerce_snapshot.py" rebuild "2 - Migrating the E-Commerce Database from SQLite to PostgreSQL/fixtures/intro_ecommerce/baseline_bundle"\n```\n\nThe fixture contains only SQLite migration inputs used to build the sample source database; it is not a copy of the introductory course or a backup of student work. The builder refuses an existing destination. A rebuilt baseline is not a saved end-of-course session.\nModule 1\'s actual server/role checks must pass; merging a PR or seeing pg_isready is insufficient.\nThis notebook does not repair PostgreSQL volume layout, bootstrap roles, or rotate credentials.\n\n### Safety boundary\nThe draft supports only the exact pinned Module 8 core schema and its indexes. Module 3 staging tables,\nadditional views/triggers/indexes, or redesigned source schemas are blocked rather than silently omitted.\nIt is a small classroom loader (64 MiB snapshot limit), not a production migration framework.\nPostgreSQL and the Marimo UI still require integration testing before teaching.\n')
    return


@app.cell
def _():
    def build_migration_api():
        """Core is kept in one cell so the draft is a self-contained Marimo notebook."""
        import hashlib
        import json
        import os
        import re
        import sqlite3
        import uuid
        from datetime import datetime
        from decimal import Decimal
        from pathlib import Path
        from types import SimpleNamespace

        TABLES = ("customers", "products", "warehouses", "orders", "order_items", "catalog_observations")
        COLUMNS = {
            "customers": ("customer_id", "email", "customer_name"),
            "products": ("sku", "product_name", "category"),
            "warehouses": ("warehouse_code", "warehouse_city"),
            "orders": ("order_id", "ordered_at", "order_status", "customer_id", "shipping_address_snapshot"),
            "order_items": ("source_row_id", "order_id", "line_no", "sku", "warehouse_code", "unit_price_cents", "quantity"),
            "catalog_observations": ("source_row_id", "sku", "warehouse_code", "observed_price_cents", "observed_quantity"),
        }
        KEYS = {t: COLUMNS[t][0] for t in TABLES}
        RENAMES = {"order_items": {"source_row_id": "order_item_id"},
                   "catalog_observations": {"source_row_id": "observation_id"}}
        IDENTITIES = {"customers": "customer_id", "order_items": "order_item_id", "catalog_observations": "observation_id"}
        INTEGERS = {"customer_id", "source_row_id", "line_no", "unit_price_cents", "quantity", "observed_price_cents", "observed_quantity"}
        SIGNATURE = "0653ff1441f8303cd2b1e3214dd3bf9880c1d0883bf96be3f1c5ee1b31192797"
        MANIFEST_KEYS = {"contract_version", "snapshot_kind", "created_at", "source_repository", "exporter_commit", "source_commit", "source_csv_sha256", "database_sha256", "sqlite_version", "table_counts", "schema_signature", "objects"}
        ADAPTER = "module8-six-table-v1"

        class MigrationError(ValueError):
            pass

        def require(condition, message):
            if not condition:
                raise MigrationError(message)

        def quote(name):
            return '"' + name.replace('"', '""') + '"'

        def target_columns(table):
            return tuple(RENAMES.get(table, {}).get(c, c) for c in COLUMNS[table])

        def canonical(value):
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(value, Decimal):
                require(value.is_finite() and value == value.to_integral_value(), "Nonintegral target cent value")
                return int(value)
            return value

        def digest_rows(rows):
            encoded = sorted(json.dumps([canonical(v) for v in row], ensure_ascii=False, separators=(",", ":"), allow_nan=False) for row in rows)
            return hashlib.sha256("\n".join(encoded).encode("utf-8")).hexdigest()

        def bounded_read(path, limit):
            with Path(path).open("rb") as stream:
                data = stream.read(limit + 1)
            require(len(data) <= limit, "This classroom draft's input-size limit was exceeded")
            return data

        def error_summary(exc):
            # Deliberately exclude raw driver messages, row values, DSNs, and passwords.
            return {"type": type(exc).__name__, "sqlstate": getattr(exc, "sqlstate", None),
                    "hint": "Check the documented source profile, integrity, credentials, privileges, and target state. Raw exception text is redacted."}

        def timestamp(value):
            require(isinstance(value, str), "Expected a timezone-free textual timestamp")
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError as exc:
                raise MigrationError("Use source timestamps in YYYY-MM-DD HH:MM:SS form; no zone is inferred") from exc
            require(parsed.strftime("%Y-%m-%d %H:%M:%S") == value, "Noncanonical source timestamp")
            return parsed

        def normalize(table, row):
            output = []
            for column, value in zip(COLUMNS[table], row):
                if column == "ordered_at":
                    value = timestamp(value)
                elif column in INTEGERS:
                    require(type(value) is int and -(2**63) <= value < 2**63, "Expected a signed BIGINT-compatible source integer")
                else:
                    require(isinstance(value, str), "Expected a non-NULL textual source value")
                output.append(value)
            return tuple(output)

        def expected_reports(rows):
            records = {t: [dict(zip(COLUMNS[t], row)) for row in rows[t]] for t in TABLES}
            customers = {r["customer_id"]: r for r in records["customers"]}
            products = {r["sku"]: r for r in records["products"]}
            warehouses = {r["warehouse_code"]: r for r in records["warehouses"]}
            orders = {r["order_id"]: r for r in records["orders"]}
            totals = {oid: [0, None] for oid in orders}
            lines, reconstructed = [], []
            for item in records["order_items"]:
                order = orders[item["order_id"]]
                customer = customers[order["customer_id"]]
                product = products[item["sku"]]
                warehouse = warehouses[item["warehouse_code"]]
                amount = item["unit_price_cents"] * item["quantity"]
                totals[item["order_id"]][0] += 1
                totals[item["order_id"]][1] = (totals[item["order_id"]][1] or 0) + amount
                lines.append((item["source_row_id"], order["order_id"], order["ordered_at"], order["order_status"],
                              order["customer_id"], customer["email"], customer["customer_name"], order["shipping_address_snapshot"],
                              item["line_no"], item["sku"], product["product_name"], product["category"],
                              item["warehouse_code"], warehouse["warehouse_city"], item["unit_price_cents"], item["quantity"], amount))
                reconstructed.append((item["source_row_id"], order["order_id"], order["ordered_at"], order["order_status"],
                                      customer["email"], customer["customer_name"], order["shipping_address_snapshot"],
                                      item["warehouse_code"], warehouse["warehouse_city"], item["sku"],
                                      product["product_name"], product["category"], item["unit_price_cents"], item["quantity"]))
            for item in records["catalog_observations"]:
                product = products[item["sku"]]
                warehouse = warehouses[item["warehouse_code"]]
                reconstructed.append((item["source_row_id"], None, None, None, None, None, None,
                                      item["warehouse_code"], warehouse["warehouse_city"], item["sku"], product["product_name"],
                                      product["category"], item["observed_price_cents"], item["observed_quantity"]))
            headers = [(o["order_id"], o["ordered_at"], o["order_status"], customers[o["customer_id"]]["email"], *totals[o["order_id"]]) for o in orders.values()]
            return {"v_order_lines": lines, "v_order_totals": headers, "reconstructed_flat": reconstructed}

        def load_source(bundle):
            bundle = Path(bundle).expanduser().resolve()
            manifest_bytes = bounded_read(bundle / "source_manifest.json", 2 * 1024 * 1024)
            manifest = json.loads(manifest_bytes)
            require(isinstance(manifest, dict) and set(manifest) == MANIFEST_KEYS, "Unsupported manifest fields/version")
            require(manifest["contract_version"] == "goliath-ecommerce-snapshot/v1", "Unsupported snapshot contract")
            require(manifest["snapshot_kind"] in ("baseline_rebuilt", "live_connection"), "Unsupported snapshot kind")
            require(manifest["source_repository"] == "Goliath-Research/Introduction-to-Databases", "Unexpected source repository")
            for key, length in (("database_sha256", 64), ("schema_signature", 64), ("source_csv_sha256", 64), ("source_commit", 40), ("exporter_commit", 40)):
                value = manifest[key]
                require((value is None and key not in ("database_sha256", "schema_signature")) or
                        (isinstance(value, str) and re.fullmatch("[0-9a-f]{" + str(length) + "}", value)), "Invalid manifest digest/revision")
            require(isinstance(manifest["sqlite_version"], str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", manifest["sqlite_version"]), "Invalid SQLite version metadata")
            require(isinstance(manifest["created_at"], str), "Invalid creation timestamp metadata")
            try:
                created = datetime.fromisoformat(manifest["created_at"])
                require(created.tzinfo is not None and created.utcoffset().total_seconds() == 0, "Manifest creation time must be UTC")
            except (ValueError, TypeError) as exc:
                raise MigrationError("Invalid creation timestamp metadata") from exc
            database_path = bundle / "ecommerce_source.sqlite"
            wal = Path(str(database_path) + "-wal")
            require(not wal.exists() or wal.stat().st_size == 0, "Use a completed self-contained backup bundle, not an active WAL database")
            data = bounded_read(database_path, 64 * 1024 * 1024)
            require(hashlib.sha256(data).hexdigest() == manifest["database_sha256"], "Snapshot checksum mismatch")
            db = sqlite3.connect(":memory:")
            try:
                require(hasattr(db, "deserialize"), "This Python/SQLite build lacks deserialize support")
                db.deserialize(data)
                db.execute("PRAGMA query_only=ON")
                require(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "Source integrity failed")
                require(not db.execute("PRAGMA foreign_key_check").fetchall(), "Source foreign-key violations")
                inventory = [dict(zip(("type", "name", "table", "sql"), row)) for row in db.execute(
                    "SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE type IN ('table','view','index','trigger') ORDER BY type,name")]
                actual_signature = hashlib.sha256(json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                require(inventory == manifest["objects"] and actual_signature == manifest["schema_signature"], "Manifest/object inventory mismatch")
                require(actual_signature == SIGNATURE, "Unsupported schema profile: only the pinned Module 8 core schema is writable in this draft")
                rows = {t: tuple(normalize(t, r) for r in db.execute("SELECT " + ",".join(map(quote, COLUMNS[t])) + " FROM " + quote(t))) for t in TABLES}
                counts = {t: len(rows[t]) for t in TABLES}
                require(isinstance(manifest["table_counts"], dict) and set(manifest["table_counts"]) == set(TABLES), "Invalid manifest table counts")
                require(all(type(n) is int and n >= 0 for n in manifest["table_counts"].values()), "Invalid manifest count type")
                require(counts == manifest["table_counts"], "Source row counts differ from manifest")
            finally:
                db.close()
            token = hashlib.sha256(data + manifest_bytes).hexdigest()
            reports = expected_reports(rows)
            return {"bundle": str(bundle), "manifest": manifest, "token": token, "rows": rows,
                    "counts": counts, "row_hashes": {t: digest_rows(rows[t]) for t in TABLES},
                    "report_hashes": {v: digest_rows(r) for v, r in reports.items()},
                    "line_total_cents": sum(r[-1] for r in reports["v_order_lines"])}

        class Config:
            def __init__(self, public, passwords):
                self.public = public
                self.passwords = passwords
                self.nonce = uuid.uuid4().hex
            def __repr__(self):
                return "<PostgreSQL configuration: credentials redacted>"

        def load_config(env_path):
            values = {}
            if Path(env_path).is_file():
                from dotenv import dotenv_values
                values.update(dotenv_values(env_path, interpolate=False))
            values.update(os.environ)
            def value(name, default=""):
                item = values.get(name, default)
                return default if item is None else str(item)
            try:
                port = int(value("PGPORT", "54329"))
                timeout = int(value("PGCONNECT_TIMEOUT", "5"))
            except ValueError as exc:
                raise MigrationError("Invalid port/connection-timeout configuration") from exc
            require(1 <= port <= 65535 and 1 <= timeout <= 30, "Invalid port/connection-timeout range")
            require(value("PGDATABASE", "goliath_ecommerce") == "goliath_ecommerce", "This draft targets the course database only")
            require(bool(value("PGHOST", "127.0.0.1").strip()), "Missing PostgreSQL host")
            mode = value("PGSSLMODE", "prefer")
            require(mode in ("disable", "allow", "prefer", "require", "verify-ca", "verify-full"), "Invalid TLS policy")
            passwords = {}
            for role in ("migrator", "app", "analyst"):
                require(value("COURSE_" + role.upper() + "_USER", "course_" + role) == "course_" + role, "Unexpected course role name")
                password = value("COURSE_" + role.upper() + "_PASSWORD")
                require(bool(password) and not password.startswith("REPLACE_"), "Configure the three course role credentials")
                passwords[role] = password
            return Config({"host": value("PGHOST", "127.0.0.1"), "port": port, "database": "goliath_ecommerce",
                           "timeout": timeout, "sslmode": mode, "sslrootcert": value("PGSSLROOTCERT")}, passwords)

        def connect(config, role):
            require(role in ("migrator", "app", "analyst"), "Unknown connection identity")
            import psycopg
            p = config.public
            kwargs = dict(host=p["host"], port=p["port"], dbname=p["database"], user="course_" + role,
                          password=config.passwords[role], connect_timeout=p["timeout"], sslmode=p["sslmode"],
                          autocommit=True, application_name="goliath_module_02",
                          options="-c statement_timeout=10000 -c lock_timeout=3000")
            if p["sslrootcert"]:
                kwargs["sslrootcert"] = p["sslrootcert"]
            return psycopg.connect(**kwargs)

        def guard_target(conn):
            require(conn.execute("SELECT current_database(),session_user,current_user").fetchone() ==
                    ("goliath_ecommerce", "course_migrator", "course_migrator"), "Unexpected migration database/login/effective identity")
            require(180000 <= conn.info.server_version < 200000, "This draft requires PostgreSQL 19 (or 18)")
            for role in ("course_migrator", "course_app", "course_analyst", "course_owner"):
                flags = conn.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolcanlogin FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
                require(flags is not None and not any(flags[:5]) and flags[5] == (role != "course_owner"), "Unexpected administrative attributes/login flags")
            for role in ("course_app", "course_analyst"):
                member = conn.execute("SELECT pg_has_role(%s,%s,'MEMBER') OR pg_has_role(%s,%s,'MEMBER')", (role, "course_owner", role, "course_migrator")).fetchone()[0]
                require(not member, "Ordinary role has ownership/migration membership")
            require(conn.execute("SELECT rolinherit FROM pg_roles WHERE rolname='course_migrator'").fetchone() == (False,), "Migrator must assume ownership explicitly")
            owner = conn.execute("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='commerce'").fetchone()
            require(owner == ("course_owner",), "Module 1 must create commerce owned by course_owner")
            existing = conn.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='commerce'").fetchall()
            require(not existing, "commerce is occupied; no overwrite, reset, or rerun is performed")
            conn.execute("SET LOCAL ROLE course_owner")
            require(conn.execute("SELECT current_user").fetchone() == ("course_owner",), "Owner-role assumption failed")

        def approval_token(plan, config):
            return hashlib.sha256((plan["token"] + config.nonce).encode()).hexdigest()

        def preflight(plan, config):
            with connect(config, "migrator") as conn:
                with conn.transaction():
                    conn.execute("SET TRANSACTION READ ONLY")
                    guard_target(conn)
            return {"ready": True, "approval_token": approval_token(plan, config), "target": dict(config.public)}

        DDL = [
            "CREATE TABLE commerce.customers(customer_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,email TEXT NOT NULL UNIQUE,customer_name TEXT NOT NULL)",
            "CREATE TABLE commerce.products(sku TEXT PRIMARY KEY,product_name TEXT NOT NULL,category TEXT NOT NULL)",
            "CREATE TABLE commerce.warehouses(warehouse_code TEXT PRIMARY KEY,warehouse_city TEXT NOT NULL)",
            "CREATE TABLE commerce.orders(order_id TEXT PRIMARY KEY,ordered_at TIMESTAMP(0) WITHOUT TIME ZONE NOT NULL,order_status TEXT NOT NULL,customer_id BIGINT NOT NULL REFERENCES commerce.customers(customer_id) ON DELETE RESTRICT,shipping_address_snapshot TEXT NOT NULL)",
            "CREATE TABLE commerce.order_items(order_item_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,order_id TEXT NOT NULL REFERENCES commerce.orders(order_id) ON DELETE RESTRICT,line_no BIGINT NOT NULL CHECK(line_no>0),sku TEXT NOT NULL REFERENCES commerce.products(sku) ON DELETE RESTRICT,warehouse_code TEXT NOT NULL REFERENCES commerce.warehouses(warehouse_code) ON DELETE RESTRICT,unit_price_cents BIGINT NOT NULL CHECK(unit_price_cents>=0),quantity BIGINT NOT NULL CHECK(quantity>0),UNIQUE(order_id,line_no))",
            "CREATE TABLE commerce.catalog_observations(observation_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,sku TEXT NOT NULL REFERENCES commerce.products(sku) ON DELETE RESTRICT,warehouse_code TEXT NOT NULL REFERENCES commerce.warehouses(warehouse_code) ON DELETE RESTRICT,observed_price_cents BIGINT NOT NULL CHECK(observed_price_cents>=0),observed_quantity BIGINT NOT NULL CHECK(observed_quantity>=0))",
            "CREATE INDEX orders_customer_idx ON commerce.orders(customer_id)",
            "CREATE INDEX items_sku_idx ON commerce.order_items(sku)",
            "CREATE TABLE commerce.migration_runs(migration_id TEXT PRIMARY KEY,adapter TEXT NOT NULL,snapshot_sha256 TEXT NOT NULL,applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,source_manifest JSONB NOT NULL,validation JSONB NOT NULL)",
            "CREATE TABLE commerce.migration_row_map(migration_id TEXT NOT NULL REFERENCES commerce.migration_runs(migration_id),source_table TEXT NOT NULL,source_key JSONB NOT NULL,target_table TEXT NOT NULL,target_key JSONB NOT NULL,PRIMARY KEY(migration_id,source_table,source_key))",
            """CREATE VIEW commerce.v_order_lines AS
               SELECT i.order_item_id,o.order_id,o.ordered_at,o.order_status,o.customer_id,c.email,c.customer_name,
                      o.shipping_address_snapshot,i.line_no,i.sku,p.product_name,p.category,i.warehouse_code,
                      w.warehouse_city,i.unit_price_cents,i.quantity,i.unit_price_cents::numeric*i.quantity::numeric AS line_amount_cents
               FROM commerce.order_items i JOIN commerce.orders o USING(order_id)
               JOIN commerce.customers c USING(customer_id) JOIN commerce.products p USING(sku)
               JOIN commerce.warehouses w USING(warehouse_code)""",
            """CREATE VIEW commerce.v_order_totals AS
               SELECT o.order_id,o.ordered_at,o.order_status,c.email,COUNT(i.order_item_id) AS line_count,
                      SUM(i.unit_price_cents::numeric*i.quantity::numeric) AS amount_cents
               FROM commerce.orders o JOIN commerce.customers c USING(customer_id)
               LEFT JOIN commerce.order_items i USING(order_id)
               GROUP BY o.order_id,o.ordered_at,o.order_status,c.email""",
            """CREATE VIEW commerce.reconstructed_flat AS
               SELECT order_item_id AS row_id,order_id,ordered_at,order_status,email AS customer_email,customer_name,
                      shipping_address_snapshot AS shipping_address,warehouse_code,warehouse_city,sku,product_name,category,unit_price_cents,quantity
               FROM commerce.v_order_lines
               UNION ALL
               SELECT x.observation_id,NULL,NULL,NULL,NULL,NULL,NULL,x.warehouse_code,w.warehouse_city,x.sku,
                      p.product_name,p.category,x.observed_price_cents,x.observed_quantity
               FROM commerce.catalog_observations x JOIN commerce.products p USING(sku)
               JOIN commerce.warehouses w USING(warehouse_code)""",
        ]

        def validate_target(conn, plan):
            checks = []
            for table in TABLES:
                values = conn.execute("SELECT " + ",".join(map(quote, target_columns(table))) + " FROM commerce." + quote(table)).fetchall()
                checks.append({"check": "rows:" + table, "passed": len(values) == plan["counts"][table] and digest_rows(values) == plan["row_hashes"][table]})
            for view, expected in plan["report_hashes"].items():
                values = conn.execute("SELECT * FROM commerce." + quote(view)).fetchall()
                checks.append({"check": "report:" + view, "passed": digest_rows(values) == expected})
            return checks

        def assess_roles(config, plan):
            results = []
            for role in ("app", "analyst"):
                try:
                    with connect(config, role) as conn:
                        with conn.transaction():
                            conn.execute("SET TRANSACTION READ ONLY")
                            actual = conn.execute("SELECT current_database(),session_user,current_user").fetchone()
                            results.append({"check": role + ":identity", "passed": actual == ("goliath_ecommerce", "course_" + role, "course_" + role)})
                            results.extend({"check": role + ":" + r["check"], "passed": r["passed"]} for r in validate_target(conn, plan))
                            for table in TABLES:
                                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                                    allowed = conn.execute("SELECT has_table_privilege(current_user,%s,%s)", ("commerce." + table, privilege)).fetchone()[0]
                                    results.append({"check": role + ":" + table + ":" + privilege, "passed": allowed == (role == "app" or privilege == "SELECT")})
                        try:
                            with conn.transaction(force_rollback=True):
                                conn.execute("UPDATE commerce.orders SET order_status=order_status WHERE FALSE")
                            results.append({"check": role + ":actual UPDATE authorization", "passed": role == "app"})
                        except Exception as exc:
                            results.append({"check": role + ":actual UPDATE authorization", "passed": role == "analyst" and getattr(exc, "sqlstate", None) == "42501"})
                except Exception as exc:
                    results.append({"check": role + ":post-commit connection/verification", "passed": False, "error": error_summary(exc)})
            return results

        def migrate(plan, config, approval, phrase, fail_after=None):
            require(phrase == "MIGRATE commerce", "Type the exact authorization phrase")
            require(approval == approval_token(plan, config), "Approval is stale or targets another configuration")
            require(fail_after is None or fail_after in TABLES, "Unknown failure-injection point")
            fresh = load_source(plan["bundle"])
            require(fresh["token"] == plan["token"], "Source changed after preview; inspect and authorize again")
            plan = fresh
            run_id = uuid.uuid4().hex
            outcome = {"migration_id": run_id, "commit_state": "not_started", "ready_for_module_3": False,
                       "snapshot_sha256": plan["manifest"]["database_sha256"], "adapter": ADAPTER}
            conn = None
            phase = "connect"
            try:
                conn = connect(config, "migrator")
                conn.execute("BEGIN")
                phase = "transaction"
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (2700254002,))
                guard_target(conn)
                for statement in DDL:
                    conn.execute(statement)
                conn.execute("INSERT INTO commerce.migration_runs(migration_id,adapter,snapshot_sha256,source_manifest,validation) VALUES(%s,%s,%s,%s::jsonb,%s::jsonb)",
                             (run_id, ADAPTER, plan["manifest"]["database_sha256"], json.dumps(plan["manifest"]), '{"status":"loading"}'))
                for table in TABLES:
                    columns = target_columns(table)
                    statement = "INSERT INTO commerce." + quote(table) + "(" + ",".join(map(quote, columns)) + ") VALUES(" + ",".join(["%s"] * len(columns)) + ")"
                    with conn.cursor() as cursor:
                        if plan["rows"][table]:
                            cursor.executemany(statement, plan["rows"][table])
                    mappings = [(run_id, table, json.dumps({KEYS[table]: row[0]}), table, json.dumps({columns[0]: row[0]})) for row in plan["rows"][table]]
                    if mappings:
                        with conn.cursor() as cursor:
                            cursor.executemany("INSERT INTO commerce.migration_row_map VALUES(%s,%s,%s::jsonb,%s,%s::jsonb)", mappings)
                    if fail_after == table:
                        raise MigrationError("Intentional failure injection")
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                validation = validate_target(conn, plan)
                require(all(check["passed"] for check in validation), "Data or report reconciliation failed")
                mapped = conn.execute("SELECT COUNT(*) FROM commerce.migration_row_map WHERE migration_id=%s", (run_id,)).fetchone()[0]
                require(mapped == sum(plan["counts"].values()), "Source-to-target key-map accounting failed")
                for table, key in IDENTITIES.items():
                    maximum = conn.execute("SELECT MAX(" + quote(key) + ") FROM commerce." + quote(table)).fetchone()[0]
                    base = max(1, maximum or 0)
                    conn.execute("SELECT setval(pg_get_serial_sequence(%s,%s),%s,%s)", ("commerce." + table, key, base, bool(maximum is not None and maximum >= 1)))
                conn.execute("GRANT USAGE ON SCHEMA commerce TO course_app,course_analyst")
                for table in TABLES:
                    conn.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON commerce." + quote(table) + " TO course_app")
                    conn.execute("GRANT SELECT ON commerce." + quote(table) + " TO course_analyst")
                for table, key in IDENTITIES.items():
                    conn.execute("GRANT USAGE,SELECT ON SEQUENCE commerce." + quote(table + "_" + key + "_seq") + " TO course_app")
                for view in plan["report_hashes"]:
                    conn.execute("GRANT SELECT ON commerce." + quote(view) + " TO course_app,course_analyst")
                conn.execute("GRANT SELECT ON commerce.migration_runs,commerce.migration_row_map TO course_app,course_analyst")
                conn.execute("UPDATE commerce.migration_runs SET validation=%s::jsonb WHERE migration_id=%s", (json.dumps(validation), run_id))
                phase = "commit"
                conn.execute("COMMIT")
                outcome.update(commit_state="committed", validation=validation, counts=plan["counts"], line_total_cents=plan["line_total_cents"])
            except Exception as exc:
                outcome["error"] = error_summary(exc)
                if phase == "commit":
                    outcome["commit_state"] = "unknown"
                elif phase == "transaction":
                    try:
                        conn.execute("ROLLBACK")
                        outcome["commit_state"] = "rolled_back"
                    except Exception:
                        outcome["commit_state"] = "unknown"
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        outcome["cleanup_warning"] = "Connection close did not complete normally"
            if outcome["commit_state"] == "committed":
                try:
                    outcome["ordinary_role_checks"] = assess_roles(config, plan)
                    outcome["ready_for_module_3"] = bool(outcome["ordinary_role_checks"]) and all(c["passed"] for c in outcome["ordinary_role_checks"])
                except Exception as exc:
                    outcome["post_commit_error"] = error_summary(exc)
            if outcome["commit_state"] == "unknown":
                outcome["recovery"] = "Do not retry loading blindly. Inspect commerce.migration_runs for this migration_id and verify target data using a new authorized connection."
            return outcome

        return SimpleNamespace(load_source=load_source, load_config=load_config, preflight=preflight,
                               migrate=migrate, assess_roles=assess_roles, error_summary=error_summary,
                               expected_reports=expected_reports, digest_rows=digest_rows, timestamp=timestamp,
                               normalize=normalize, target_columns=target_columns, approval_token=approval_token,
                               validate_target=validate_target, guard_target=guard_target, tables=TABLES,
                               columns=COLUMNS, ddl=DDL, MigrationError=MigrationError, Config=Config,
                               signature=SIGNATURE)

    return (build_migration_api,)


@app.cell
def _(build_migration_api):
    migration = build_migration_api()
    return (migration,)


@app.cell
def _(Path):
    module_dir = Path(__file__).resolve().parent
    repo_root = module_dir.parent
    return module_dir, repo_root


@app.cell(hide_code=True)
def _(mo):
    mo.md('## 2.1 Inspect a completed source snapshot\nThe bundle must contain ecommerce_source.sqlite and source_manifest.json under contract\n`goliath-ecommerce-snapshot/v1`. Both baseline_rebuilt and live_connection are supported when the\nactual schema matches. Counts are read from the snapshot, not assumed to be the original fixture counts.\nThe source artifact is read into one immutable byte buffer; checksum verification and inspection use\nthose same bytes, avoiding a separate unchecked reopen. No source SQL is executed in PostgreSQL.\n')
    return


@app.cell
def _(mo, repo_root):
    source_form = mo.ui.dictionary({
        "bundle": mo.ui.text(value=str(repo_root / "2 - Migrating the E-Commerce Database from SQLite to PostgreSQL" / "fixtures" / "intro_ecommerce" / "baseline_bundle"), label="Authorized snapshot-bundle directory", full_width=True),
        "inspect": mo.ui.checkbox(value=False, label="Inspect this local snapshot; no PostgreSQL connection"),
    }).form()
    source_form
    return (source_form,)


@app.cell
def _(mo, migration, source_form):
    mo.stop(not source_form.value or not source_form.value["inspect"], mo.md("Source inspection has not been requested."))
    try:
        plan = migration.load_source(source_form.value["bundle"])
        _view = mo.vstack([
            mo.md("### Verified source profile and counts"),
            mo.ui.table([{"table":t,"rows":n} for t,n in plan["counts"].items()], selection=None),
            mo.md("Snapshot kind: " + plan["manifest"]["snapshot_kind"] + "\n\nAll-status historical merchandise total: " + str(plan["line_total_cents"]) + " cents. This is not a recognized-revenue claim."),
        ])
    except Exception as _exc:
        plan = None
        _view = mo.md("Source validation blocked migration: " + str(migration.error_summary(_exc)))
    _view
    return (plan,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("## 2.2 Review the migration contract\n| Source fact | Target decision |\n|---|---|\n| Integer-cent prices | BIGINT cents; no float conversion, currency invention, or silent rounding |\n| Timezone-free timestamp text | TIMESTAMP(0) WITHOUT TIME ZONE after exact format validation |\n| Charged line price and shipping-address snapshot | Retained on lines and orders |\n| Email uniqueness and RESTRICT foreign keys | Preserved |\n| Repeated SKU on different lines | Allowed; UNIQUE(order_id,line_no) remains |\n| source_row_id on order_items | Becomes application key order_item_id, preserving its existing value |\n| source_row_id on observations | Becomes observation_id, preserving its existing value |\n| Imported/database key history | Explicit snapshot/table/key mapping in migration_row_map |\n| True CSV lineage for later application rows | Unknown; no fake provenance generated |\n| Catalog-only observation quantity | Retained as observed_quantity, not asserted to be stock |\n| Status rules | Existing text preserved, including DELIVERED/custom live values; no new status CHECK |\n\nIdentical integer IDs in different tables are not the same identity. Newly generated source_row_id\nvalues in Module 8 are not universally original CSV row numbers. reconstructed_flat preserves source\nDATABASE row identifiers and may contain overlaps; UNION ALL is intentional, not a global deduplication.\nFuture PostgreSQL identities start beyond existing positive keys; this is not a claim to reproduce\nSQLite's future rowid reuse algorithm. The source uses INTEGER PRIMARY KEY, not AUTOINCREMENT.\n")
    return


@app.cell
def _(mo, migration):
    show_ddl = mo.ui.checkbox(value=False, label="Show the fixed target DDL before authorizing any writes")
    show_ddl
    return (show_ddl,)


@app.cell
def _(mo, migration, show_ddl):
    mo.md("```sql\n" + ";\n\n".join(migration.ddl) + ";\n```") if show_ddl.value else mo.md("Target DDL is available above for review.")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md('## 2.3 Configure the target and run read-only preflight\nUses existing PGHOST, PGPORT, PGDATABASE, PGCONNECT_TIMEOUT and the three COURSE_* credentials.\nPGSSLMODE (default prefer) and optional PGSSLROOTCERT are supported. Prefer is a local-lab setting,\nnot authenticated TLS; use a verified certificate policy remotely. Environment overrides .env without\ninterpolating secrets or trimming password whitespace. Never share .env, runtime variable inspectors,\nor raw driver exceptions. This notebook displays no password-bearing connection URL.\n\nPreflight verifies PostgreSQL 19 (or 18), the course database, role attributes/memberships, owner access,\nand an empty commerce schema. It uses SET TRANSACTION READ ONLY. Source/configuration changes reset\nsubsequent authorization widgets. Re-submit preflight after changing environment files.\n')
    return


@app.cell
def _(mo, repo_root, plan):
    mo.stop(plan is None, mo.md("Resolve source validation first."))
    target_form = mo.ui.dictionary({
        "env_path": mo.ui.text(value=str(repo_root / ".env"), label="Local configuration file", full_width=True),
        "authorize": mo.ui.checkbox(value=False, label="Run read-only target preflight as course_migrator"),
    }).form()
    target_form
    return (target_form,)


@app.cell
def _(mo, migration, plan, target_form):
    mo.stop(not target_form.value or not target_form.value["authorize"], mo.md("No PostgreSQL connection attempted."))
    try:
        config = migration.load_config(target_form.value["env_path"])
        target_check = migration.preflight(plan, config)
        _view = mo.vstack([
            mo.md("### Target preflight passed"),
            mo.ui.table([{"setting":k,"value":str(v)} for k,v in target_check["target"].items()], selection=None),
            mo.md("Authorization token for THIS preview and target configuration:\n\n`" + target_check["approval_token"] + "`"),
        ])
    except Exception as _exc:
        config = None
        target_check = None
        _view = mo.md("Target preflight failed: " + str(migration.error_summary(_exc)))
    _view
    return config, target_check


@app.cell(hide_code=True)
def _(mo):
    mo.md('## 2.4 Load in a deliberate transaction\nThe order is customers/products/warehouses -> orders -> order_items/catalog_observations.\nA target-wide advisory lock serializes competing migration attempts. The loader rechecks identity,\nsource token, and empty-target state at execution. DDL, rows, key maps, reconciliation, grants,\nidentity synchronization, and a migration ledger entry commit together.\n\nOptional exercise: inject a failure after orders or order_items, then rerun target preflight.\nSuccessful rollback should leave commerce empty. No DROP, TRUNCATE, constraint-disabling, or conflict-ignore\nreset is provided. Successful migrations intentionally refuse reruns against the occupied target.\n')
    return


@app.cell
def _(mo, plan, config, target_check):
    mo.stop(plan is None or config is None or target_check is None, mo.md("Pass source validation and target preflight."))
    commit_form = mo.ui.dictionary({
        "phrase": mo.ui.text(value="", label="Type MIGRATE commerce to authorize database changes"),
        "token": mo.ui.text(value="", label="Paste the current authorization token", full_width=True),
        "failure": mo.ui.dropdown(options=["No failure"] + list(plan["counts"]), value="No failure", label="Optional failure injection for rollback exercise"),
        "ack": mo.ui.checkbox(value=False, label="I reviewed the mapping and authorize writes to this course laboratory"),
    }).form()
    commit_form
    return (commit_form,)


@app.cell
def _(mo, migration, plan, config, target_check, commit_form):
    mo.stop(not commit_form.value or not commit_form.value["ack"], mo.md("Migration has not been authorized."))
    try:
        _failure = commit_form.value["failure"]
        outcome = migration.migrate(plan, config, commit_form.value["token"], commit_form.value["phrase"], None if _failure == "No failure" else _failure)
    except Exception as _exc:
        outcome = {"commit_state":"not_started", "ready_for_module_3":False, "error":migration.error_summary(_exc)}
    mo.vstack([
        mo.md("## Migration result\nCommit state: " + outcome["commit_state"] + "\n\nReady for Module 3: " + str(outcome["ready_for_module_3"])),
        mo.ui.table(outcome.get("validation", []) + outcome.get("ordinary_role_checks", []), selection=None) if outcome.get("validation") or outcome.get("ordinary_role_checks") else mo.md("No successful validation report is available."),
        mo.md("Redacted failure: " + str(outcome["error"])) if outcome.get("error") else mo.md(""),
        mo.md(outcome.get("recovery", "")),
    ])
    return (outcome,)


@app.cell
def _(mo, json, outcome):
    mo.download(data=json.dumps(outcome, indent=2, allow_nan=False).encode(), filename="module_02_migration_report.json", mimetype="application/json", label="Export reviewed migration report")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("## 2.5 Interpret evidence, not just a green connection\nValidation checks every canonical row in all six tables and the line/header/reconstruction reports.\nHeaders without lines keep line_count=0 and amount_cents=NULL. Calculations use exact integers/NUMERIC,\nnot overflowing BIGINT intermediate multiplication or SQLite floating-point aggregation.\n\nAfter commit, separate app/analyst connections verify data/report reads and grants. An actual no-op UPDATE\nruns in a rollback-only READ/WRITE transaction: app is allowed, analyst must receive SQLSTATE 42501.\nThis initial smoke check is not a comprehensive application-security or concurrency test.\n\nCommit states:\n- not_started: preconditions/connection failed before the transaction ran.\n- rolled_back: this attempt's pre-commit work was explicitly rolled back.\n- committed: rows/DDL/ledger committed; post-commit role failures do NOT undo them.\n- unknown: connection/commit acknowledgement needs recovery inspection. Never blindly reload.\n\nInspect migration_runs using the reported migration_id if commit acknowledgement is uncertain.\nIdentity allocations generally are not rolled back. Generated identities created within failed DDL\nare removed with their creating transaction; do not use contiguous IDs as success evidence.\nExports contain operational metadata; review them before sharing. Keep bundles and credentials out of Git.\n\n### Assessment\nSubmit source/mapping notes, successful parity evidence, injected-failure evidence, ordinary-role checks,\nand a rerun/recovery explanation. Source/contract 20%; design decisions 20%; transactional recovery 25%;\nreconciliation 25%; privileges/reproducibility 10%.\n\n### Draft limitations\nOnly the pinned Module 8 source profile is supported; source helper signature and provenance are recorded\nin fixtures/intro_ecommerce/README.md. No live PostgreSQL or Marimo UI validation is claimed by this initial draft.\nKnown Module 1 provisioning/volume issues are prerequisites to resolve separately, not hidden fixes here.\nPython/SQLite must provide Connection.deserialize (checked before inspection).\n")
    return


if __name__ == "__main__":
    app.run()
