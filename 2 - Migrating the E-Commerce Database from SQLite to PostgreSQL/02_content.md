# Module 2: Migrating the E-Commerce Database from SQLite to PostgreSQL

Course: PostgreSQL with Python: Advanced Relational Databases — Goliath Research Academy  
Implementation file: `02_sqlite_to_postgresql.py`  
Repository directory: `2 - Migrating the E-Commerce Database from SQLite to PostgreSQL/`  
Source helper: `fixtures/intro_ecommerce/8 - Python Database Integration & Capstone/ecommerce_snapshot.py`
Estimated effort: 4–6 hours  
Documentation baseline: implementation at commit `4c17468edfcf20d168fb716b0f410d2a6dc9da9b`

## Overview & Learning Outcomes

Module 2 moves the introductory course's existing six-table relational database from SQLite into PostgreSQL's `commerce` schema. It teaches migration as an inspectable, authorized, and validated operation—not a connection-string substitution or an unrelated CSV re-import.

The migration uses Python's `sqlite3` module and Psycopg 3 directly. DuckDB 2.0 analytical access and SQLAlchemy application persistence belong to later modules. Keeping those interfaces out of this migration makes source inspection, target SQL, ownership, transactions, and validation visible.

The implementation is a self-contained Marimo notebook. `build_migration_api()` defines its migration functions and returns a `SimpleNamespace`; a later cell exposes that namespace as `migration`. Opening the notebook does not build a source database, connect to PostgreSQL, or write a snapshot. Source inspection, target preflight, and migration are separate user-triggered operations.

By the end, students should be able to:
1. Distinguish a rebuilt teaching baseline from a snapshot of an actual live connection.
2. Verify a snapshot's manifest, checksum, schema profile, integrity, relationships, and counts before loading it.
3. Explain the differences between database identity, imported source keys, and verified CSV provenance.
4. Preserve integer-cent amounts, order-time shipping addresses, charged prices, and catalog-only observations.
5. Map SQLite values to PostgreSQL without silently inventing currency or timezone information.
6. Use the migrator identity and explicit owner-role assumption rather than an application or superuser login.
7. Load related tables and migration metadata within one deliberate transaction.
8. Reconcile complete row content and reports, rather than relying only on matching counts.
9. Demonstrate rollback, verify ordinary-role access, and interpret uncertain commit outcomes safely.

This guide describes the code's implemented behavior. It does not certify that the notebook has passed live PostgreSQL or Marimo UI integration testing.

---

## Section Summary

The headings below follow the notebook's five numbered teaching sections.

| Section | Topic | Main code |
|---|---|---|
| 2.1 | Inspect a completed source snapshot | `bounded_read`, `load_source`, `normalize`, `expected_reports` |
| 2.2 | Review the migration contract and target DDL | `COLUMNS`, `RENAMES`, `IDENTITIES`, `target_columns`, `DDL` |
| 2.3 | Configure the target and run read-only preflight | `Config`, `load_config`, `connect`, `guard_target`, `preflight` |
| 2.4 | Authorize and execute the transactional load | `approval_token`, `migrate`, source/target/commit forms |
| 2.5 | Interpret validation, access checks, and recovery evidence | `digest_rows`, `validate_target`, `assess_roles`, result/export cells |

---

## Preparation & Repository Workflow

### Required environment

Use Python 3.11 or later with the dependencies declared in the script:

```bash
python -m pip install "marimo>=0.11,<1" "psycopg[binary]>=3.2,<4" "python-dotenv>=1,<2"
```

The course standard is PostgreSQL 19. The target guard accepts the PostgreSQL 18 and 19 release series: `180000 <= server_version < 200000`. It does not accept PostgreSQL 17 or claim compatibility with an unreviewed PostgreSQL 20.

Module 1 must already have provisioned `goliath_ecommerce`, the course roles, and `commerce` owned by `course_owner`. Its actual runtime checks must pass. A merged PR or a successful server healthcheck alone is not migration readiness. Module 2 does not repair container volumes, create bootstrap roles, rotate existing credentials, or reset the database.

### Prepare a source bundle deliberately

From the repository root, create a new baseline only when one is needed:

```bash
python "2 - Migrating the E-Commerce Database from SQLite to PostgreSQL/fixtures/intro_ecommerce/8 - Python Database Integration & Capstone/ecommerce_snapshot.py" rebuild "2 - Migrating the E-Commerce Database from SQLite to PostgreSQL/fixtures/intro_ecommerce/baseline_bundle"
```

The helper refuses an existing destination. Use an already verified bundle or choose a different new destination; do not delete an existing snapshot merely to bypass this safeguard.

