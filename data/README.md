# Reproducible synthetic HVAC demonstration data

`demo_hvac.csv` is an original, fixed-seed teaching dataset created for this tutorial.
It contains no real sensor measurements, building operations, personal data, or
claimed connection to a particular model. It is covered by the root [MIT license](../LICENSE).
The deterministic generator is [generate_demo_data.py](../scripts/generate_demo_data.py);
seed **20261107**. Its formulas deliberately create teaching patterns rather than a
physical equipment model.

## Format, units, and source timestamps

Columns: `timestamp,equipment_id,sensor,value`. Equipment IDs, exact sensor labels,
and JSON mapping keys are defined in [measurements.py](../scripts/measurements.py).

| Equipment | Exact CSV sensor | JSON field | Source unit |
|---|---|---|---|
| ahu-01 | Chilled Water Temperature | chilled_water_temperature | Fahrenheit |
| ahu-01 | Heat Pipe Leaving Tempera | heat_pipe_leaving_temperature | Fahrenheit |
| ahu-01 | Outside Air Humidity | outside_air_humidity | percent RH, 0-100 |
| vav-3 | Discharge Air Temperature | discharge_air_temperature | Fahrenheit |
| vav-3 | Zone Humidity | zone_humidity | percent RH, 0-100 |
| vav-3 | Zone Temperature | zone_temperature | Fahrenheit |

The truncated heat-pipe sensor label is preserved for mapping compatibility.
Parameter display names may use the full readable name.

There are **720 rows, 120 complete batches, six series of 120 readings**.
No incomplete groups, duplicates, blank cells, or nonfinite values are present.
Every batch contains all six measurements. Missing-group behavior is tested using
separate test fixtures; no gaps are hidden in the default sample.

Source timestamps are UTC, **2026-01-01T00:00:00Z through 2026-01-02T05:45:00Z**,
exactly 15 minutes apart. The first-to-last span is 29 hours 45 minutes.
Dates are illustrative, not a claim about real observations.

The sender groups by source time but does **not** post timestamps. Tandem assigns
current server time. Source time, client request time, and retained history time are
different. No Python-side unit conversion occurs. Configure matching source units
and verify any Tandem conversion before comparing history.

## Variation and sustained excursions

Baseline values vary within bounded seeded ranges. The deliberate events below
each contain ten consecutive source readings, followed by return to the baseline:

| Series | One-based batches | Approximate event value | Example threshold breached |
|---|---|---|---|
| Zone Temperature | 21-30 | 80 F | Upper alert 78 F |
| Outside Air Humidity | 61-70 | 85 percent RH | Upper alert 80 percent RH |
| Chilled Water Temperature | 91-100 | 65 F | Upper alert 64 F |
| Zone Temperature | 101-110 | 64 F | Lower alert 65 F |

A ten-sample event spans **135 source minutes from first to last sample**, and
returns to baseline on the next 15-minute source boundary: a 150-minute event
window. With 60-second replay spacing, first-to-last event requests span about
**9 minutes plus request overhead**; the normal next batch follows about one minute
later. These are planned replay intervals, not promises about stored buckets.

The first upper-temperature event begins about 20 replay minutes after batch 1.
A 40-batch run includes normal data before and after it and takes about 39 minutes
plus requests. Use 120 batches for all four events (about 119 minutes plus requests).
A six-batch preview/run shows normal values only.

Full example bounds and native UI instructions are in
[the walkthrough](../docs/TANDEM_SETUP.md#9-configure-demonstration-thresholds).
These thresholds and durations demonstrate visualization; they are not HVAC
performance criteria, safety limits, or alert-response rules.

## Reproduce the file

After environment setup, create a new file without overwriting the bundled sample:

```powershell
.\.venv\Scripts\python.exe -B scripts/generate_demo_data.py --output outputs/recreated-demo.csv
(Get-FileHash data/demo_hvac.csv).Hash -eq (Get-FileHash outputs/recreated-demo.csv).Hash
```

Expected: 120 complete batches / 720 values, seed 20261107, and `True` for the hash
comparison. An existing output is preserved and produces an error; choose a fresh
path. The generator writes UTF-8 with LF newlines for reproducibility.

The superseded `payloads_dataset.csv` is preserved in an external local backup,
outside this working data directory and the public file list. Its former path remains
ignored by Git. No redistribution permission or unit/timezone metadata is inferred
for that earlier file.
