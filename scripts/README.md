# Script guide

Start with the [root learning path](../README.md). Run commands from the project
root after setup. Windows examples use the environment's Python explicitly; use
`.venv/bin/python` on macOS/Linux. Supporting modules are imported by the entry
points; they are not additional programs learners must run.

## Learner entry points

| File | Inputs and configuration | Output and relationship |
|---|---|---|
| `setup_environment.py` | Installed system Python 3.11+, `requirements-lock.txt`; no credentials | Creates/checks `.venv`, installs pinned packages, preserves unusable environments. `Setup-Environment.cmd` invokes it on Windows. |
| `ingest-data-individual-stream-from-csv.py` | Default `data/demo_hvac.csv`, `--steps`, `--interval`; live mode uses private `config/config.json`, CLI URL environment overrides, or hidden prompts | Preview is offline. Explicit `--send` posts numeric payloads without source timestamps; console gives UTC status and attempt CSV defaults to `logs/hvac_send_log.csv`. Uses `measurements.py`. |
| `read_readings.py` | Private root `.env` (`APS_CLIENT_ID`, `APS_CLIENT_SECRET`; process variables override), private `config/readback.json`, UTC query bounds; optional `--region`/`--page-size` | `--discover` writes local discovery JSON. Export writes genuine API CSV plus `.csv.summary.json`, exclusively. Uses `tandem_api.py` and `measurements.py`; never reads source/send-log values. |
| `tandem-control-panel.py` | Default demo CSV; masked URLs loaded from private ingestion JSON, editable in memory. Export also uses APS `.env`, private readback JSON, editable UTC bounds, and selected output path | Optional Tkinter interface sharing sender and reader functions. Logs GUI messages in UTC, saves a GUI session log on request, exports history in a worker, and offers explicit OS opening. `Open-Tandem-Controls.cmd` launches it on Windows. Opening/previewing sends nothing. |

### Setup and offline preview

```powershell
py -3 -B scripts/setup_environment.py
.\.venv\Scripts\python.exe -B scripts/ingest-data-individual-stream-from-csv.py --steps 1
```

Expected: environment ready, then two three-field JSON payloads and no data sent.
Follow [private configuration and mapping](../README.md#2-prepare-private-configuration)
before using the root README's **captured** live-send commands. Do not run extra
sends merely to follow both guides.

### Read-only discovery and historical export

After APS/facility authorization and saving the six mappings:

```powershell
.\.venv\Scripts\python.exe -B scripts/read_readings.py --discover --output outputs/discovery-check.json
```

Use a new output filename if it exists. Fill the discovered keys and IDs in the
private readback JSON; preserve the payload field names. For historical CSV export,
use the recorded-bound commands in [README stage 6](../README.md#6-discover-ids-and-export-genuine-history).
The full [readback guide](../docs/READBACK.md) explains authentication, discovery,
units, half-open bounds, UTC-day paging, empty-series exit 3, and output failures.
These are authorized API requests, not offline checks or measurement sends.

### Optional panel

Run setup once, then double-click `Open-Tandem-Controls.cmd` in Windows File Explorer
or run `./Open-Tandem-Controls.cmd` from the project PowerShell terminal. The `.cmd`
launcher and actual Python interface are complementary files. For other platforms
with Tkinter, run `.venv/bin/python -B scripts/tandem-control-panel.py`.

See [desktop controls](../README.md#optional-desktop-controls) for sending, session
log saving, explicit read-only export, connection checks, range padding, and opening
results. GUI session logs are not captured terminal stdout. Both workflows preserve
original client bounds separately from a padded historical query. APS credentials
are distinct from secret ingestion URLs; no credential code edits are needed.

## Supporting modules — imported, not executed

| File | Purpose and adaptation points |
|---|---|
| `measurements.py` | Defines equipment → exact CSV sensor label → flat JSON key. Shared by sender, discovery, reader, generator, and panel. For another dataset, follow [ADAPTING.md](../docs/ADAPTING.md); display-name customization alone requires no change here. |
| `tandem_api.py` | Loads APS credentials, handles OAuth/HTTP, normalizes keys, discovers schema/saved mappings, and pages genuine history. Configure private files instead of editing authentication. |
| `panel_support.py` | Small local GUI helpers: categorized sanitized UTC evidence, safe log saving, suggested padded bounds, URL/readback ID correspondence, and explicit OS file/folder opening. No network or duplicate reader implementation. |

## Optional data and maintainer utilities

| File | Run directly? | Inputs and outputs |
|---|---|---|
| `generate_demo_data.py` | Optional learner/maintainer tool | Fixed seed, documented units/UTC spacing, and deliberate excursions produce a new synthetic CSV. It refuses to overwrite. No live simulation or network use. |
| `build_distribution.py` | Maintainer tool | Explicit public-file list reads current working sources and builds `dist/autodesk-tandem-data-streaming.zip` with `MANIFEST.sha256`. Private files are excluded; the ZIP remains an optional review copy. |

```powershell
.\.venv\Scripts\python.exe -B scripts/generate_demo_data.py --output outputs/recreated-demo.csv
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B scripts/build_distribution.py
```

Choose a fresh generator output path. See [dataset notes](../data/README.md) for
reproduction and [verification](../docs/VERIFICATION.md) for actual evidence and
pending checks. The five files under `tests/` cover synthetic data, sender,
reader, panel/helpers, and setup/distribution; run them through unittest rather
than treating each as a tutorial stage. Mocked tests do not prove live behavior.

Original authorship and Autodesk workflow references are preserved in
[REFERENCES.md](../docs/REFERENCES.md) and the project [license](../LICENSE).