The `fixtures/intro_ecommerce/` directory contains only SQLite migration inputs: the pinned helper and source CSV used to build the sample source database, with provenance, license, and verification. It is not a copy of the introductory course or a backup of student work.

The bundle contains:

```text
ecommerce_source.sqlite
source_manifest.json
```

`baseline_rebuilt` means the helper reconstructed the teaching baseline from its source records. `live_connection` means a selected connection was backed up. A baseline is not evidence that a student's earlier application changes were captured. The backup operation preserves a database, unlike an order-report CSV or JSON export that represents only a selected result set.

Open the actual repository notebook from the root:

```bash
marimo edit "2 - Migrating the E-Commerce Database from SQLite to PostgreSQL/02_sqlite_to_postgresql.py"
```

The script's opening prose mentions a shorter suggested directory name. The command above uses the actual directory in the reviewed repository. Its runtime locates the repository root through the notebook's parent directory.

---

## Detailed Section Explanations

### 2.1 Inspect a completed source snapshot

The first form accepts an authorized local bundle directory. Its inspection checkbox must be selected and submitted before `load_source()` runs. This step does not connect to PostgreSQL.

#### Manifest and artifact validation

`load_source()` checks the exact manifest fields and the contract `goliath-ecommerce-snapshot/v1`. It accepts only `baseline_rebuilt` and `live_connection` snapshot kinds and the expected introductory-course repository identifier.

It validates digest/revision formats, SQLite version metadata, UTC creation-time metadata, table-count names, and nonnegative integer count values. Optional revision/CSV digest values may remain unknown where the contract permits them; the code does not manufacture missing provenance.

The manifest is limited to 2 MiB and the database to 64 MiB. A nonempty `-wal` file beside the database is rejected: this loader expects a completed self-contained backup bundle, not an actively changing SQLite database.

The database is read once into a byte buffer. Those exact bytes are hashed and deserialized into an independent in-memory SQLite connection. Inspection therefore does not verify one file and then silently reopen a different unchecked version. The temporary connection is set to `PRAGMA query_only=ON` and closed in `finally`.

#### Integrity and supported-profile checks

The code requires:
- `PRAGMA integrity_check` to return `ok`.
- `PRAGMA foreign_key_check` to return no violations.
- The actual object inventory to match the manifest.
- The inventory's SHA-256 signature to match the supported Module 8 profile.
- The observed counts to match the manifest.

The supported signature is:

```text
0653ff1441f8303cd2b1e3214dd3bf9880c1d0883bf96be3f1c5ee1b31192797
```

The inventory includes tables, views, indexes, triggers, and stored SQL. This is an exact profile check, not general schema-equivalence reasoning. An extra index, a staging table, or a differently stored definition can cause rejection even if a human considers the design equivalent. Module 3 snapshots containing `flat_orders` and `reconstructed_flat`, and snapshots with additional reporting objects, are not silently accepted or partially migrated.

Checksums establish consistency with the supplied manifest; they are not digital signatures proving who created or authorized the source.

#### Read and normalize the six business tables

| Table | Source columns |
|---|---|
| `customers` | `customer_id`, `email`, `customer_name` |
| `products` | `sku`, `product_name`, `category` |
| `warehouses` | `warehouse_code`, `warehouse_city` |
| `orders` | `order_id`, `ordered_at`, `order_status`, `customer_id`, `shipping_address_snapshot` |
| `order_items` | `source_row_id`, `order_id`, `line_no`, `sku`, `warehouse_code`, `unit_price_cents`, `quantity` |
| `catalog_observations` | `source_row_id`, `sku`, `warehouse_code`, `observed_price_cents`, `observed_quantity` |

`normalize()` requires integer fields to be actual Python integers within signed BIGINT range. Text fields must be non-NULL strings. `timestamp()` requires the exact `YYYY-MM-DD HH:MM:SS` representation and converts it to a timezone-free Python `datetime`; it does not infer an offset.

The returned plan contains normalized rows, actual counts, row hashes, expected report hashes, a line-total amount, and a token covering both the database bytes and original manifest bytes. Baseline counts are not hardcoded acceptance criteria: a live snapshot can have different data while retaining the supported schema.

`expected_reports()` builds independent Python expectations for line, order-header, and reconstructed-source reports. The displayed total includes all statuses and is described as historical merchandise amount, not recognized revenue.

### 2.2 Review the migration contract

This section explains deliberate target decisions before any write authorization. The optional DDL checkbox displays the fixed SQL statements held in `DDL`; target DDL is not executed from untrusted SQLite schema text.

