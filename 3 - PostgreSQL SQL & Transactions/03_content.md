# Module 3: PostgreSQL SQL & Transactions

- Course: PostgreSQL with Python: Analytics, ORM, and Database Applications — Goliath Research Academy
- Implementation: `03_postgresql_sql_and_transactions.py` and `module_03_support.py`
- Directory: `3 - PostgreSQL SQL & Transactions/`
- Estimated effort: 4–6 hours

## Overview and learning outcomes

This module reads the migrated commerce database and performs transaction exercises
only on synthetic rows in `lab`. It uses PostgreSQL, Psycopg 3, python-dotenv and
Marimo, not SQLite concurrency mocks, DuckDB, SQLAlchemy or Jupyter. Opening or
importing the code does not read credentials, connect, provision, run an
experiment, or write a report. Actions require explicit submissions. This guide
describes the implementation, not evidence that your own environment has passed.

After completing the module, you should be able to:

1. Check real relations, roles and permissions before relying on migrated data.
2. Explain strict types, nulls, numeric arithmetic and result grain.
3. Distinguish an unzoned wall-clock timestamp from an instant.
4. Explain atomic transactions, aborted transactions and savepoints.
5. Compare statement and transaction snapshots using separate sessions.
6. Recognize row-lock conflicts, deadlock victims and ordered locking.
7. Explain a serialization anomaly and retry the **whole** transaction safely.
8. Interpret evidence, distinguish blocked exercises from passes, and clean up
   only an explicitly selected run.

## Section summary

| Section | Topic | Main observation |
|---|---|---|
| 3.1 | Readiness and read-only SQL | Inspect actual prerequisites and ordinary-role access |
| 3.2 | Expressions and strict types | Null, casts, exact arithmetic, aggregation and grain |
| 3.3 | Time | Hypothetical timezone policy, never a source-data conversion |
| 3.4 | Provisioning and atomicity | Authorized namespaced tables; commit versus rollback |
| 3.5 | Errors and savepoints | 25P02 until rollback; a savepoint contains a failure |
| 3.6 | Isolation snapshots | Read Committed refreshes; Repeatable Read stays stable |
| 3.7 | Locks | NOWAIT, real deadlock detection, ordered acquisition |
| 3.8 | Serializable | Write skew, 40001, bounded whole-transaction retry |
| 3.9 | Evidence, cleanup, assessment | Redacted results and separately authorized cleanup |

## Preparation

Use Python 3.11+ and the project's existing dependencies. From the repository
root, with your environment activated:

```bash
python -m pip install -e .
marimo edit "3 - PostgreSQL SQL & Transactions/03_postgresql_sql_and_transactions.py"
```

Module 1 must already have created the expected database, roles and schemas;
Module 2 must have actually migrated its six business tables. Neither a merged PR
nor a listening server proves readiness. Configure `.env` as described in Module 1.
The loader uses `dotenv_values(..., interpolate=False)` and process environment
variables override the file. Password whitespace is significant. The module
requires PostgreSQL 18 and `goliath_ecommerce`; it does not repair bootstrap,
change passwords, or substitute a superuser if a role cannot log in.

The notebook locates its helper relative to its own file, including when its
directory contains spaces and `&`. Submit configuration and preflight first,
then authorize each write action separately. On configuration changes submit a
new preflight and new action authorization. Never put credentials into the
notebook, a report, or a screenshot.

## 3.1 Readiness and read-only SQL

Preflight checks the actual server version, database and session identities,
the `lab` owner and the six `commerce` relations and access rather than assuming
the migration succeeded. A missing relation, mismatched role or insufficient
privilege blocks exercises; fix the prerequisite through the appropriate earlier
module, not by running this module as an administrator. Read-only examples use
aggregates rather than exporting customer details.

The target contains `customers`, `products`, `warehouses`, `orders`, `order_items`
and `catalog_observations`. Money is integer cents. `orders.ordered_at` is
`TIMESTAMP WITHOUT TIME ZONE`, and `shipping_address_snapshot` remains on the
order. `order_item_id` and `observation_id` are separate application keys. A
database key map documents database lineage, not original CSV provenance.
Catalog observations are observations, **not inventory**.

## 3.2 Expressions, types and grain

