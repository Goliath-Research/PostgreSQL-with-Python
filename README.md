# PostgreSQL with Python: Analytics, ORM, and Database Applications
**Hosted lab architecture and operator requirements:** [HOSTED_LABS.md](HOSTED_LABS.md) — current execution modes, security boundaries, and outstanding hosting work.

**Institution:** Goliath Research Academy  
**Delivery Format:** Interactive Marimo Reactive Notebooks (`.py`), Module Reference Guides (`*_content.md`), Reproducible PostgreSQL 18 Laboratory (`compose.yaml`), DuckDB 2.0, SQLAlchemy 2.0, and Automated Verification Suites  
**Prerequisites:** Completion of *Introduction to Databases: Relational Foundations & Python Integration* (8-module SQLite course); Python 3.11+, SQL fundamentals, and basic terminal usage

---

## 1. Course Overview & Architectural Philosophy

Building directly on the normalized e-commerce domain from the introductory SQLite course, this 10-module advanced course establishes **PostgreSQL** as an authoritative client/server relational database accessed through two complementary Python interfaces separated by responsibility:

* **DuckDB 2.0** for analytical queries, lazy relational transformations, execution-placement control, and dataframe/Arrow exports.
* **SQLAlchemy 2.0 (Core + ORM + Sessions)** for transactional application development, object mapping, unit-of-work management, and schema migrations.

The central distinction is **analytical work versus application persistence**—not two interchangeable ways of querying the same database:

```text
                            PostgreSQL
                 Authoritative relational database
                                │
                  ┌─────────────┴─────────────┐
                  │                           │
        Analytical workflows        Application workflows
                  │                           │
             DuckDB 2.0                  SQLAlchemy
       Python relational API       Core + ORM + Sessions
                  │                           │
       Filter, join, aggregate,    Entities, relationships,
       analyze, export results     transactions, persistence
```

### Core Pedagogical Principles
1. **Least-Privilege Role Separation:**
   * `course_owner` (`NOLOGIN`): Owns schemas (`commerce`, `lab`) and relational objects.
   * `course_migrator` (`LOGIN`, `NOINHERIT`): Performs controlled schema migrations by explicitly assuming `course_owner`.
   * `course_app` (`LOGIN`): Used by Psycopg 3 and SQLAlchemy for transactional reads and writes on permitted tables.
   * `course_analyst` (`LOGIN`): Used by DuckDB 2.0 for read-only analytical queries.
2. **DuckDB as an Analytical Execution Engine (Not Just a Pandas Wrapper):**
   * A DuckDB relation represents a **lazy query**, not an already-materialized in-memory dataframe.
   * Re-reading a relation can re-execute the query; converting to pandas or Arrow is an explicit execution and materialization boundary.
   * Students compare querying attached PostgreSQL tables through DuckDB, explicitly routing queries to PostgreSQL (`CONNECT` mode), and extracting bounded datasets for local processing.
3. **SQLAlchemy from Core to ORM:**
   * Students learn SQLAlchemy Core (`Engine`, connections, parameterized SQL expressions) before declarative ORM mappings and `Session` lifecycle (`flush` vs. `commit`, rollback, object identity, and emitted SQL inspection).

---

## 2. Ten-Module Syllabus (Three Stages)

### Stage A — Migrate and Establish the Server Database
| Module | Directory & Script | Focus |
| :---: | :--- | :--- |
| **1** | `1 - PostgreSQL Environment/01_postgresql_environment.py` | Reproducible PostgreSQL environment, namespaces (`commerce`, `lab`), role hierarchy, secret-safe configuration, Psycopg 3 connectivity, privilege verification on `lab.connection_probe`, and readiness reporting |
| **2** | `2 - Migrating the E-Commerce Database from SQLite to PostgreSQL/02_sqlite_to_postgresql.py` | Schema migration into `commerce`, deliberate design refinements, data loading, identifier handling, and post-migration validation |
| **3** | `3 - PostgreSQL SQL & Transactions/03_postgresql_sql_and_transactions.py` | PostgreSQL SQL behavior, strict types (`TIMESTAMPTZ`, `NUMERIC`), isolation levels, locking, and concurrency experiments |

### Stage B — Analytical Access with DuckDB 2.0
| Module | Directory & Script | Focus |
| :---: | :--- | :--- |
| **4** | `4 - DuckDB PostgreSQL Connection/04_duckdb_postgresql_connection.py` | PostgreSQL extension setup, read-only access as `course_analyst`, attached tables, `CONNECT` mode, and execution placement |
| **5** | `5 - Pythonic Relational Analytics/05_pythonic_relational_analytics.py` | Filtering, projection, joins, grouping, aggregation, generated SQL inspection, and lazy evaluation |
| **6** | `6 - Analytical Reporting & Performance/06_analytical_reporting_and_performance.py` | Window calculations, pandas/Arrow materialization boundaries, exports, and measured comparisons |