| Source concern | Implemented target decision |
|---|---|
| Integer-cent amounts | Preserve as `BIGINT` cents; do not convert to binary floats or invent currency |
| Timestamp text without an offset | Validate and store as `TIMESTAMP(0) WITHOUT TIME ZONE` |
| Historical shipping and charged prices | Retain on orders and order lines |
| Customer email | Preserve `UNIQUE NOT NULL` |
| Parent deletion behavior | Preserve `ON DELETE RESTRICT` |
| Repeated SKUs within one order | Permit them; preserve `UNIQUE(order_id, line_no)` instead |
| Order-line `source_row_id` | Rename to application key `order_item_id`, retaining its numeric value |
| Observation `source_row_id` | Rename to `observation_id`, retaining its numeric value |
| Source-to-target identity | Record the snapshot/run, source table/key, and target table/key explicitly |
| Catalog observation quantity | Retain `observed_quantity >= 0`; do not assert inventory availability |
| Existing order statuses | Preserve text, including `DELIVERED` and valid custom live values; add no status CHECK |

#### Application identity is not CSV provenance

Module 8 generates `source_row_id` for new application lines. That inherited name does not prove the row came from the original CSV. Line and observation identifiers can also overlap because they belong to separate tables.

The target therefore uses clearer application-key names and `migration_row_map` for database-row lineage. It does not fill a fictional CSV-provenance column. A mapping answers which source database row became which target row, not whether that row was an original CSV record.

The source uses SQLite `INTEGER PRIMARY KEY`, not `AUTOINCREMENT`. This adapter does not require a `sqlite_sequence` table or invent its state. PostgreSQL generators are synchronized beyond existing positive identifiers; future generated-key behavior is not claimed to reproduce SQLite's rowid-reuse algorithm.

#### Target objects

In addition to the six business tables, the loader creates:

| Object | Purpose |
|---|---|
| `orders_customer_idx` | Index the order-to-customer lookup key |
| `items_sku_idx` | Index order-line SKU lookups |
| `migration_runs` | Record run ID, adapter, source checksum/manifest, timestamp, and validation |
| `migration_row_map` | Record table-qualified source/target key mappings for every business row |
| `v_order_lines` | One row per transactional line, with descriptive fields and exact line amount |
| `v_order_totals` | One row per order header, including headers without lines |
| `reconstructed_flat` | Combine transactional lines and catalog observations with `UNION ALL` |

The target reconstruction uses legacy database identifiers as `row_id`. They may overlap across the two source tables, so they are not a globally unique CSV key. `UNION ALL` preserves both records rather than silently deduplicating them.

### 2.3 Configure the target and run read-only preflight

After source validation, the target form accepts a local configuration-file path and separate authorization for read-only preflight.

`load_config()` reads `.env` through `dotenv_values(..., interpolate=False)`, then overlays process environment variables. Password whitespace is preserved rather than silently trimmed. The fixed role names and course database are validated.

| Setting | Purpose/default |
|---|---|
| `PGHOST` | Endpoint; default `127.0.0.1` |
| `PGPORT` | Default `54329`; valid port range required |
| `PGDATABASE` | Must be `goliath_ecommerce` |
| `PGCONNECT_TIMEOUT` | Default 5 seconds; accepted range 1–30 |
| `PGSSLMODE` | Default `prefer`; explicit supported TLS mode required |
| `PGSSLROOTCERT` | Optional certificate path |
| `COURSE_MIGRATOR_USER/PASSWORD` | Controlled loading identity |
| `COURSE_APP_USER/PASSWORD` | Post-commit application checks |
| `COURSE_ANALYST_USER/PASSWORD` | Post-commit analytical checks |

All three role passwords are required, even though the first target connection uses only the migrator. Missing and `REPLACE_` placeholder passwords block configuration. The `Config` representation redacts credentials, but runtime objects still hold them: variable inspectors are not a secret vault.

`connect()` opens short-lived Psycopg connections with explicit keyword arguments, `autocommit=True`, an application name, a 10-second statement timeout, and a 3-second lock timeout. Connection establishment has its own timeout. Local `sslmode=prefer` is not authenticated TLS; remote use needs an appropriate verified certificate policy.

#### What `guard_target()` verifies

Inside an explicitly read-only transaction, preflight checks:
1. The actual database, session user, and effective user are the expected migration identity.
2. The server belongs to the PostgreSQL 19 (or 18) release series.
3. The four roles exist with expected login flags and without the inspected administrative attributes.
4. Application and analyst roles are not members of the owner or migrator roles.
5. The migrator has `NOINHERIT`.
6. `commerce` exists and belongs to `course_owner`.
7. No relations are already present in `commerce`.
8. Explicit `SET LOCAL ROLE course_owner` succeeds.

