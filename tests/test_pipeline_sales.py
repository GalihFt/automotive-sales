import csv
import tempfile
import unittest
from pathlib import Path

from pipeline_sales import COLUMNS, ROOT, local_ids, read_batch, validate


class SalesValidationTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(zip(COLUMNS, [
            "ORDER-TEST", "2026-11-01", "D001", "V001", "1",
            "265000000.00", "pending", "2026-11-01 10:00:00",
        ]))

    def test_valid_row_has_database_types(self):
        record = validate(self.row, {"D001"}, {"V001"})
        self.assertEqual(record["qty"], 1)
        self.assertEqual(record["order_date"].isoformat(), "2026-11-01")

    def test_reject_invalid_business_values_and_database_bounds(self):
        cases = [
            ("qty", "-1"), ("qty", "32768"), ("qty", "1.5"),
            ("unit_price", "NaN"), ("unit_price", "Infinity"),
            ("unit_price", "1000000000000000000"), ("unit_price", "1.001"),
            ("dealer_id", "D999"), ("vehicle_id", "V999"),
            ("status", "unknown"), ("order_id", "x" * 51),
            ("order_date", "2026-02-30"), ("updated_at", ""),
            ("updated_at", "2026-10-01 00:00:00"),
            ("updated_at", "2026-11-01T10:00:00+07:00"),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate({**self.row, key: value}, {"D001"}, {"V001"})

    def test_duplicate_and_malformed_rows_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sales.csv"
            with path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerow(self.row)
                writer.writerow(self.row)
                writer.writerow({**self.row, "order_id": "BAD", "qty": "0"})
                handle.write("too,few,columns\n")
            accepted, rejected = read_batch(path, {"D001"}, {"V001"})
        self.assertEqual(len(accepted), 1)
        self.assertEqual([r["line"] for r in rejected], [3, 4, 5])
        self.assertIn("duplikat", rejected[0]["reason"])

    def test_sample_contains_new_orders_update_and_two_rejections(self):
        accepted, rejected = read_batch(
            ROOT / "data/incoming/sales_2026_11.csv",
            local_ids("dealers.csv", "dealer_id"),
            local_ids("vehicles.csv", "vehicle_id"),
        )
        self.assertEqual(len(accepted), 11)
        self.assertEqual(len(rejected), 2)
        with (ROOT / "data/sales.csv").open(newline="", encoding="utf-8-sig") as handle:
            original = {r["order_id"]: r for r in csv.DictReader(handle)}
        updates = [r for r in accepted if r["order_id"] in original]
        self.assertEqual(len(updates), 1)
        self.assertEqual(original[updates[0]["order_id"]]["status"], "pending")
        self.assertEqual(updates[0]["status"], "delivered")


if __name__ == "__main__":
    unittest.main()