PostgreSQL requires compatible operand types; a text value is not automatically
an integer. `CAST(... AS numeric)` or `::numeric` states the intended conversion.
Integer division truncates (`5 / 2 = 2`); `5::numeric / 2 = 2.5`. Use exact
`numeric` for calculations requiring decimal fractions; keep stored prices in
integer cents. A `NULL` comparison yields unknown, so use `IS NULL`, not
`= NULL`. `WHERE` retains only true, not false or unknown.

`read_sql_examples` uses `COUNT(*) FILTER (WHERE unit_price_cents > 0)` to
count a selected subset without excluding other rows from the group. Its
`per_order` CTE groups lines by order ID, so its grain is one row per **order
with items**, not all orders. `row_number() OVER (ORDER BY total_cents, order_id)`
retains those rows; the final query returns only aggregate counts, not business
rows. It multiplies cents and quantity as `numeric` to avoid integer overflow
in the calculation. An empty `SUM` is null, and the final `COALESCE` explicitly
presents zero. A left join could keep orders without lines, but this example
does not perform one. Explain the grain before interpreting results.

## 3.3 Timezone-free values and instants

`TIMESTAMP WITHOUT TIME ZONE` records a wall-clock value, not an instant.
Interpreting it requires an external timezone policy, including decisions for
ambiguous or nonexistent daylight-saving times. For illustration only, a
hypothetical `TIMESTAMP '2024-01-15 12:00:00' AT TIME ZONE 'America/New_York'`
chooses that zone and produces an instant. `TIMESTAMPTZ` represents an instant;
PostgreSQL displays it according to the session timezone, not an originally
stored zone label. A different hypothetical zone may produce a different
instant. These examples do not assert a zone for imported orders and do not
rewrite source timestamps.

## 3.4 Provisioning and COMMIT/ROLLBACK

Provisioning is a separate, explicitly authorized operation using
`course_migrator` and `SET LOCAL ROLE course_owner`. It refuses an existing
object of that name rather than changing it, and verifies the created table's
ownership, columns, constraints and privileges before use. The only new
relation is `lab.module_03_txn_rows`, whose UUID and slot identify synthetic
values; app gets explicit SELECT/INSERT/UPDATE/DELETE and analyst SELECT. No privileges on
`lab.connection_probe` or `commerce` are broadened.

Every exercise uses fresh UUID-scoped synthetic rows. Atomicity means that the
committed transaction persists all of its changes; the intentionally rolled-back
transaction persists none. The balances are integer cents, not real orders or
warehouse stock. Data from a successful exercise remains until separately
authorized cleanup; no automatic destructive reset is performed.

`provision` refuses a second creation attempt rather than adopting an unknown
object. `_ready` verifies the table before a run. In `commit_rollback`, an
initial value of 10 commits; a change to 20 is rolled back, and a fresh read
checks that 10 remains. The report returns boolean evidence, not the row.

## 3.5 Aborted transactions and savepoint recovery

A constraint violation fails the statement and marks its transaction aborted.
Subsequent SQL in that transaction receives `25P02` until rollback. With a
savepoint, rolling back the inner failed unit restores the outer transaction to
a usable state; it can then make another valid change and commit. Psycopg
transaction contexts delimit these units; do not catch an error and continue in
the same aborted transaction without rolling back to a savepoint or ending it.
The implemented constraint exercise attempts a duplicate `(run_id, slot)`,
records `23505` and `25P02`, rolls back to the savepoint, inserts a different
slot, and commits the outer transaction.

## 3.6 Two-session isolation

The reader and writer use genuinely distinct connections and an explicit
sequence: reader queries, writer commits a change, reader queries again. Under
Read Committed each statement obtains a new snapshot, so the second query can
see the committed change. Under Repeatable Read the first query establishes a
stable transaction snapshot, so the second query sees the original value.
Repeatable Read does **not** prevent every serialization anomaly.
The helper checks the intermediate uncommitted value as well as the value after
the writer commits, then starts a new transaction to check the refreshed view.

## 3.7 Row locks and deadlocks

`SELECT ... FOR UPDATE` locks a row until transaction end. A second session's
`FOR UPDATE NOWAIT` immediately fails with `55P03`; it is not a successful lock.
To demonstrate a deadlock, two sessions lock different rows then request each
other's row. PostgreSQL may abort either victim with `40P01`; both sessions must
release their transactions. Timeouts, inaccessible settings, worker failure or
an unavailable environment are blocked/inconclusive, not proof of deadlock
detection. Finite statement/lock limits and bounded synchronization prevent an
unbounded classroom wait. Acquiring the same rows in a consistent order avoids
this opposite-order cycle; it is not a guarantee against every possible deadlock.
The helper inspects `deadlock_timeout`, `lock_timeout` and `statement_timeout`
before the deadlock test and refuses to call a timeout a successful deadlock.

