# Module 7: SQLAlchemy Core & Connections

Use the course virtual environment with Marimo and SQLAlchemy 2.0 installed. The notebook uses ephemeral SQLite for the transaction exercise, and the companion script uses PostgreSQL through Psycopg 3.

```powershell
python -m marimo check "7 - SQLAlchemy Core & Connections/07_sqlalchemy_core_and_connections.py"
python -m unittest discover -s "7 - SQLAlchemy Core & Connections/tests" -v
python -m marimo edit "7 - SQLAlchemy Core & Connections/07_sqlalchemy_core_and_connections.py"
```

## Engine, Connection, and SQL expressions

The Engine packages a dialect and connection pool. Check out a Connection with `engine.connect()`. `select()` constructs a statement without executing it. `bindparam()` names a value that is supplied separately to `execute()`. At cutoff 2, the compiled SQLite SQL shows `?`; the bound value is displayed separately. Parameters stand for values, not table or column names.

## Commit and rollback

`engine.begin()` commits the two fixture inserts when the block exits normally and rolls back if an exception escapes. The second insert exercise uses `conn.begin()` and explicitly rolls back. At cutoff 2, expect ID 2 before the transaction, IDs 2 and 3 inside it, and ID 2 again after rollback. The last read uses a fresh Connection context, not necessarily a different physical connection. Try cutoff 5: only the uncommitted row qualifies. This tests DML, not SQLite DDL or PostgreSQL isolation.

## PostgreSQL companion: course_app

Start the existing course database. Set `PGHOST`, `PGPORT`, and `PGDATABASE` in your shell as needed (defaults: localhost, 5432, goliath_ecommerce). The script prompts for the course_app password without echoing it. It never reads or changes the project .env and never prints a DSN. Do not put the password on the command line.

```powershell
python "7 - SQLAlchemy Core & Connections/07_postgresql_probe.py" --quantity 3
```

This uses `postgresql+psycopg`, enables read-only mode for the transaction, executes a `text()` statement with a bound integer, and checks the actual login and read-only setting. Expect role `course_app`, quantity `3`, and read-only `on`. It makes no persistent writes. Compare the script's `:quantity` syntax to the notebook's compiled SQLite placeholder; neither requires formatting a value into SQL text. PostgreSQL write transactions are not covered by the probe.
