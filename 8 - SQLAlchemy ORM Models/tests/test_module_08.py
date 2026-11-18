import sys
from pathlib import Path
import unittest

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from module_08_models import Base, Order, fixture_engine, run_lab


class ModelTests(unittest.TestCase):
    def test_navigation(self):
        result = run_lab(1)
        self.assertEqual([row["order_id"] for row in result["orders"]], [101, 102])
        self.assertTrue(all(row["back_reference_is_customer"] and row["customer_id"] == 1 for row in result["orders"]))

    def test_identity_scope(self):
        result = run_lab(1)
        self.assertTrue(result["same_session_get_is_same_object"])
        self.assertTrue(result["same_session_select_is_same_object"])
        self.assertTrue(result["other_session_has_same_key"])
        self.assertFalse(result["other_session_is_same_object"])

    def test_empty_and_missing(self):
        self.assertEqual(run_lab(2)["orders"], [])
        self.assertEqual(run_lab(99), {"found": False, "customer_id": 99})

    def test_foreign_key_enforced(self):
        engine = fixture_engine()
        try:
            Base.metadata.create_all(engine)
            with self.assertRaises(IntegrityError), Session(engine) as session, session.begin():
                session.add(Order(order_id=1, customer_id=999, status="placed"))
        finally:
            engine.dispose()
