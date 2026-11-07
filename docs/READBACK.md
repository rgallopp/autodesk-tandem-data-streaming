# APS authentication, ID discovery, and API export

`scripts/read_readings.py` is a complete reader. It never reads the source measurement
CSV or send log. Exported rows originate only from authenticated Tandem history
responses. An attempted send is not substituted for a stored measurement.

## 1. Create and authorize an APS application

1. Sign in to the [APS developer portal](https://aps.autodesk.com/myapps/) and create
   an application with access to the Tandem Data API. This script uses server-to-server
   client credentials (two-legged OAuth), not a browser callback flow.
2. Obtain its Client ID and Client Secret. An authorized Tandem administrator must
   add the application to the facility: open the facility's Users panel, choose the
   Service/API key workflow, enter the application's **Client ID**, and assign
   **Read permission** for this read-only reader. Creating an APS application alone
   does not grant facility access: the Client ID must also be added to the intended
   facility. Adding an app at account level grants
   broader facility access and is unnecessary for this single-facility lesson.
3. Confirm the account/facility entitlement permits the Tandem Data API. Creating an
   APS app and receiving a token do not by themselves grant access to this facility.
4. Create private local files once, without overwriting any existing credentials:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
if (-not (Test-Path -LiteralPath config/readback.json)) {
    Copy-Item -LiteralPath config/readback.example.json -Destination config/readback.json
}
```

Open the root `.env` in your editor and fill these exact keys:

```dotenv
APS_CLIENT_ID=YOUR_APS_CLIENT_ID
APS_CLIENT_SECRET=YOUR_APS_CLIENT_SECRET
```

The Client ID is the APS application's client key, not a connection key.
The reader loads only these two credential variables from the project-root file,
independent of the terminal's working directory. It does not change the process
environment. Existing process variables, including empty values, take precedence;
remove stale terminal variables if you want to use the file values.

This small standard-library loader accepts UTF-8 `KEY=VALUE` lines, blank lines,
whole-line `#` comments, and optional matching single/double quotes. Values are
literal: no shell execution, variable interpolation, multiline values, or inline
comment removal. Use one assignment per credential key. No `python-dotenv`
dependency is needed; setup and dependency pins are unchanged.

Open private `config/readback.json` and fill `facility_urn` first. Connection keys
and parameter IDs belong in that JSON file, not in `.env`. They can remain blank
until discovery. Keep the existing `connections` object and all six field names.

The root `.env` and private JSON files are excluded from Git and review archives.
Only `.env.example` and `config/*.example.json` are public. Never put actual
credentials into those examples. The ingestion configuration
`config/config.json` remains separate and is not changed by the reader.

Alternatively, supply credentials through process variables. For PowerShell 7:

```powershell
$env:APS_CLIENT_ID = Read-Host 'APS Client ID'
$env:APS_CLIENT_SECRET = Read-Host 'APS Client Secret' -MaskInput
```

Windows PowerShell 5.1 does not support `-MaskInput`. Use:

```powershell
$env:APS_CLIENT_ID = Read-Host 'APS Client ID'
$secret = Read-Host 'APS Client Secret' -AsSecureString
$env:APS_CLIENT_SECRET = [System.Net.NetworkCredential]::new('', $secret).Password
Remove-Variable secret
```

Masked entry avoids terminal echo, not plaintext storage in the process environment.
On macOS/Linux, the root `.env` works the same way, or export the exact same keys
through your local secret-entry workflow. Do not print credentials or environment dumps.

The reader requests `POST https://developer.api.autodesk.com/authentication/v2/token`
with `grant_type=client_credentials` and scope `data:read`. It refreshes expiring tokens
during long queries. Individual ingestion URLs use a separate credential and are
not the APS credentials used by this reader. The reader sends no measurement POSTs.

## 2. Discover facility, connection, and parameter IDs

Find the facility URN in the facility URL/settings; use the form `urn:adsk.dtt:...`,
not a Revit model URN or equipment tag. If the URL does not expose a usable URN,
ask your administrator for it. The default logical model has the same suffix with
`urn:adsk.dtm:`; discovery checks that model against the facility's links.

```powershell
.\.venv\Scripts\python.exe -B scripts/read_readings.py --discover --output outputs/discovery.json
```

With `facility_urn` filled in private JSON, `--discover` reads that field without
requiring connection or parameter IDs. An explicit `--facility-urn` overrides the
JSON value for discovery. These discovery/export commands make authenticated
requests; run them only when authorized.

Discovery authenticates and reads facility metadata, default-model schema, connection
elements, and stream configurations. It prints connection names, full connection
keys, mapped qualified parameter IDs, parameter names, metadata units, and recognized
source fields. It writes the same information plus schema attributes to the ignored
local JSON file. Only known payload field names are exposed from mappings; unknown
paths are reported as unrecognized, never echoed. Raw integration settings are not exported.

Find the two connections you created. Match their names/keys to the actual connections
in Tandem, not the host's Revit element ID. Both short and full logical connection
keys are accepted by the reader and normalized to full keys. Parameters use qualified
IDs such as `z:Dg`; IDs are facility-specific and must not be guessed from display
names. The same parameter name can occur more than once. Match each to the saved
mapping on the intended connection. If parameters are absent, fix/save the mappings
in Tandem and rerun discovery using a new output filename.

Edit the private JSON created in step 1; do not overwrite it with the example again.

Replace the facility URN, both connection keys, and all six parameter IDs using the
discovery results. Preserve the equipment IDs and JSON-field keys. For example,
`chilled_water_temperature` must point to that connection's actual chilled-water
parameter ID, not an arbitrary temperature parameter. Both connections and every
field in `scripts/measurements.py` are required. Before history requests begin, the
reader checks that each parameter ID is on the configured connection and has the
matching saved source field. Swapping two valid IDs is rejected. Recognized flat
paths are `field`, `$.field`, `$['field']`, and `$["field"]`; other path forms stop
export and require inspection of the actual saved mapping.

Display names may be customized: the reader does not search for hardcoded names.
It matches stable IDs and exports the schema's current name. A rename that preserves
the ID does not require changing payload keys. Deleting/recreating a parameter can
change its ID; rerun discovery and update the configuration in that case.

If your facility requires regional routing, supply `--region` with its documented
Region header value to both discovery and export. Do not guess a region to work
around an authentication or access error.

## 3. Query timezone-aware bounds

Record the live run's UTC bounds using the README commands. For a manual query,
substitute your actual recorded times, using an offset or `Z`:

```powershell
.\.venv\Scripts\python.exe -B scripts/read_readings.py --from-utc '2026-11-05T19:00:00.000Z' --to-utc '2026-11-05T19:10:00.000Z' --output outputs/readback-run.csv
```

Those dates illustrate syntax; they are not a promise of available data. The reader
accepts timezone-aware ISO 8601 bounds with at most millisecond precision, converts
them to integer epoch milliseconds, and exports the half-open interval `[from, to)`:
the lower bound is included, the upper bound excluded. Offset-bearing bounds are
converted to UTC. A timezone-free local time is rejected.

Stored history can be aligned to collection buckets, and data may arrive after a
processing delay. Server/client clock differences can also place a returned server
timestamp just outside locally recorded request bounds. A controlled one-batch test
found all three values from one connection only after padding the client end; this
did not require resending or changing stored timestamps. First query the recorded
run bounds. If a boundary point is missing,
wait for collection and query a separately named export spanning one collection
interval before/after the run. Label that expanded window and check for older or
later test points instead of claiming all returned rows belong to this run. Never
replace returned timestamps with client send times.

## 4. Response limits and returned rows

For each configured connection/parameter pair, the reader uses the official
`GET timeseries/models/{modelID}/streams/{connectionKey}` endpoint, with `substream`,
`from`, `to`, `sort=asc`, and an explicit `limit`. It requests only that series.

`--page-size` defaults to 1000 and accepts 2–1000. The requested interval is split
at UTC midnight boundaries, with paging inside each day. Live testing found that a
small-page query could return empty before later days containing known history;
an empty response must not end the entire multi-day export. Also, a one-millisecond
look-behind into an exhausted preceding day could hide the new day's records.
If that first query is empty, the reader retries the exact window start before
moving to the next day. These are observed behaviors, not assumptions about the
server's internal storage implementation.

Queries overlap the last returned timestamp and deduplicate it. A short or
overlap-only page is followed; when the response includes the queried lower bound,
the next cursor advances one millisecond past its last point. Only an empty page
or reaching the window's upper bound ends that day's paging. Later days are still
queried. Boundary overlap is filtered locally to the requested half-open interval.
Unexpected response shapes, out-of-range timestamps, conflicting overlap values,
HTTP failures, or invalid numeric readings stop the export. HTTP errors are reported
without response bodies, URLs, headers, or tokens. There is no automatic retry loop.
The protocol relies on the API honoring its documented ascending sort and bounds;
the controlled live procedure explicitly checks paging against a larger page size.

All series must finish before output writing begins. Earlier exports are not
overwritten. The CSV and summary are exclusively created; handled write failures
remove only files created by that export. A two-file write is not atomic across
process termination. Require successful completion and both files with matching
counts before using an export. Each CSV row is a real returned measurement:

| Column | Meaning |
|---|---|
| timestamp_utc | Returned timestamp rendered as UTC, retaining milliseconds |
| timestamp_epoch_ms | Original returned epoch millisecond value |
| equipment_id | Your local equipment label |
| connection_key | Actual full connection key |
| field | Your outgoing JSON field label |
| parameter_id | Actual qualified parameter ID |
| parameter_name | Name from the model schema |
| value | Numeric value returned by Tandem |
| unit | Schema `forgeUnit`, or blank when metadata does not supply one |

No unit is invented and no value is converted by this reader. Tandem may have
converted incoming values according to your saved source/destination units; reconcile
using the actual metadata and chart units. Rows sort by timestamp, equipment, field.
Unlike the upstream wide-format export example, this exporter does not round timestamps
to seconds, merge simultaneous measurements into one row, or require pandas.

The adjacent `.summary.json` identifies the API source, requested bounds, facility/model,
export time, page size, UTC-day query strategy, total count, every configured series
count, and any empty series. Empty
results produce a header-only/partial-data CSV with genuine rows only, explicit zero
counts, and exit code 3. A successful complete query can still return fewer historical
points than the number of successful POSTs. Investigate and report that difference.

## 5. Finish and protect credentials

Compare all six series to the chart and send log. Then clear credentials from this
terminal if no longer needed (this does not erase a local `.env`):

```powershell
Remove-Item Env:APS_CLIENT_SECRET, Env:APS_CLIENT_ID -ErrorAction SilentlyContinue
```

Discovery and exports are ignored by Git because they can contain facility-specific
information. Review them before sharing. HTTP 401 from APS means the token request
was not authenticated; HTTP 403 from Tandem can indicate missing service/facility
access, scope, or API entitlement. See [troubleshooting](TROUBLESHOOTING.md).

## Optional desktop export and evidence

The [optional panel](../README.md#optional-desktop-controls) calls this same reader;
it does not maintain a second authentication, mapping, paging, or CSV implementation.
CLI discovery is still used to fill private `config/readback.json`. Root `.env`
supplies APS credentials as above; masked ingestion URLs supply separate sender
credentials and let the panel verify that export targets the same model/connections.
URL/ID mismatch or missing configuration stops before authenticated API requests.
Keep the intended ingestion URLs in the panel even for historical-only export.

Enter a known historical From/To interval in UTC, with an inclusive lower and
exclusive upper bound. Export does not require a send in this session. After a send,
the panel preserves original client bounds and suggests query bounds padded by 60
seconds on each side. This is a labeled starting point, not proof of the actual
collection interval. Edit the query when appropriate and account for other runs'
points. Original client bounds are never relabeled as server timestamps.

Export readings opens a native Save As dialog, starting in ignored `outputs/` with
a timestamped CSV name. Both the CSV and companion summary must be new. The existing
writer's collision protection and handled-failure cleanup apply even if a file
appears after the dialog. Retrieval runs in a worker; sending cannot run concurrently.
Closing waits for the operation to finish. For regional routing use CLI `--region`;
the panel currently uses the default reader routing.

The panel shows genuine per-series counts and labels empty/partial results. The
result buttons become available only for the just-completed export. Open CSV and
Open folder are explicit actions using OS associations, with no Excel dependency;
failed opening does not remove the saved result. A new export attempt clears those
buttons, so failure cannot present a previous export as its result.

Save session log records categorized UTC GUI messages, sender status/bounds, query
intervals, API counts, and safe failures. Save it after completion; existing text
files require explicit replacement confirmation. It is GUI evidence, not terminal
stdout. For CLI evidence keep using the README's console capture and recorded UTC
bounds. Neither kind of log substitutes for the genuine API CSV and summary. Review
facility-specific exports before sharing. New GUI export behavior remains pending
authorized live verification; previous CLI API results do not prove the GUI path.
