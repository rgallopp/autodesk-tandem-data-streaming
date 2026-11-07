# autodesk-tandem-data-streaming

An independent community tutorial by [rgallopp](https://github.com/rgallopp):
configure a digital twin in Autodesk Tandem, replay CSV measurements with Python,
export actual stored history, inspect charts and thresholds, and build a native
dashboard. HVAC is the worked example; the skills apply to other equipment and
numeric measurements. This is not an Autodesk product.

Start with the Python workflow below. The optional desktop panel comes afterward.
The sender and reader are working examples; you configure your own facility and
verify what it stores. [Verification status](docs/VERIFICATION.md) separates offline
tests, completed live API checks, and pending UI/longer-run checks. HTTP success
alone does not prove historical storage or end-to-end tutorial readiness.

## What you bring and what is supplied

You need basic file editing and terminal skills; no prior Tandem API experience is
assumed. You should be comfortable opening a project folder, editing placeholder
values, running a command, and reading its output. Keep this terminal open through
the run and export steps so the example variables remain available.

| Supplied | Your work |
|---|---|
| Working sender, reader, offline tests, and setup scripts | Install the environment, preview payloads, run deliberately, and interpret results |
| Placeholder configuration templates | Fill private local files with your authorized credentials and discovered IDs |
| Reproducible synthetic HVAC CSV, units, and known excursions | Inspect the data, check mappings and units, and distinguish source time from server time |
| Tandem walkthrough and example threshold settings | Import your authorized models; create parameters, templates, assets, connections, charts, and a dashboard |
| Logs, export summaries, and verification procedures | Compare attempted sends with genuine history and explain differences |

Do not edit credential-handling code to configure this lesson. Display names are
customizable; payload keys and parameter IDs have different roles, explained below.
No building model is bundled. The [synthetic sample](data/README.md) is original
MIT-licensed demonstration data, with explicit UTC source dates and units. It does
not represent real equipment behavior.

## Repository map and script guide

The publishable source contains **37 files**. `[run]` marks learner entry points;
`[support]` marks imported modules, and `[maintainer]` marks the review-package tool.
See [scripts/README.md](scripts/README.md) for inputs, outputs, commands, and relationships.

```text
autodesk-tandem-data-streaming/
├── README.md                         Learning path, exercises, and repository map
├── LICENSE                           Original code/docs/demo-data MIT terms
├── .gitignore                        Private/local/generated file exclusions
├── .gitattributes                    Preserve reproducible CSV bytes on checkout
├── .env.example                      Placeholder APS credential keys
├── requirements.txt                  Direct dependency declaration
├── requirements-lock.txt             Pinned installation dependencies
├── Setup-Environment.cmd             Windows setup launcher [run]
├── Open-Tandem-Controls.cmd           Windows panel launcher [run]
├── config/
│   ├── config.example.json           Placeholder ingestion URLs by equipment
│   └── readback.example.json         Placeholder facility/connection/parameter IDs
├── data/
│   ├── demo_hvac.csv                 Reproducible 120-batch synthetic sample
│   └── README.md                     Units, source times, seed, patterns, rights
├── docs/
│   ├── TANDEM_SETUP.md               Models through charts/thresholds/dashboard
│   ├── READBACK.md                   APS, discovery, history, bounds, output
│   ├── ADAPTING.md                   Reuse with other names/data/equipment
│   ├── TROUBLESHOOTING.md            Symptoms and checkpoint-specific actions
│   ├── LIVE_VERIFICATION.md          Authorized live test procedure
│   ├── VERIFICATION.md               Dated evidence and remaining limitations
│   └── REFERENCES.md                 Authorship and third-party attribution
├── scripts/
│   ├── README.md                     Script roles and command guide
│   ├── setup_environment.py          Environment installation/check [run]
│   ├── ingest-data-individual-stream-from-csv.py  Preview/send CSV [run]
│   ├── read_readings.py              Discovery and genuine CSV export [run]
│   ├── tandem-control-panel.py       Optional desktop interface [run]
│   ├── generate_demo_data.py         Optional offline sample reproduction [run]
│   ├── measurements.py               Exact sensor/JSON routing table [support]
│   ├── tandem_api.py                 Authentication/discovery/history [support]
│   ├── panel_support.py              Local GUI evidence/target/file helpers [support]
│   └── build_distribution.py         Explicit source ZIP builder [maintainer]
├── tests/
│   ├── test_demo_data.py             Sample reproduction and known patterns
│   ├── test_sender.py                CSV validation, payloads, pacing, failures
│   ├── test_readback.py              Synthetic auth/discovery/history/export
│   ├── test_panel.py                 Sessions, logs, exports, controls, opening
│   └── test_setup_and_distribution.py  Environment, launcher, ZIP exclusions
├── logs/.gitkeep                     Preserve the otherwise empty log directory
└── outputs/.gitkeep                  Preserve the otherwise empty output directory
```

Private/generated items coexist locally but are **outside the publishable tree**:
root `.env`, `config/config.json`, `config/readback.json`, `.venv/`, `.vscode/`,
Python caches, log/export contents under `logs/` and `outputs/`, and `dist/` review
archives. Git ignores them; only the two `.gitkeep` placeholders are public in
the output directories. The ZIP builder selects the source files explicitly and
adds `MANIFEST.sha256`. Older copies/data/archives already moved outside this folder
remain in the external backup; they are not alternate starter/solution trees.

## 1. Prerequisites and Python setup

**Purpose:** establish the tools and access needed for the whole workflow before
sending anything.

- Install Python 3.11 or later with pip, and use an editor and internet connection.
  Windows examples use PowerShell. Tkinter is only needed for the optional panel.
- Obtain Tandem access with permission to import a model and configure parameters,
  classifications, templates, assets, connections, mappings, and native visualizations.
- Bring an authorized model with identifiable AHU and VAV instances and usable
  rooms/spaces. See [model requirements](docs/TANDEM_SETUP.md#1-create-a-facility-and-import-models).
- For readback, obtain an APS application's Client ID and Client Secret and confirm
  the account permits the Tandem Data API. Once the facility exists, its administrator
  must add that **Client ID as a service/API key with Read permission**. An APS app
  or UI access alone does not grant facility API access. See [APS prerequisites](docs/READBACK.md#1-create-and-authorize-an-aps-application).

Download and extract the ZIP from
[GitHub](https://github.com/rgallopp/autodesk-tandem-data-streaming), or clone:

```powershell
git clone https://github.com/rgallopp/autodesk-tandem-data-streaming.git
cd autodesk-tandem-data-streaming
```

Open the root containing this README. On Windows, double-click
`Setup-Environment.cmd`, or run these commands from the project terminal:

```powershell
py -3 -B scripts/setup_environment.py
.\.venv\Scripts\python.exe -m pip check
```

If `py` is unavailable, use your installed `python` for setup. On macOS/Linux:

```sh
python3 -B scripts/setup_environment.py
.venv/bin/python -m pip check
```

Setup creates `.venv`, installs `requirements-lock.txt`, and checks packages.
It preserves an unusable environment as `.venv.unusable-<UTC time>` before replacing
it; close tools using that environment first. Recreate environments after downloading
or moving the project because their paths are machine-specific.

**Check:** setup reports ready and `pip check` reports no broken requirements.
Select `.venv/Scripts/python.exe` in your editor (or `.venv/bin/python` on macOS/Linux).
Activation is optional. Substitute that POSIX interpreter path in later commands.
The capture blocks use PowerShell syntax; on macOS/Linux, use PowerShell with those
POSIX paths or capture equivalent console text and UTC bounds in your shell. Windows
is the verified platform; macOS/Linux execution remains unverified.
If setup fails, use [setup troubleshooting](docs/TROUBLESHOOTING.md) before continuing.

## 2. Prepare private configuration

**Purpose:** separate your local access details from reusable public examples.
Create each private file only if it is absent:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
if (-not (Test-Path -LiteralPath config/config.json)) {
    Copy-Item -LiteralPath config/config.example.json -Destination config/config.json
}
if (-not (Test-Path -LiteralPath config/readback.json)) {
    Copy-Item -LiteralPath config/readback.example.json -Destination config/readback.json
}
```

On other platforms, copy the same examples only when the private destination does
not exist. Edit the private files, leaving public examples as placeholders:

| Private local file | Fill now or when available |
|---|---|
| Root `.env` | `APS_CLIENT_ID` and `APS_CLIENT_SECRET` from your APS app |
| `config/config.json` | One distinct Individual ingestion URL under each equipment ID, after creating connections in stage 4 |
| `config/readback.json` | `facility_urn` after facility creation; each `connection_key` and the six `parameters` IDs after discovery in stage 6 |

**Check:** the three private files exist with the template's keys intact. Unknown
facility/connection/parameter values stay placeholders until the relevant step;
do not guess IDs or run an export with placeholders.

Ingestion URLs contain secrets. Do not put them in code, images, or shared archives.
The CLI can instead prompt without echoing input; `TANDEM_AHU_URL` and `TANDEM_VAV_URL`
override its file values. The sender does not read `.env`. The reader loads the two
APS keys from root `.env`; existing process variables take precedence, even when
empty. No extra dotenv dependency is needed. See [credential formats and precedence](docs/READBACK.md#1-create-and-authorize-an-aps-application)
if the wrong configuration appears to be used.

Private `.env`, JSON, logs, and exports are ignored by Git and excluded by the supplied
ZIP builder. Only placeholder examples are publishable. Manual archives need their
own inspection.

## 3. Inspect the CSV and preview a payload

**Purpose:** predict what will be sent before configuring its destination.
Open [the dataset notes](data/README.md), the CSV, and the small mapping table in
`scripts/measurements.py`. Then run this offline preview:

```powershell
.\.venv\Scripts\python.exe -B scripts/ingest-data-individual-stream-from-csv.py --steps 1
```

**Check:** `120 complete batches`, `0 incomplete timestamps`, two JSON objects with
three numeric fields each, and `Preview only: no data sent.` The exact first payloads
are shown in [the mapping guide](docs/TANDEM_SETUP.md#7-establish-json-mappings-and-collection).
Preview does not resolve credentials, send requests, wait, or create a send log.

Trace one CSV sensor label to its JSON field. Temperatures are Fahrenheit and
humidity is percent RH, 0–100. The source readings are 15 minutes apart; their
timestamps group rows into batches and remain in local logs. **No timestamp goes
in the outgoing JSON.** Tandem assigns ingestion timestamps during a live replay.
Incomplete groups are skipped; invalid/duplicate rows fail validation rather than
inventing values. Resolve any [CSV error](docs/TROUBLESHOOTING.md) before sending.

## 4. Set up Tandem and plan the mappings

**Purpose:** give every payload field the correct equipment, numeric parameter,
unit, and historical destination.

Follow [Tandem setup sections 1–7](docs/TANDEM_SETUP.md) in order: new facility/model
import → six numeric parameters and units → classification/template assignment →
AHU and VAV assets → two connections with verified hosts and rooms → three JSON
mappings per connection. The guide describes how to select actual library classes,
including OmniClass, without guessing classification codes.

Choose your parameter display names. Keep the exact CSV sensor labels and JSON keys
unchanged for this sample. A display-name customization does not change the payload:
discovery matches IDs and saved source fields, and readback exports current names.
Deleting/recreating a parameter can change its ID and requires rediscovery.

Fill the private ingestion URLs and facility URN from your new facility. Have its
administrator grant the APS app the Read service access described in stage 1.
You can check authentication/facility discovery before sending:

```powershell
$preflightId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')
.\.venv\Scripts\python.exe -B scripts/read_readings.py --discover --output "outputs/preflight-$preflightId.json"
```

This makes authorized read-only API requests. Connections without saved mappings may
not list parameters yet. If Configure Connections needs an incoming sample, use the
captured one-batch run in stage 5, then finish saving the mappings. Do not send an
uncaptured extra run just to follow both documents.

**Check:** correct model instances, six numeric specifications/units, an applied
template, two distinct host/room relationships, and a field-to-parameter mapping plan.
After an incoming sample is available, save and reopen all six actual mappings and
check incoming units and collection frequency. A missing parameter usually calls
for checking the connection class/template; HTTP 403 on discovery calls for checking
service access/API entitlement. See [troubleshooting](docs/TROUBLESHOOTING.md).

## 5. Stream a controlled batch and capture console results

**Purpose:** test the mapping with six known values and preserve what the sender
actually reported. Commands with `--send` are **live writes**; use only a facility
you are authorized to modify. Run one sender at a time and wait at least 60 seconds
since any previous attempt on each connection.

Use the inspected first batch for this initial check. The following block creates
uniquely named console, bounds, and attempt files; run it again only deliberately:

```powershell
New-Item -ItemType Directory -Force outputs | Out-Null
$runId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')
$boundsPath = "outputs/run-$runId-bounds.json"
$runStart = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
.\.venv\Scripts\python.exe -u -B scripts/ingest-data-individual-stream-from-csv.py --send --steps 1 --interval 60 --log "logs/run-$runId.csv" 2>&1 | Tee-Object -FilePath "outputs/run-$runId-console.txt"
$sendExit = $LASTEXITCODE
$runEnd = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
@{ from_utc = $runStart; to_utc = $runEnd; sender_exit = $sendExit } | ConvertTo-Json | Set-Content $boundsPath
```

**Check:** exit 0, a complete console outcome, two accepted requests (AHU and VAV),
and six attempt-log rows. These establish HTTP acceptance, not historical storage.
The console includes run settings, UTC request results, completion status, and
accepted-value counts. An attempt-log CSV does not replace console capture.

If this sample established the mappings, finish [saving them](docs/TANDEM_SETUP.md#7-establish-json-mappings-and-collection).
After at least 60 seconds, deliberately repeat the captured block for a fresh test
only if needed. A failure stops the sender; it never retries automatically. One
connection can succeed while the other fails. After a timeout, inspect history and
logs before deciding whether another attempt is appropriate; delivery is uncertain.

After verifying the controlled batch through stages 6–7, you can repeat this block
with `--steps 6` for a short history plot, using its fresh run filenames. Each CLI
invocation restarts at source batch 1. Longer runs use the same capture procedure.

| Batches | Requests | Measurement values | Supplied values per series | Time at 60 seconds |
|---:|---:|---:|---:|---|
| 1 | 2 | 6 | 1 | Request time |
| 6 | 12 | 36 | 6 | About 5 minutes + requests |
| 17 | 34 | 102 | 17 | About 16 minutes + requests |
| 50 | 100 | 300 | 50 | About 49 minutes + requests |
| 100 | 200 | 600 | 100 | About 99 minutes + requests |
| 120 | 240 | 720 | 120 | About 119 minutes + requests |

These assume every request succeeds. The first batch sends immediately; waits occur
between batches. The enforced minimum is 60 seconds, independent of 15-minute source
spacing. Retained points depend on saved mappings, actual collection frequency,
processing delay, retention, and query bounds. Do not equate the table with chart counts.

## 6. Discover IDs and export genuine history

**Purpose:** verify what Tandem retained, using an independent API read rather than
copying attempted values from a log or the source CSV.

After saving mappings, run [discovery](docs/READBACK.md#2-discover-facility-connection-and-parameter-ids)
to a fresh private file:

```powershell
$discoveryId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')
.\.venv\Scripts\python.exe -B scripts/read_readings.py --discover --output "outputs/discovery-$discoveryId.json"
```

Match each connection to its intended name and host in Tandem, then use its saved
source fields to identify the three parameter IDs. Names alone are insufficient.
Fill both `connection_key` values and all six `parameters` IDs in private
`config/readback.json`. The reader validates those IDs against the saved source
fields; it does not guess by display name.

Allow collection and processing time, then query the recorded run bounds:

```powershell
$bounds = Get-Content -LiteralPath $boundsPath | ConvertFrom-Json
$exportId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')
.\.venv\Scripts\python.exe -B scripts/read_readings.py --from-utc $bounds.from_utc --to-utc $bounds.to_utc --output "outputs/readback-$exportId.csv"
$readExit = $LASTEXITCODE
```

If using a new terminal, first set `$boundsPath` to the actual saved run-bounds file.
**Check:** both the CSV and adjacent `.summary.json` exist, the export completed,
and each of the six series has genuine rows. Inspect names, IDs, units, millisecond
UTC timestamps, and values against the preview and attempt log. Neither script
converts units; Tandem's saved source/destination unit settings may do so.

Exit 3 means some series are empty: preserve that result. Investigate mappings,
processing delay, and UTC bounds before declaring a failure or resending. Server
timestamps can fall just outside client run bounds. Follow the [padded-window procedure](docs/READBACK.md#3-query-timezone-aware-bounds)
when needed, exporting to a fresh filename and distinguishing other runs' points.
Never replace server timestamps or fill missing values from the source. Existing
exports are preserved; see [output and paging troubleshooting](docs/TROUBLESHOOTING.md).

## 7. Make charts readable and reconcile results

**Purpose:** turn verified measurements into interpretable history.
Follow [the chart walkthrough](docs/TANDEM_SETUP.md#8-read-charts-and-reconcile-history).
Choose the actual ingestion interval, account for the UI timezone, inspect hover
values, and separate Fahrenheit and humidity views/axes with visible units and legends.

**Check:** both connections and all six series are represented. Compare chart values,
units, and timestamps with your API CSV. One batch can verify a point; use a deliberately
captured multi-batch run for a trend. Explain any aggregation/count differences.
If a series is absent, check the selected connection/time range and saved mappings
before changing axes. Latest-value cards and Usage capacity do not prove history counts.

## 8. Explore thresholds and a native dashboard

**Purpose:** interpret sustained changes and build a reusable native visualization.
Complete the [threshold and dashboard walkthrough](docs/TANDEM_SETUP.md#9-configure-demonstration-thresholds).
The dataset contains four sustained excursions with known batch ranges and example
thresholds. A short run stays in normal variation; a deliberately captured 40-batch
run reaches the first excursion and its return to normal. The full 120-batch sample
reaches all four. Check duration and count calculations before choosing a longer run.

**Check:** saved thresholds use the right units, an observed event agrees with API
history, and a saved/reopened native dashboard shows all six series with readable
temperature and humidity charts. Distinguish source duration from replay duration.
Thresholds here are teaching settings, not operating limits. If historical stream
cards are unavailable, record the feature/access limitation rather than claiming
completion. These steps remain part of the public tutorial; they need no custom
monitoring application, rules engine, simulation, or status writeback.

## Optional desktop controls

After running setup once, double-click **`Open-Tandem-Controls.cmd` in Windows File
Explorer**, or execute it from the project terminal:

```powershell
.\Open-Tandem-Controls.cmd
```

The `.cmd` file is the Windows launcher: it checks the environment and starts
`scripts/tandem-control-panel.py`, the actual Tkinter interface. They are complementary
files, not alternative versions. **Opening the interface sends no data.** Preview
also sends nothing; the two send buttons initiate live requests. On macOS/Linux with
Tkinter available, use `.venv/bin/python -B scripts/tandem-control-panel.py` directly.

The panel reuses the Python sender's validation, field mappings, HTTP routine, and
attempt-log format. It always loads `data/demo_hvac.csv`. On opening, it loads URLs
from private `config/config.json` into masked fields; it does not load CLI URL
environment variables or APS `.env` credentials. URL edits and run settings stay in
memory and are not saved back to configuration.

Preview shows the next pending payloads. Stop/Start retains progress, including a
partially completed batch, and per-connection cooldowns while the window remains
open. Closing resets them; wait at least 60 seconds after previous attempts before
starting a new session. Stop cancels waits; an active HTTP request finishes and is
logged first. Following a failure, check uncertain delivery before choosing to resume.
Do not run the CLI and panel concurrently.

Requests append to `logs/hvac_send_log.csv`. Messages now use UTC and distinguish
`PREVIEW`, `SEND`, and `READBACK`. After a run or export finishes, choose **Save session
log** and a text-file destination. This saves actual GUI messages, including original
UTC run bounds, selected interval, requested/completed batches, request outcomes,
and final status. It is a **GUI session log**, not captured terminal stdout. Saving
over an existing text file requires explicit confirmation; saving is disabled while
a worker is active. Credentials, ingestion URLs, and raw sensitive errors are excluded.

For **Export readings**, finish [APS/readback setup](docs/READBACK.md), including the
facility service's Read permission and both connections' discovered parameter IDs.
Ingestion URL credentials and APS `.env` credentials serve different purposes.
The panel checks the model/connection IDs in its current masked URLs against private
`config/readback.json` before retrieval, so temporary URL overrides cannot silently
export a different facility or connection. Missing/mismatched configuration points
back to setup/discovery; it does not launch a setup wizard. Export uses the existing
reader's authentication, mapping validation, paging, and CSV/summary writer.

Enter **From UTC (inclusive)** and **To UTC (exclusive)** for known stored history;
no new send is required. After a send, original client bounds remain visible, while
the editable query fields suggest **60 seconds of padding on each side**. Use last
run ±60s restores that suggestion. Adjust for actual collection/timing differences;
a padded window may include earlier or later runs and does not change the original
bounds. Allow processing time; missing points are not a reason for an automatic resend.

Choose **Export readings**, then a new CSV filename in the native Save As dialog.
It starts in ignored `outputs/` with a timestamped suggestion; another directory is
allowed. Either an existing CSV or companion `.csv.summary.json` blocks replacement.
Retrieval runs in the background, independently of sending. Export is disabled during
streaming, and sending is disabled during export. Stop applies to sends; closing
during an export waits for it to finish or fail. No file opens automatically.

After completion, inspect the displayed saved path and all six genuine per-series
counts. Empty/partial exports are labeled explicitly and should be investigated using
[the readback guide](docs/READBACK.md#3-query-timezone-aware-bounds). **Open CSV** uses
the operating system's default CSV application; **Open folder** shows its directory.
Neither needs Excel. Opening failures leave the saved export intact. A new export
attempt clears the old result buttons; a failed attempt never presents an earlier
file as its result. Save the GUI session log again after exporting to include counts.

The primary CLI capture and independent reader remain supported. Use CLI `--csv`
for a different input, or CLI `--region` if your facility needs regional routing.
The panel provides no chart or dashboard controls; those remain native Tandem steps.
New GUI features have offline evidence only until explicitly verified live.
If it will not open, check [environment/Tkinter troubleshooting](docs/TROUBLESHOOTING.md);
the CLI remains sufficient for the complete tutorial.

## Check your understanding / Try an adaptation

- Inspect a one-batch preview. Trace all six values from CSV sensor labels through
  `FIELDS` and JSON keys to the saved parameter IDs. Why can a display name change
  without changing the JSON?
- Explain why a 15-minute source interval becomes a different timeline during
  replay. Identify source, client request, and returned server timestamps in your
  artifacts, and explain why no source date belongs in the outgoing payload here.
- For your captured run, calculate requests, values, and values per series. Reconcile
  them with the API summary and chart; explain a discrepancy using evidence rather
  than assuming every accepted value must be retained as a distinct point.
- Interpret a demonstrated threshold event: name its series, unit, bound, crossing
  values, return to normal, and duration on the returned timeline. Compare it with
  the documented source duration. What does a shorter run fail to demonstrate?
- First try a harmless display-name customization and rediscover/export to a new
  file, verifying that its ID and source field still match. Then, if desired, use
  [the adaptation guide](docs/ADAPTING.md) to preview another authorized CSV with
  `--csv`. Propose its units and mapping before making any live changes. Keep
  credential-handling code intact.

## Tests, review copy, and attribution

- [Troubleshooting](docs/TROUBLESHOOTING.md) covers the checkpoints above.
- [Controlled live verification](docs/LIVE_VERIFICATION.md) identifies checks still
  needing authorized Tandem access.
- [References and attribution](docs/REFERENCES.md) identify Autodesk workflow examples
  and this tutorial's independently implemented adaptations.
- [Dataset reproduction](data/README.md#reproduce-the-file) runs without Tandem.

Run offline tests, or build the optional review ZIP from the current working source:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B scripts/build_distribution.py
```

Offline tests use synthetic inputs and mocked HTTP responses; they do not establish
live compatibility. The ZIP uses an explicit public-file list and `MANIFEST.sha256`;
it excludes private configurations, environments, generated logs/outputs, retained
old data, and obsolete copies. The working folder remains the authoritative source.

Original project code, documentation, and `data/demo_hvac.csv` are MIT licensed.
Building models, Autodesk products, upstream implementations, and dependencies have
separate terms. No external model or upstream implementation package is bundled.
