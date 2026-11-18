# Module 11: MCP Servers over PostgreSQL & DuckDB

## Part 1 — Run the fixture and inspect the contract

Use Python 3.11+ and the existing course `.venv`. Run from the clone root in PowerShell:

```powershell
$python = ".\.venv\Scripts\python.exe"
$module = "11 - MCP Servers over PostgreSQL & DuckDB"
& $python -m pip install -r "$module/requirements.txt"
& $python "$module/11_mcp_client.py"
& $python -m unittest discover -s "$module/tests" -v
& $python -m marimo check "$module/11_mcp_servers.py"
& $python -m marimo edit "$module/11_mcp_servers.py"
```

The client starts a local stdio subprocess and selects the synthetic fixture by default. No LLM account is needed. Expect order 101 to total 2,000 cents and Books to rank first at 1,500 cents. Inspect `schema://commerce/reporting`, call both tools, then try invalid arguments. For an optional manual walkthrough, configure MCP Inspector to launch the same `.venv` Python with the server script as its argument; leave the database URL unset for fixture mode. Reserve server stdout for MCP messages.

## Part 2 — Use a disposable PostgreSQL database

1. In a disposable PostgreSQL lab instance, provision a dedicated LOGIN named `mcp_analyst` (no elevated flags or role memberships) and a fresh lab database. Set its password using your local PostgreSQL administration workflow; do not commit it. Connect as the lab administrator and apply `postgres_fixture.sql` with error-on-failure enabled. Do not apply it to the live course schema. It creates only a synthetic reporting interface and a restricted fixture table.
2. Set `COURSE_MCP_DATABASE_URL` in your local process environment to a `postgresql+psycopg` URL for `mcp_analyst` on that database. Percent-encode reserved characters in credentials, and do not paste the real URL into the notebook, a transcript, or the repository. Run `& $python "$module/11_mcp_client.py" --postgres`. Expected results match the synthetic fixture.
3. Set `$env:COURSE_MCP_TEST_POSTGRES = '1'` and rerun unittest. The opt-in test queries effective table privileges and performs an approved read; it does not attempt DDL or mutation. Remove both environment variables afterward using `Remove-Item Env:COURSE_MCP_TEST_POSTGRES, Env:COURSE_MCP_DATABASE_URL`.

SQLAlchemy sends fixed parameterized PostgreSQL statements. For category reporting PostgreSQL filters the dates and transfers at most 1,001 rows. The extra row detects overflow; more than 1,000 rows causes rejection, not a partial aggregate. DuckDB groups the bounded rows locally. The date range is half-open and capped at 31 days; the tool returns at most 25 categories. The order tool returns a summary, not customer details. The supplied PostgreSQL fixture contains only eligible sales. For a capstone extension, adapt an approved view to the real `commerce` schema and document eligibility, grants, and reconciliation rather than granting blanket access.

## Review

Explain why input validation, bound values, database privileges, and read-only transactions are separate controls. Verify no generic SQL or write tool is advertised. This is a local lab, not a remote authenticated MCP deployment. Compare the same reporting contract with a declaratively modeled Exograph interface in the next course; do not assume matching titles imply matching authorization.
