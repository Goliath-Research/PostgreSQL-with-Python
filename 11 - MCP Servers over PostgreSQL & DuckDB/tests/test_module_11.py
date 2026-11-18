import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from module_11_reporting import ROWS, category_sales


class ReportingTests(unittest.TestCase):
    def test_top_category(self):
        self.assertEqual(category_sales(ROWS, "2026-01-01", "2026-01-03", 1),
                         [{"category": "Books", "revenue_cents": 1500}])

    def test_end_exclusive(self):
        self.assertEqual(category_sales(ROWS, "2026-01-01", "2026-01-02", 1)[0]["revenue_cents"], 1200)

    def test_cap_rejects_instead_of_truncating(self):
        with self.assertRaises(ValueError):
            category_sales(ROWS * 334, "2026-01-01", "2026-01-03", 1)


@unittest.skipUnless(importlib.util.find_spec("mcp") and importlib.util.find_spec("sqlalchemy"), "MCP SDK or SQLAlchemy unavailable")
class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio(self):
        spec = importlib.util.spec_from_file_location("lab_client", root / "11_mcp_client.py")
        client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(client)
        async with asyncio.timeout(30):
            tools, resource, lookup, rollup, invalid = await client.smoke()
        self.assertEqual(tools, {"get_order_summary", "get_category_sales"})
        self.assertIn("integer cents", resource.contents[0].text)
        self.assertFalse(lookup.isError)
        self.assertFalse(rollup.isError)
        self.assertIn("2000", lookup.model_dump_json())
        self.assertIn("1500", rollup.model_dump_json())
        self.assertTrue(invalid.isError)


@unittest.skipUnless(os.getenv("COURSE_MCP_TEST_POSTGRES") == "1", "PostgreSQL test is opt-in")
class PostgresTests(unittest.TestCase):
    def test_privileges(self):
        from sqlalchemy import create_engine, text
        engine = create_engine(os.environ["COURSE_MCP_DATABASE_URL"], hide_parameters=True)
        try:
            with engine.connect() as conn:
                self.assertEqual(conn.scalar(text("SELECT current_user")), "mcp_analyst")
                self.assertEqual(conn.scalar(text("SELECT count(*) FROM mcp_lab.sales_lines")), 3)
                for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                    self.assertFalse(conn.scalar(text("SELECT has_table_privilege('mcp_lab.sales_lines', :p)"), {"p": privilege}))
                self.assertFalse(conn.scalar(text("SELECT has_table_privilege('mcp_lab.restricted_fixture', 'SELECT')")))
        finally:
            engine.dispose()