### Stage C — Application Persistence with SQLAlchemy 2.0
| Module | Directory & Script | Focus |
| :---: | :--- | :--- |
| **7** | `7 - SQLAlchemy Core & Connections/07_sqlalchemy_core_and_connections.py` | Engines, connections, SQL expressions, bound parameters, and explicit transactions |
| **8** | `8 - SQLAlchemy ORM Models/08_sqlalchemy_orm_models.py` | Declarative mappings, primary/foreign keys, relationships, and object identity |
| **9** | `9 - Sessions & Transactional Services/09_sessions_and_transactional_services.py` | Session scope, `flush` vs. `commit`, rollback, loading behavior, and transactional order services |
| **10** | `10 - Migrations, Testing & Capstone/10_migrations_testing_and_capstone.py` | Alembic migrations, integration tests, reporting, and the dual-deliverable application capstone |

---

## 3. Deliberate Schema Refinements Across the Migration

While keeping the e-commerce entities and business questions from the introductory SQLite course, Stage A uses the migration into `commerce` to resolve and test explicit design decisions:
* Separate the application's order-line identifier (`order_item_id`) from imported CSV provenance (`source_row_id`).
* Establish and document an explicit monetary representation and currency policy (integer cents vs. `NUMERIC(12, 2)`).
* Define a `TIMESTAMPTZ` timezone policy before converting imported ISO-8601 timestamp text.
* Preserve charged prices on `order_items` and shipping-address snapshots on `orders`.
* Keep `catalog_observations` separate from transactional orders and inventory claims.
* Document whether customer `email` uniqueness remains an enforced database constraint and application rule.
* Verify keys, relationships, row counts, monetary totals, and reconstructed reports through automated tests before declaring migration complete.

---

## 4. Reproducible Laboratory Setup

### Repository Layout
```text
PostgreSQL-with-Python/
├── compose.yaml
├── .env.example
├── .gitignore
├── LICENSE
├── pyproject.toml
├── README.md
├── bootstrap/
│   ├── 01_roles_and_database.sql
│   └── 02_schemas_and_probe.sql
└── 1 - PostgreSQL Environment/
    ├── 01_postgresql_environment.py
    └── 01_content.md
```

### Primary Path: Containerized PostgreSQL 18 Laboratory
1. **Create your local `.env` configuration from the template:**
   ```bash
   cp .env.example .env
   ```
2. **Start the PostgreSQL container and wait for health readiness:**
   ```bash
   docker compose up -d
   docker compose ps
   ```
   On first initialization of the `goliath_pgdata` volume, PostgreSQL automatically executes `bootstrap/01_roles_and_database.sql` and `bootstrap/02_schemas_and_probe.sql`.
3. **Normal Shutdown vs. Destructive Reset:**
   * **Stop without losing data (preserves `goliath_pgdata`):**
     ```bash
     docker compose stop
     docker compose start
     ```
   * **Destructive reset (deletes `goliath_pgdata` and re-runs `/docker-entrypoint-initdb.d/` on next `up`):**
     ```bash
     docker compose down -v
     ```

### Alternative Path: Native PostgreSQL 18 Installation
If you run a local native PostgreSQL 18 server instead of Docker:
1. Ensure PostgreSQL is listening solely on `127.0.0.1` and update `PGPORT` in `.env` to match your local port.
2. Create the `goliath_ecommerce` database as a superuser (`createdb -U postgres goliath_ecommerce`).
3. Execute the bootstrap scripts in order:
   ```bash
   psql -v ON_ERROR_STOP=1 -U postgres -d goliath_ecommerce -f bootstrap/01_roles_and_database.sql
   psql -v ON_ERROR_STOP=1 -U postgres -d goliath_ecommerce -f bootstrap/02_schemas_and_probe.sql
   ```

### Running the Marimo Notebooks
Install dependencies in a Python 3.11+ virtual environment and launch Marimo:
```bash
pip install -e .
marimo edit "1 - PostgreSQL Environment/01_postgresql_environment.py"
```

---

## 5. Dual-Interface Capstone (Module 10)

The course culminates in a capstone operating over the single `goliath_ecommerce` database with two concrete deliverables:
1. **Analytical Deliverable (DuckDB 2.0 as `course_analyst`):**
   * Customer-order analysis with order totals and status filters, product/category summaries, running totals, customer rankings, explicit treatment of missing values and denominators, and a documented execution-placement and data-transfer strategy.
2. **Operational Deliverable (SQLAlchemy 2.0 ORM as `course_app`):**
   * Customer and order retrieval, atomic creation of an order and its lines, a guarded order-cancellation workflow, automatic rollback after an invalid line item, emitted SQL inspection, and integration tests covering relationships and transaction boundaries.

---

## 6. Institutional & Disclosure Notice
* **Non-Credit / Portfolio Alignment:** Courses offered directly through **Goliath Research Academy** (`academy.goliathresearch.com`) are non-credit professional and technical training modules. While aligned with Florida Statewide Course Numbering System (SCNS) competencies for portfolio and prior-learning assessment (PLA) documentation, direct college credit is awarded solely at the discretion of accredited receiving institutions.
