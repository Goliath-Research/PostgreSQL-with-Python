import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import module_04_support as lab

class OfflineTests(unittest.TestCase):
    def test_sample_bounds(self):
        for n in (1, 25, 500):
            self.assertTrue(lab.sample_sql(n).endswith(f'LIMIT {n}'))
        for n in (0, 501, True, '2; SELECT 1', 1.5):
            with self.assertRaises(ValueError):
                lab.sample_sql(n)

    def test_sql_literal(self):
        self.assertEqual(lab.sql_string("O'Brien"), "'O''Brien'")
        with self.assertRaises(ValueError):
            lab.sql_string(chr(0))

    def test_config_and_redaction(self):
        with patch.dict(os.environ, {'PGPORT':'5432', 'COURSE_ANALYST_PASSWORD':' sample-secret '}, clear=True):
            settings = lab.Settings.load('absent-module04.env')
            self.assertEqual(settings.port, 5432)
            self.assertEqual(settings.password, ' sample-secret ')
            self.assertNotIn(settings.password, repr(settings))
            with patch.dict(os.environ, {'COURSE_ANALYST_USER':'postgres'}):
                with self.assertRaises(lab.LabError):
                    lab.Settings.load('absent-module04.env')

    def test_local_aggregate_is_exact(self):
        import duckdb
        with duckdb.connect(':memory:') as db:
            db.execute('CREATE TABLE line_sample(unit_price_cents BIGINT, quantity BIGINT)')
            self.assertEqual(db.execute(lab.LOCAL).fetchone(), (0, None))
            db.execute('INSERT INTO line_sample VALUES (1000000000000000000, 20), (199, 3)')
            self.assertEqual(db.execute(lab.LOCAL).fetchone(), (2, 20000000000000000597))

class IntegrationTests(unittest.TestCase):
    @unittest.skipUnless(os.getenv('MODULE04_TEST_ENV'), 'set MODULE04_TEST_ENV to opt in')
    def test_populated_postgres_lab(self):
        report = lab.run(os.environ['MODULE04_TEST_ENV'], 3)
        self.assertEqual(report['postgres_role'], 'course_analyst')
        self.assertTrue(report['postgres_read_only'])
        self.assertTrue(report['local_aggregate_after_detach'])
        self.assertGreater(report['sampled_lines'], 0, 'populate Module 2 first')
        self.assertLessEqual(report['sampled_lines'], 3)
        self.assertIsInstance(report['sampled_cents'], int)
