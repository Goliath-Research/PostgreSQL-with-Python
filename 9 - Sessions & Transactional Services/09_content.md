# Module 9: Sessions & Transactional Services

Use the same `.venv` as Modules 7 and 8 (Marimo and SQLAlchemy 2.0). This is a self-contained SQLite fixture, not a migration or integration test for PostgreSQL `commerce`.

```powershell
.\.venv\Scripts\python.exe -m marimo check "9 - Sessions & Transactional Services/09_sessions_and_transactional_services.py"
.\.venv\Scripts\python.exe -m unittest discover -s "9 - Sessions & Transactional Services/tests" -v
.\.venv\Scripts\python.exe -m marimo edit "9 - Sessions & Transactional Services/09_sessions_and_transactional_services.py"
```

## Trace the transaction

`sessionmaker.begin()` supplies a short-lived Session and transaction for the whole order. `flush()` sends SQL and obtains a generated ID without committing. The fixture flushes each line separately so the invalid case can show one successful line INSERT before the second line fails. This per-line flush is for demonstration, not a batching recommendation. The database `CHECK` rejects zero. Catch `IntegrityError` outside the transaction block so the context manager handles cleanup. A separate Session verifies the final state; no ORM instance is returned from the service.

| Scenario | Lines flushed for attempt | Attempt persists | Total orders / lines | Lazy / select-in SELECTs |
|---|---:|---|---|---|
| Valid | 2 | Yes | 4 / 5 | 5 / 2 |
| Invalid second line | 1 | No | 3 / 3 | 4 / 2 |

## Compare loading behavior

Both strategies return the same order and line data. Lazy loading issues a SELECT for the orders, then one per order as its collection is accessed (the N+1 pattern). `selectinload` issues a second SELECT with an IN list for this small fixture. Larger sets may require multiple batches. Fresh Sessions prevent one strategy from benefiting from loaded state left by the other. Compare the SQL shapes; query count is not a timing benchmark.

Practice: predict the counts if only the first order's lines are accessed. Then modify the loader to verify your prediction.
