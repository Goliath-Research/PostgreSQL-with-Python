from datetime import date
import duckdb

ROWS = ((101, "2026-01-01", "Books", 1200),
        (101, "2026-01-01", "Games", 800),
        (102, "2026-01-02", "Books", 300))
MAX_LINES = 1000


def category_sales(rows, start, end, limit):
    if not 1 <= limit <= 25:
        raise ValueError("limit must be 1–25")
    if not 1 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 31:
        raise ValueError("Use a positive date range of at most 31 days")
    if len(rows) > MAX_LINES:
        raise ValueError("Too many input lines; narrow the date range")
    with duckdb.connect(":memory:") as db:
        db.execute("CREATE TABLE lines (order_id BIGINT, day DATE, category VARCHAR, cents BIGINT)")
        if rows:
            db.executemany("INSERT INTO lines VALUES (?, ?, ?, ?)", rows)
        result = db.execute("""
            SELECT category, SUM(cents) FROM lines WHERE day >= ? AND day < ?
            GROUP BY category ORDER BY SUM(cents) DESC, category LIMIT ?
        """, [start, end, limit]).fetchall()
    return [{"category": category, "revenue_cents": cents} for category, cents in result]
