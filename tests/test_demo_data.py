"""Keep sample bytes, source spacing, and documented threshold patterns reproducible."""

import collections
import csv
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import generate_demo_data as demo


class DemoDataTests(unittest.TestCase):
    def test_published_data_reproduces_exactly_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "demo.csv"
            demo.generate(path)
            self.assertEqual(path.read_bytes(), (ROOT / "data/demo_hvac.csv").read_bytes())
            with self.assertRaises(FileExistsError):
                demo.generate(path)

    def test_complete_unique_finite_groups_and_utc_spacing(self):
        rows = list(demo.demo_rows())
        self.assertEqual(len(rows), 720)
        groups = collections.defaultdict(list)
        keys = set()
        for row in rows:
            key = (row["timestamp"], row["equipment_id"], row["sensor"])
            self.assertNotIn(key, keys)
            keys.add(key)
            groups[row["timestamp"]].append(row)
        self.assertEqual(len(groups), 120)
        self.assertEqual({len(group) for group in groups.values()}, {6})
        dates = [datetime.fromisoformat(stamp) for stamp in groups]
        self.assertEqual(dates[0], demo.START)
        self.assertTrue(all(b - a == timedelta(minutes=15) for a, b in zip(dates, dates[1:])))
        self.assertEqual(dates[-1] - dates[0], timedelta(hours=29, minutes=45))

    def test_documented_sustained_threshold_patterns(self):
        rows = list(demo.demo_rows())
        series = collections.defaultdict(list)
        for row in rows:
            series[row["sensor"]].append(float(row["value"]))
        expected = [
            ("Zone Temperature", lambda v: v > 78, range(20, 30)),
            ("Outside Air Humidity", lambda v: v > 80, range(60, 70)),
            ("Chilled Water Temperature", lambda v: v > 64, range(90, 100)),
            ("Zone Temperature", lambda v: v < 65, range(100, 110)),
        ]
        for sensor, breached, indexes in expected:
            with self.subTest(sensor=sensor):
                self.assertEqual([i for i, value in enumerate(series[sensor]) if breached(value)], list(indexes))


if __name__ == "__main__":
    unittest.main()
