# Module 1: PostgreSQL Environment, Connections & Access Control

> **Hosted-lab architecture and operator requirements:** See the
> [Hosted Labs guide](../HOSTED_LABS.md) for execution modes, browser-versus-
> runtime responsibilities, and the distinction between recommendations and
> the current local-only Compose configuration.

**Course:** PostgreSQL with Python: Advanced Relational Databases — Goliath Research Academy  
**Implementation File:** `01_postgresql_environment.py`  
**Bootstrap & Infrastructure Files:** `../compose.yaml`, `../.env.example`, `../bootstrap/01_roles_and_database.sql`, `../bootstrap/02_schemas_and_probe.sql`  
**Estimated Effort:** 3–4 hours

## Overview & Learning Outcomes

Module 1 establishes a reproducible client/server PostgreSQL environment, secret-safe Python connectivity via **Psycopg 3**, deliberate role separation between schema ownership, migration, application writes, and analytical reads, and an automated readiness report over a disposable diagnostic table (`lab.connection_probe`).

Notice the explicit scope boundary: **the e-commerce schema and data migration belong in Module 2.** Module 1 establishes trust in the server environment, namespaces, and authorization boundaries before moving any business data.

By the end of this module, students will be able to:
1. Explain the architectural transition from an embedded SQLite database to a PostgreSQL client/server environment.
2. Start, inspect, stop (non-destructively), and reconnect to a reproducible local PostgreSQL environment.
3. Distinguish a PostgreSQL server instance (cluster), database (`goliath_ecommerce`), schema (`commerce`, `lab`), role, and client connection.
4. Configure Python connectivity via environment variables without embedding or printing credentials in notebooks.
5. Execute parameterized SQL using Psycopg 3 and manage connection/transaction lifecycles explicitly.
6. Distinguish authentication (`session_user` / login identity) from authorization (database, schema, and object privileges).
7. Demonstrate `course_app` read/write access and `course_analyst` read-only access on `lab.connection_probe`, while proving that unauthorized writes and DDL are rejected.
8. Diagnose common connection, namespace, and privilege failures systematically without resorting to superuser accounts or `GRANT ALL`.
9. Generate a secret-free readiness report verifying that the environment is ready for Module 2's migration.

---

## Section Summary

| Section | Topic                                                                      |
| ------- | -------------------------------------------------------------------------- |
| 1.1     | From embedded SQLite to a PostgreSQL client/server architecture            |
| 1.2     | Establishing a reproducible laboratory (`compose.yaml` & `bootstrap/*.sql`) |
| 1.3     | Understanding database namespaces (`goliath_ecommerce`, `commerce`, `lab`) |
| 1.4     | Separating ownership, migration, application, and analytical identities    |
| 1.5     | Configuring credentials safely without exposing secrets                    |
| 1.6     | Connecting from Python with Psycopg 3 and inspecting session identity      |
| 1.7     | Verifying privileges against `lab.connection_probe`                        |
| 1.8     | Troubleshooting as a systematic diagnostic sequence                        |
| 1.9     | Secret-free readiness report, submission checklist, and assessment rubric  |

---

## Detailed Section Explanations

### 1.1 From embedded SQLite to a database server
In the introductory course, Python's `sqlite3` ran as an in-process library reading and writing an in-memory or local file database directly:
```text
Introductory course:
Marimo / Python ──► sqlite3 (in-process engine) ──► SQLite database (:memory: or file)

Advanced course:
Marimo / Python ──► Psycopg 3 / DuckDB / SQLAlchemy
                        │
                Host + Port + Authentication
                        ▼
               PostgreSQL Server (19)
                        │
           Database (goliath_ecommerce)
              ├── Schema: commerce (Module 2 business tables)
              └── Schema: lab      (Module 1 diagnostic probe)
```
- **What remains transferable:** Relational modeling (1NF–3NF), primary and foreign keys, `CHECK` and `UNIQUE` constraints, joins, result-grain discipline, ACID transactions, and window functions.
- **What becomes explicit:** Independent server lifecycle, network endpoints (`host`, `port`), connection timeouts, login authentication, role ownership, schema namespaces, and multi-level authorization (`DATABASE`, `SCHEMA`, `TABLE`, `SEQUENCE`).
- **Why changing a connection string is not a migration:** Simply swapping `sqlite3.connect(...)` for `psycopg.connect(...)` does not create roles, configure schema ownership, enforce least-privilege access, or map SQLite dynamic typing (`typeof(...)`) to strict PostgreSQL native types (`TIMESTAMPTZ`, `NUMERIC`, identity columns).

