import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
HELPER = ROOT / '8 - Python Database Integration & Capstone' / 'ecommerce_snapshot.py'
SPEC = importlib.util.spec_from_file_location('local_ecommerce_snapshot', HELPER)
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)


class LocalSourceTests(unittest.TestCase):
    def test_default_csv_stays_with_fixture(self):
        self.assertEqual(
            snapshot.DEFAULT_CSV,
            ROOT / '1 - The Relational Model' / 'messy_ecommerce_orders.csv',
        )
        self.assertTrue(snapshot.DEFAULT_CSV.is_file())

    def test_exact_upstream_files(self):
        expected = {
            HELPER: '28a27f8b703e2e65de01a7521b5d5979034b6a82',
            ROOT / '1 - The Relational Model' / 'messy_ecommerce_orders.csv': '1a67452f45edcdcdfb9fc1aa50a1c38877411e47',
            ROOT / 'LICENSE': 'bd1b06e8458a26976268c9d091b250b40ecd54c7',
        }
        for path, wanted in expected.items():
            data = path.read_bytes()
            digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            self.assertEqual(digest, wanted, str(path))

    def test_baseline_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / 'baseline'
            manifest = snapshot.rebuild_baseline(bundle)
            self.assertEqual(snapshot.verify_snapshot(bundle), manifest)
            self.assertEqual(manifest['table_counts'], dict(zip(snapshot.TABLES, (3, 4, 3, 5, 6, 1))))
            self.assertEqual(manifest['snapshot_kind'], 'baseline_rebuilt')
            self.assertEqual(manifest['schema_signature'], '0653ff1441f8303cd2b1e3214dd3bf9880c1d0883bf96be3f1c5ee1b31192797')
            db = sqlite3.connect(bundle / 'ecommerce_source.sqlite')
            try:
                self.assertEqual(db.execute('SELECT SUM(unit_price_cents*quantity) FROM order_items').fetchone()[0], 131740)
            finally:
                db.close()

    def test_live_export_and_identifier_overlap(self):
        records, _ = snapshot.read_source()
        db = snapshot.build_application_database(records)
        try:
            db.execute('INSERT INTO order_items(order_id,line_no,sku,warehouse_code,unit_price_cents,quantity) SELECT order_id,99,sku,warehouse_code,unit_price_cents,quantity FROM order_items LIMIT 1')
            overlap = db.execute('SELECT COUNT(*) FROM order_items WHERE source_row_id IN (SELECT source_row_id FROM catalog_observations)').fetchone()[0]
            self.assertEqual(overlap, 1)
            with tempfile.TemporaryDirectory() as tmp:
                bundle = Path(tmp) / 'live'
                manifest = snapshot.export_snapshot(db, bundle)
                self.assertEqual(snapshot.verify_snapshot(bundle), manifest)
                self.assertEqual(manifest['snapshot_kind'], 'live_connection')
                self.assertIsNone(manifest['source_csv_sha256'])
                self.assertEqual(manifest['table_counts']['order_items'], 7)
            self.assertEqual(db.execute('SELECT 1').fetchone()[0], 1)
        finally:
            db.close()

    def test_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / 'existing'
            bundle.mkdir()
            marker = bundle / 'keep.txt'
            marker.write_text('preserve me', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                snapshot.rebuild_baseline(bundle)
            self.assertEqual(marker.read_text(encoding='utf-8'), 'preserve me')


if __name__ == '__main__':
    unittest.main()
