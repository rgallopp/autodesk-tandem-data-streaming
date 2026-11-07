"""Reproduce the tutorial's original synthetic measurements, never real sensor data.

This is a static example CSV generator, not a live equipment simulator. See
data/README.md for units, seed, timestamps, excursions, and licensing.
"""

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random

from measurements import FIELDS

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261107
BATCHES = 120
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SOURCE_MINUTES = 15
COLUMNS = ["timestamp", "equipment_id", "sensor", "value"]


def demo_rows():
    """Yield 120 complete groups with bounded variation and deliberate excursions."""
    rng = random.Random(SEED)
    for index in range(BATCHES):
        # Positions follow FIELDS insertion order for this worked example. Adapting
        # its sensors also requires updating these baselines and excursion indexes.
        # Temperatures are Fahrenheit; humidity values are percent RH (0..100).
        values = [54 + rng.uniform(-0.6, 0.6), 58 + rng.uniform(-0.8, 0.8),
                  48 + rng.uniform(-2, 2), 60 + rng.uniform(-0.6, 0.6),
                  45 + rng.uniform(-1, 1), 72 + rng.uniform(-0.3, 0.3)]
        # Human-readable batch numbers are index + 1. Each excursion is 10 batches.
        if 20 <= index < 30:
            values[5] += 8       # Zone temperature approximately 80 F.
        if 60 <= index < 70:
            values[2] += 37      # Outside humidity approximately 85% RH.
        if 90 <= index < 100:
            values[0] += 11      # Chilled water temperature approximately 65 F.
        if 100 <= index < 110:
            values[5] -= 8       # Zone temperature approximately 64 F.
        stamp = (START + timedelta(minutes=index * SOURCE_MINUTES)).isoformat().replace("+00:00", "Z")
        number = 0
        for equipment, sensors in FIELDS.items():
            for sensor in sensors:
                yield dict(zip(COLUMNS, [stamp, equipment, sensor, f"{values[number]:.2f}"]))
                number += 1


def generate(path):
    """Create a new CSV; never overwrite a local dataset."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(demo_rows())
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/demo_hvac.csv")
    args = parser.parse_args()
    try:
        generate(args.output)
    except OSError:
        parser.exit(1, "Cannot create CSV. Choose a new writable --output path; existing files are preserved.\n")
    print(f"Created {BATCHES} complete synthetic batches / {BATCHES * 6} values; seed {SEED}.")


if __name__ == "__main__":
    main()
