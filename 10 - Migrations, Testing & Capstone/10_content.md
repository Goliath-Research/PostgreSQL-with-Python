# Module 10: Migrations, Testing & Capstone

From the clone root in PowerShell, use the existing course `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install "alembic>=1.13,<2"
.\.venv\Scripts\python.exe -m marimo check "10 - Migrations, Testing & Capstone/10_migrations_testing_and_capstone.py"
.\.venv\Scripts\python.exe -m unittest discover -s "10 - Migrations, Testing & Capstone/tests" -v
.\.venv\Scripts\python.exe -m marimo edit "10 - Migrations, Testing & Capstone/10_migrations_testing_and_capstone.py"
```

## Migration rehearsal

The baseline revision creates `orders`. The lab seeds an existing row, upgrades to add a non-null status with a server default, and downgrades using Alembic batch operations. Expect `(id=1, total_cents=1250, status=placed)` after upgrade and the same ID and amount, without status, after downgrade. The `alembic_version` row returns to `0001`. A downgrade that drops a column also drops its data, even when the surviving columns are preserved. The Alembic environment deliberately accepts only a supplied connection; this exercise is not a migration for the course PostgreSQL schema.

## Capstone brief: one PostgreSQL database, two deliverables

Start with a disposable copy of `goliath_ecommerce` populated by Module 2. Inspect the actual `commerce` schema and valid status transitions before mapping it. Use synthetic test orders and separate credentials for the migration, app and analyst roles. Never run the supplied SQLite revisions on the course database. If your capstone needs a schema change, review a separate PostgreSQL revision and apply it as `course_migrator` after assuming `course_owner`; neither runtime role should run DDL.

### A. Analytical deliverable — DuckDB as `course_analyst`

1. Attach read-only. At order grain, compute totals from charged line price times quantity; apply a documented status filter. For each customer report order count, eligible revenue, and average order value with an explicit denominator. Decide how customers with no eligible orders appear; never silently count a null joined order as one.
2. Produce category totals at order-line grain. Add a running total ordered by timestamp and order ID, and rank customers by eligible revenue with a stated tie rule. Reconcile overall totals across grains and explain exclusions or missing categories.
3. Compare an attached query with a bounded explicit `postgres_query` or `CONNECT` query. Document execution placement, what crosses the connection, and the sample bound. Export one bounded report and record its row count and money unit. Do not export personal data or connection settings.

### B. Operational deliverable — SQLAlchemy ORM as `course_app`

1. Map customers, orders, and order lines to the inspected schema. Retrieve existing orders with their lines and demonstrate relationship loading; capture emitted SQL without parameter values.
2. Create an order and all its lines in one `sessionmaker.begin()` scope. Include a test where a valid line is flushed before an invalid line causes failure, then use a new Session to verify that neither the failed order nor any of its lines persisted. Verify the successful case in a new Session as well.
3. Implement guarded cancellation using a conditional update with an allowed prior status in its predicate (or equivalent locking). Test allowed, already cancelled, and missing order cases, plus an ineligible status if supported by the actual schema. Record whether cancellation is idempotent in your API.

## Integration evidence to submit

Submit the report and its verification queries; mapped models and service code; migration history if applicable; integration tests; and a short runbook. Test that an application-created eligible order appears in the analyst report after commit, and that a failed order does not. Include a reconciliation against a small hand-calculated fixture, tests for relationship and rollback behavior, and a check that the analyst cannot write. Make live tests opt-in and target only a disposable course database. The supplied tests verify the migration rehearsal, not these learner deliverables.
