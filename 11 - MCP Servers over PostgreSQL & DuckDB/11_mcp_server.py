import os
from datetime import date
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from module_11_reporting import MAX_LINES, ROWS, category_sales

mcp = FastMCP("course-commerce-reporting")


def make_engine():
    value = os.environ.get("COURSE_MCP_DATABASE_URL")
    if value is None:
        return None
    try:
        url = make_url(value)
        if url.drivername != "postgresql+psycopg" or url.username != "mcp_analyst" or url.query:
            raise ValueError
        return create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    except (SQLAlchemyError, ValueError, ImportError):
        raise SystemExit("Invalid PostgreSQL configuration for mcp_analyst") from None


engine = make_engine()


def fetch(sql, params):
    try:
        with engine.begin() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout = '3s'"))
            if conn.scalar(text("SELECT current_user")) != "mcp_analyst":
                raise ValueError("Unexpected database role")
            return [tuple(row) for row in conn.execute(text(sql), params)]
    except SQLAlchemyError:
        raise ValueError("Reporting database query failed") from None


@mcp.resource("schema://commerce/reporting")
def reporting_schema() -> str:
    return ("Approved sales lines: order_id, day, category, cents. Amounts are integer cents. "
            "Only eligible sales are included; ranges are [start, end). No personal data.")


@mcp.tool()
def get_order_summary(order_id: Annotated[int, Field(ge=1, le=2147483647)]) -> dict:
    """Summarize eligible sales lines for one order, without personal data."""
    if engine is None:
        values = [row[3] for row in ROWS if row[0] == order_id]
        count, cents = len(values), sum(values)
    else:
        count, cents = fetch("""SELECT count(*), coalesce(sum(cents), 0)
            FROM mcp_lab.sales_lines WHERE order_id = :order_id""", {"order_id": order_id})[0]
    return {"order_id": order_id, "line_count": count, "revenue_cents": int(cents)}


@mcp.tool()
def get_category_sales(start_date: date, end_date: date,
                       limit: Annotated[int, Field(ge=1, le=25)] = 10) -> list[dict]:
    """Rank categories by eligible revenue in a bounded half-open date range."""
    if not 1 <= (end_date - start_date).days <= 31:
        raise ValueError("Use a positive date range of at most 31 days")
    if engine is None:
        rows = ROWS
    else:
        rows = fetch("""SELECT order_id, day, category, cents FROM mcp_lab.sales_lines
            WHERE day >= :start_date AND day < :end_date LIMIT :cap""",
            {"start_date": start_date, "end_date": end_date, "cap": MAX_LINES + 1})
    return category_sales(rows, start_date.isoformat(), end_date.isoformat(), limit)


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    finally:
        if engine is not None:
            engine.dispose()
