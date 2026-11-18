from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from module_10_lab import migration_lab


class MigrationTests(unittest.TestCase):
    def test_existing_data_after_upgrade(self):
        self.assertEqual(migration_lab()["upgraded"],
                         {"id": 1, "total_cents": 1250, "status": "placed"})

    def test_downgrade_preserves_base_data_and_revision(self):
        result = migration_lab()
        self.assertEqual(result["downgraded_columns"], ["id", "total_cents"])
        self.assertEqual(result["retained_row"], {"id": 1, "total_cents": 1250})
        self.assertEqual(result["final_revision"], "0001")