This is a targeted classroom guard, not an exhaustive security audit of every possible membership or object type.

The successful result includes an approval token derived from the source token and a new random configuration nonce. Subsequent authorization is tied to that preview/configuration instance. The displayed configuration contains no password.

Changing a submitted source/configuration recreates downstream controls. Editing a file on disk is not an automatic filesystem watcher: resubmit the relevant inspection or preflight form to reload it. The migration additionally rereads the source before execution and rejects a changed source token.

### 2.4 Load in a deliberate transaction

The commit form requires all of the following:
- The exact phrase `MIGRATE commerce`.
- The current preflight approval token.
- An explicit acknowledgment authorizing writes to the course lab.
- An optional failure-injection selection, or `No failure`.

`migrate()` validates these inputs, reloads the source, compares the new token with the preview, and generates a migration ID.

The transaction sequence is:

```text
Connect as course_migrator
    -> BEGIN
    -> acquire transaction-scoped advisory lock
    -> recheck target and SET LOCAL ROLE course_owner
    -> create fixed tables, indexes, ledger, map, and views
    -> record the migration run
    -> insert parents, then dependent rows and key mappings
    -> validate all rows and reports
    -> check mapping count
    -> synchronize generated identifiers
    -> grant the intended access
    -> save validation evidence
    -> COMMIT
```

The target-wide advisory lock serializes cooperating migration attempts. The target guard is repeated after the lock is acquired; the loader does not trust a potentially stale preflight alone.

#### Dependency order and parameterization

The source/target table order is:

```text
customers / products / warehouses
             -> orders
             -> order_items / catalog_observations
```

`cursor.executemany()` loads explicit column lists with bound `%s` values. Identifier text comes from fixed allowlisted table/column definitions and passes through `quote()`; arbitrary source identifiers or SQL are not executed in PostgreSQL.

A map entry is inserted for every row in all six business tables. The total mapping count must equal the total number of source business rows. Source and target keys are JSONB objects qualified by table and migration ID.

#### Generator synchronization and grants

For `customers.customer_id`, `order_items.order_item_id`, and `catalog_observations.observation_id`, the loader finds the existing maximum and uses `setval()` with the appropriate called/not-called state. Empty or nonpositive-only key sets leave the next normal generated value at 1; positive keys advance the generator beyond the maximum.

Within the same transaction:
- `course_app` receives business-table `SELECT`, `INSERT`, `UPDATE`, and `DELETE` privileges plus required sequence access.
- `course_analyst` receives business-table `SELECT` only.
- Both ordinary roles receive schema `USAGE` and read access to the reports and migration metadata.

These are grants for the objects created by this migration, not a general default-privilege policy for every future table.

#### Rollback exercise and reruns

Selecting a failure point raises `MigrationError` immediately after that table's rows and mappings are loaded. A useful exercise is failure after `orders` or `order_items`: earlier inserts and freshly created target objects must not remain after a successful rollback.

The function catches pre-commit failures, explicitly attempts `ROLLBACK`, records the outcome, and closes the connection. It does not provide `DROP`, `TRUNCATE`, disabled constraints, blanket conflict-ignore, or automatic reset behavior. After a successful migration, the occupied-target guard intentionally refuses reruns.

### 2.5 Interpret evidence, not just a green connection

#### Complete row and report reconciliation

`digest_rows()` canonicalizes each row, serializes values deterministically, sorts the serialized rows, and hashes the collection. Sorting removes reliance on database return order while preserving duplicate multiplicity. Datetimes become canonical timestamp text; integral PostgreSQL `Decimal` results become integers without losing cents.

`validate_target()` compares:
- Counts and full canonical-row hashes for each of the six tables, accounting for renamed key columns.
- All rows returned by `v_order_lines`.
- All rows returned by `v_order_totals`.
- All rows returned by `reconstructed_flat`.

Expected report rows are calculated independently in Python from the normalized source. They are not simply copied from the target query being tested. A migration cannot pass merely because it contains the right number of incorrect rows.

Line multiplication and totals use exact integer/NUMERIC arithmetic. The target explicitly casts before multiplication so a valid pair of BIGINT values does not first overflow a BIGINT intermediate. Order headers without lines retain `line_count=0` and `amount_cents=NULL`; the code does not silently turn missing line amounts into a business assertion of zero revenue.

For the unchanged teaching fixture, counts are customers 3, products 4, warehouses 3, orders 5, order_items 6, and catalog_observations 1. Its all-status merchandise total is 131740 cents. These are reference values for that fixture, not universal requirements for a live snapshot.

