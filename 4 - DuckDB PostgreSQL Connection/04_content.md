# Module 4: DuckDB PostgreSQL Connection

Course: PostgreSQL with Python: Analytics, ORM, and Database Applications  
Notebook: `04_duckdb_postgresql_connection.py`  
Implementation: `module_04_support.py`

## Overview and learning outcomes

Use DuckDB to read the PostgreSQL database migrated in Module 2. By the end, you can connect as the analyst, distinguish a DuckDB query over an attached table from SQL explicitly sent to PostgreSQL, and verify that an aggregation runs entirely in DuckDB after the source is detached.

| Section | Exercise | Evidence |
|---|---|---|
| 4.1 | Load the PostgreSQL extension and attach read-only | Remote role, database, version, transaction mode |
| 4.2 | Run DuckDB SQL over attached data | Filtered count and PostgreSQL scan plan indicator |
| 4.3 | Execute SQL in PostgreSQL explicitly | PostgreSQL session settings and server-side ordered limit |
| 4.4 | Compute locally after extracting a sample | Local computation succeeds with PostgreSQL detached |

## Start the lab

Keep the notebook and helper side by side. Open the notebook from the repository root in the course virtual environment:

```bash
python -m marimo edit "4 - DuckDB PostgreSQL Connection/04_duckdb_postgresql_connection.py"
```

Dependencies are native Python with Marimo, DuckDB, Psycopg 3 (for building a libpq connection string), and python-dotenv. Use a DuckDB build with the official `postgres` extension available for your platform. The notebook reports the actual runtime version; this draft does not assert a tested DuckDB release range. It uses `postgres_query` rather than depending on the newer `CONNECT`/`DISCONNECT` API. `DETACH` removes the attachment; it is not `DISCONNECT`.

Use your repository-root `.env` with `PGHOST`, `PGPORT`, `PGDATABASE=goliath_ecommerce`, `COURSE_ANALYST_USER=course_analyst`, and `COURSE_ANALYST_PASSWORD`. Environment variables override the file. The default port is 54329; use your actual port for a native server. `PGSSLMODE` and `PGSSLROOTCERT` can configure TLS; for a remote connection, use a verified TLS policy appropriate to the deployment. Leave credentials out of Git and screenshots. Run against the course database, not production.

This notebook expects PostgreSQL 18 and migrated Module 2 data. In a hosted lab the browser is the editor; the native Python kernel and DuckDB extension run outside the browser and reach the learner's private PostgreSQL instance. This is not a browser-WASM notebook. See the course's `HOSTED_LABS.md`.

## 4.1 Load and attach

Select **Install / load extension** if needed. This explicitly runs `INSTALL postgres` and `LOAD postgres`; installation may download an extension into DuckDB's cache. It does not install PostgreSQL itself. Then select **Run read-only lab** and submit. The execution path loads the extension without downloading it automatically. `Settings.load()` uses the fixed analyst identity; `run()` attaches `commerce` under `course_pg` with `READ_ONLY` and requests read-only PostgreSQL transactions. Server-side analyst grants are the authorization boundary; the notebook does not audit every grant or attempt writes. Raw driver errors and the connection string are not printed. Do not enable SQL tracing around credential-bearing connection construction.

## 4.2 Read an attached table

`SCAN` counts order lines whose `quantity` is at least two; the count is at order-line grain, not order grain. A PostgreSQL scan operator means the attached source participates, not that PostgreSQL performed the whole filter and aggregate. The report shows whether the plan text contains `POSTGRES_SCAN`; a false value can reflect plan naming differences. The full-table count may do more work than the later bounded extraction; a statement timeout is requested for remote work.

## 4.3 Send a fixed query to PostgreSQL

`postgres_query` sends SQL to PostgreSQL for execution. The first call returns PostgreSQL session facts. The second projects only three order-line fields and specifies `ORDER BY order_item_id LIMIT n` inside the PostgreSQL query. The cap bounds result rows, not all server work or bytes. Only the validated integer limit is configurable; the notebook has no free-form SQL input. The sample is deterministic for unchanged data but is not a random sample.

## 4.4 Materialize and aggregate in DuckDB

The helper creates an in-memory `line_sample`, detaches `course_pg`, then computes count and merchandise cents from the retained rows. `HUGEINT` widens the operands before multiplication; values and totals remain integer cents. The result covers only the sampled rows and is not revenue. `SUM` returns NULL for an empty sample; exceptionally large products or sums may exceed `HUGEINT` and fail rather than round. No timestamps are converted, no catalog observations are used as inventory, and no PostgreSQL data is copied permanently or modified.

## Verify your work

From the repository root:

```bash
python -m unittest discover -s "4 - DuckDB PostgreSQL Connection/tests" -p 'test_*.py'
```

The database check is opt-in. Install the extension first, then point `MODULE04_TEST_ENV` at the dotenv file for your populated disposable course lab and rerun the same command. Process variables still override the file. An integration skip is not a live PostgreSQL pass. Evidence to submit: actual DuckDB version, remote analyst identity, explanation of what the scan proves, and sample limit/count with an explanation of why the final aggregation is local.

## References

- DuckDB PostgreSQL extension: https://duckdb.org/docs/stable/core_extensions/postgres
- DuckDB PostgreSQL extension functions: https://duckdb.org/docs/1.5/core_extensions/postgres/functions