### 1.2 Establish a reproducible laboratory
The primary laboratory uses `compose.yaml` with `postgres:19-bookworm` (and supports native PostgreSQL 19 installations; PostgreSQL 18 servers are still accepted by every module's version check):
- **PostgreSQL 19 Image Tag:** Uses `postgres:19-bookworm` rather than `postgres:latest`. This is a floating-minor tag, not an exact release pin; use a tested exact tag (and verified digest for controlled releases) when exact image reproducibility is required.
- **Named Data Volume (`goliath_pgdata`):** Persists `/var/lib/postgresql` across container restarts. PostgreSQL 19 keeps its data directory at `/var/lib/postgresql/19/docker`. A volume created by the earlier `postgres:18-bookworm` image holds its cluster in `/var/lib/postgresql/18/docker`; the PostgreSQL 19 image does not upgrade it. See the README section *Upgrading an existing PostgreSQL 18 volume*.
- **Version Check:** The notebook's readiness report requires `180000 <= server_version_num < 200000` (PostgreSQL 18 or 19), the same range enforced by Modules 2–4.
- **Localhost-Only Port Publishing:** `"127.0.0.1:${PG_HOST_PORT:-54329}:5432"` binds the host port exclusively to the loopback interface (`127.0.0.1`), preventing accidental exposure on local Wi-Fi or LAN networks.
- **Health/Readiness Check:** Runs `pg_isready -U postgres -d goliath_ecommerce` so tools can distinguish "container started" from "PostgreSQL ready to accept connections."
- **Normal Shutdown vs. Destructive Reset:**
  - `docker compose stop` / `docker compose start`: Stops and restarts the server process while preserving `goliath_pgdata`.
  - `docker compose down -v`: Destroys the container **and** deletes `goliath_pgdata` (triggering `/docker-entrypoint-initdb.d/*.sql` on the next `docker compose up -d`).
- **Notebook Boundary:** `01_postgresql_environment.py` inspects the environment and connects to it; rerunning notebook cells never launches containers or deletes volumes behind the scenes.

### 1.3 Understand database namespaces
A PostgreSQL server cluster manages one or more **databases**, and each database contains multiple **schemas** (namespaces):
| Object   | Name                | Purpose                                        |
| -------- | ------------------- | ---------------------------------------------- |
| Database | `goliath_ecommerce` | Authoritative course database                  |
| Schema   | `commerce`          | Target namespace for business tables (Module 2)|
| Schema   | `lab`               | Diagnostic objects for Module 1 (`lab.connection_probe`) |

- **Schema Qualification:** Writing `SELECT * FROM lab.connection_probe;` explicitly names both the schema (`lab`) and the relation (`connection_probe`).
- **`search_path` and Trust:** When a query omits the schema name (`SELECT * FROM connection_probe;`), PostgreSQL searches the schemas listed in `SHOW search_path` in order. Relying on unqualified names can cause `"relation does not exist"` (`SQLSTATE 42P01`) if the schema is absent from `search_path`, and placing a schema with broad `CREATE` privileges (like an unhardened `public` schema) early in `search_path` allows object-shadowing attacks. For this reason, `01_roles_and_database.sql` executes `REVOKE CREATE ON SCHEMA public FROM PUBLIC;`, and students use schema-qualified names throughout Module 1.

### 1.4 Separate ownership, migration, application, and analytics
Module 1 provisions four non-superuser roles in `bootstrap/01_roles_and_database.sql`:

| Role              | Login? | Intended Responsibility                                                        |
| ----------------- | ------ | ------------------------------------------------------------------------------ |
| `course_owner`    | No     | Owns the `goliath_ecommerce` database, `commerce` and `lab` schemas, and tables |
| `course_migrator` | Yes    | Performs controlled DDL migrations via explicit `SET ROLE course_owner`        |
| `course_app`      | Yes    | Executes permitted transactional reads/writes (Psycopg 3 & SQLAlchemy)         |
| `course_analyst`  | Yes    | Executes read-only analytical queries (DuckDB 2.0)                             |

- **Three Permission Layers:** Reaching a table requires (1) `CONNECT` on the database, (2) `USAGE` on the containing schema, and (3) specific table/sequence privileges (`SELECT`, `INSERT`, etc.).
- **The Future-Object Problem (`ALTER DEFAULT PRIVILEGES`):** Granting `SELECT ON ALL TABLES IN SCHEMA lab` only affects tables that exist at that moment. For future tables to inherit permissions automatically, `ALTER DEFAULT PRIVILEGES FOR ROLE course_owner IN SCHEMA ...` must be configured specifically for the role that **creates** those objects (`course_owner`).

### 1.5 Configure credentials without exposing them
- **Configuration Boundary:** Connection parameters (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGCONNECT_TIMEOUT`) and role credentials (`COURSE_APP_PASSWORD`, `COURSE_ANALYST_PASSWORD`, `COURSE_MIGRATOR_PASSWORD`) are read from `.env` or process environment variables.
- **Redaction Rules:** The notebook displays only safe metadata (`Host`, `Port`, `Database`, `Role`, and `Password: configured (not displayed)`). Passwords, raw DSN strings containing passwords, and unredacted traceback parameters are never rendered in cell outputs.
- **Host vs. Container `localhost`:** When Python runs on the host machine, `127.0.0.1:54329` reaches the published host port. Inside the PostgreSQL container itself, PostgreSQL listens on container port `5432`.

### 1.6 Connect from Python with Psycopg 3
- **Diagnostic Identity Query:**
  ```sql
  SELECT
      current_database() AS database_name,
      current_user       AS effective_role,
      session_user       AS login_role,
      current_schema()   AS current_schema;
  ```
  `session_user` identifies the authenticated login role (e.g., `course_migrator`), while `current_user` identifies the active effective role for permission checks (which changes to `course_owner` after `SET ROLE course_owner;`).
- **Context-Manager Difference (`sqlite3` vs. `psycopg` v3):**
  - In Python's `sqlite3`, `with conn:` manages a transaction boundary but **does not close** the connection.
  - In **Psycopg 3**, `with psycopg.connect(...) as conn:` commits at block exit (if no exception occurred and `autocommit=False`), rolls back on exception, **and closes the connection** when leaving the `with` block.

### 1.7 Verify privileges with a diagnostic table (`lab.connection_probe`)
Behind an explicit **Run access-control tests** action, the notebook executes six isolated verification cases against `lab.connection_probe`:

| # | Identity         | Operation                                                     | Expected Result |
| - | ---------------- | ------------------------------------------------------------- | --------------- |
| 1 | `course_app`     | `SELECT` from `lab.connection_probe`                          | **Allowed**     |
| 2 | `course_app`     | Parameterized `INSERT` into `lab.connection_probe`            | **Allowed**     |
| 3 | `course_analyst` | `SELECT` from `lab.connection_probe`                          | **Allowed**     |
| 4 | `course_analyst` | `INSERT` into `lab.connection_probe`                          | **Denied** (`42501`) |
| 5 | `course_app`     | `CREATE TABLE commerce.unauthorized_check (...)`              | **Denied** (`42501`) |
| 6 | `course_app`     | Owner-only DDL (`ALTER TABLE lab.connection_probe ...`)       | **Denied** (`42501`) |

Each negative test runs inside its own short-lived connection or rolls back its aborted transaction cleanly so subsequent checks are unaffected.

### 1.8 Troubleshooting as a diagnostic sequence
Before changing configuration files or granting permissions, classify the symptom using the failure stage and SQLSTATE code:
- **Network / Endpoint (`OperationalError`):** `Connection refused` (service stopped or wrong `PGPORT`) vs. `Connection timeout` (unreachable host/firewall).
- **Authentication / Target Database (`OperationalError`):** `28P01` (`password authentication failed`) vs. `3D000` (`database "..." does not exist`).
- **Namespace / Object Resolution (`UndefinedTable` `42P01`):** Table missing or referenced without its schema prefix (`lab.connection_probe`).
- **Authorization (`InsufficientPrivilege` `42501`):** Missing `USAGE` on schema, missing `SELECT`/`INSERT` on table, or attempting DDL without ownership.

### 1.9 Readiness report and assessment rubric

| Area                                        | Weight |
| ------------------------------------------- | ------ |
| Reproducible setup and container lifecycle  | 25%    |
| Safe configuration and Psycopg connectivity | 25%    |
| Role separation and privilege verification  | 30%    |
| Diagnostics, troubleshooting, and report    | 20%    |