#### Ordinary-role checks happen after commit

`assess_roles()` opens separate application and analyst connections. It verifies actual identities, rereads the migrated rows and reports in read-only transactions, and checks individual table privileges.

It then attempts:

```sql
UPDATE commerce.orders
SET order_status = order_status
WHERE FALSE;
```

The statement runs in a normal read/write transaction with `force_rollback=True`. Application permission should allow it; the analyst should receive SQLSTATE `42501`. An unrelated error does not pass the expected-denial check.

Because the predicate matches no rows, this tests statement authorization—not successful business-row modification, order creation, row-level policy behavior, or a complete application service. Those need additional tests and later course work.

#### Commit states and recovery

| `commit_state` | Meaning | Appropriate interpretation |
|---|---|---|
| `not_started` | Preconditions/connection failed before the migration transaction ran | Resolve the reported prerequisite; no successful migration is claimed |
| `rolled_back` | Pre-commit failure followed by acknowledged rollback | Inspect the target and rerun preflight before a deliberate retry |
| `committed` | COMMIT returned successfully | Interpret post-commit role checks separately; they cannot undo the accepted data |
| `unknown` | Commit acknowledgment or rollback confirmation was uncertain | Do not blindly reload; inspect the run ledger and target with a fresh authorized connection |

`ready_for_module_3` becomes true only after an acknowledged commit and successful ordinary-role checks. A committed migration with failed role checks remains committed but not ready.

For an uncertain outcome, use the reported `migration_id` to inspect `commerce.migration_runs` and verify data, counts, and checksum. Do not assume an error means nothing committed, and do not use a destructive reset as the first recovery step.

Sequence allocations are generally not reclaimed by rollback. Newly created identity sequences are removed if their creating DDL transaction rolls back, but gaps in already existing sequences are not evidence of a broken transaction.

#### Exported evidence and testing boundary

The final download serializes the actual `outcome` into JSON with `allow_nan=False`. It includes commit state, run ID, source checksum, validation/access results where available, and redacted failure/recovery information.

`error_summary()` deliberately excludes raw driver messages, connection URLs, passwords, and row values. A credential-free report is still operational material that should be reviewed before sharing. Database bundles and runtime inspectors can expose customer data.

This notebook contains runtime reconciliation and a failure-injection exercise. It does not contain a standalone pytest suite, prove production readiness, or establish that live PostgreSQL/Marimo validation has already been performed. The separate local-source tests validate the copied source helper and fixture, not the entire migration.

---

## Assessment & Submission Checklist

| Area | Weight | Evidence |
|---|---:|---|
| Source inventory and migration contract | 20% | Reviewed manifest/profile, snapshot kind, and source-accounting notes |
| Representation and identity decisions | 20% | Explanation of cents, timezone-free timestamps, key renames, and provenance limits |
| Transactional loading and recovery | 25% | A successful load and an injected-failure/rollback demonstration |
| Row and report reconciliation | 25% | Complete parity results and explanation of row grain and NULL amounts |
| Privileges and reproducibility | 10% | Ordinary-role results, safe configuration procedure, rerun/recovery explanation |

Students submit the reviewed migration report, source-to-target mapping explanation, failure/recovery evidence, and the commands/assumptions needed to reproduce the lab. Never submit `.env` credentials or publish customer-containing database bundles by default.

## Scope Boundary & Next Module

This initial implementation supports exactly the pinned Module 8 six-table source profile. It blocks unreviewed object/schema changes, uses bounded in-memory processing, and requires Python/SQLite support for `Connection.deserialize()`.

Module 3 can build on a verified PostgreSQL target to study PostgreSQL SQL behavior, isolation, locking, and concurrent transactions. DuckDB 2.0 and SQLAlchemy remain later analytical and application interfaces; they are not substitutes for demonstrating migration preservation here.

## Technical References

- Reviewed implementation commit: https://github.com/Goliath-Research/PostgreSQL-with-Python/commit/4c17468edfcf20d168fb716b0f410d2a6dc9da9b
- Local source contract/provenance: `fixtures/intro_ecommerce/README.md`
- Python SQLite connection and backup APIs: https://docs.python.org/3/library/sqlite3.html
- Psycopg transaction management: https://www.psycopg.org/psycopg3/docs/basic/transactions.html
- PostgreSQL identity columns: https://www.postgresql.org/docs/19/ddl-identity-columns.html
- PostgreSQL sequence behavior: https://www.postgresql.org/docs/19/functions-sequence.html