## 3.8 Serializable and retry

Consider two accounts each with 100 cents and the invariant that their sum is
at least 100. Both sessions read 200 before either writes. Each independently
decides to subtract 100 from a different account if the total is at least 200.
Snapshot isolation can allow both writes and violate the invariant (write skew).
Serializable detects the conflict and rejects a transaction with `40001`,
possibly at its statement or commit. A retry opens a fresh transaction and
repeats **all** reads and decision logic with a bounded attempt count; it may
now legitimately decline the debit. Do not retry arbitrary errors, deadlocks,
permission failures or uncertain commit acknowledgements as serialization
failures, or replay external side effects. Retries must not wait on a two-party
first-attempt barrier whose peer has already finished.
The helper first commits the anomalous Repeatable Read outcome on one pair of
slots, then uses a separate pair for Serializable. Its reported decision after
retry is `decline` when the peer has already left the total at 100.

## 3.9 Evidence, cleanup and assessment

Reports are redacted: no credentials, DSNs, driver error messages or sensitive
business rows. Record statuses and SQLSTATEs rather than private data. A test
pass does not mean an exercise was run; a skipped integration test is not a
PostgreSQL concurrency pass. Keep each run UUID and submit cleanup separately
for exactly that run. Cleanup failure must be reported; it must not be presented
as success or followed by a schema-wide reset.

Run offline tests explicitly (the repository's default pytest discovery does not
include this directory):

```bash
python -m pytest "3 - PostgreSQL SQL & Transactions/tests/test_module_03.py"
```

The integration test is skipped unless `MODULE03_DISPOSABLE` is exactly
`I_ACCEPT_DISPOSABLE_DATABASE_WRITES`. It also requires an explicit
`MODULE03_DISPOSABLE_PORT` on localhost and `MODULE03_MIGRATOR_PASSWORD`,
`MODULE03_APP_PASSWORD`, and `MODULE03_ANALYST_PASSWORD` in the environment.
Only opt in against a separately created, bootstrapped and migrated disposable
PostgreSQL 18 instance, never an ordinary course database. The test creates lab
objects if absent and commits synthetic runs; its cleanup removes only the run
UUIDs it created, not the lab table itself. A skipped integration test does not
verify PostgreSQL behavior.

### Assessment rubric

| Criterion | Evidence |
|---|---|
| Readiness and data model | Correct identities and six relations; explains lineage and observation limits |
| SQL and time | Correct grain, null and numeric explanations; no invented timezone |
| Transactions | Explains committed/rolled-back state, 25P02 and savepoint recovery |
| Concurrency | Explains two snapshots, 55P03, actual 40P01 and lock ordering |
| Serializable | Names invariant, 40001 and full retry with a possible rejected decision |
| Operational safety | Distinguishes pass/skip/block, protects credentials and scopes cleanup |

### Troubleshooting and limitations

* Connection, identity, version or permission errors: inspect Module 1 and
  Module 2 provisioning and credentials; the module will not fix them for you.
* Missing or incompatible lab objects: stop and inspect ownership/contracts;
  never drop an unknown table or broaden unrelated privileges.
* `55P03` is the intended NOWAIT denial; `40P01` is deadlock detection;
  `40001` is serialization failure; `25P02` indicates an aborted transaction.
  A timeout is not a substitute for any of these observations.
* A lost connection during commit can leave an unknown outcome. Inspect the
  run's state manually; do not blindly repeat the transaction.
* Exercises require independent connections and enough server capacity. A
  passing offline test alone does not verify PostgreSQL lock scheduling.

### References

* [PostgreSQL 18 transaction isolation](https://www.postgresql.org/docs/18/transaction-iso.html)
* [PostgreSQL 18 explicit locking](https://www.postgresql.org/docs/18/explicit-locking.html)
* [PostgreSQL 18 serialization failure handling](https://www.postgresql.org/docs/18/mvcc-serialization-failure-handling.html)
* [Psycopg 3 transaction management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
