# Verification status

This record separates implementation and offline evidence from live behavior.
The tutorial is ready for source review; **end-to-end Tandem readiness is not yet
established**. Offline checks made no live requests. Subsequent authorized read-only
authentication, metadata discovery, and historical export succeeded. A separately
authorized one-batch ingestion/readback test also passed, as recorded below.

## Offline verification - November 7, 2026

A source ZIP was extracted into separate temporary directories with spaces in their
paths. Environments were created from installed system Python, not copied from this
working folder. The documented setup script installed the five pinned dependencies
from locally cached wheels with package-index access disabled. No existing project
environment was replaced or modified.

| Environment | Setup and pip check | Offline suite |
|---|---|---|
| Windows CPython 3.13.3, experimental free-threading build selected by `py -3` | Passed | 38 passed, 0 skipped |
| Windows CPython 3.11.9 selected by `py -3.11` | Passed | 38 passed, 0 skipped |

Both installations used requests 2.34.2, certifi 2026.10.23, charset-normalizer 3.5.2,
idna 3.20, and urllib3 2.8.0. This checks installation from cached distribution
wheels, not current package-index availability. macOS/Linux execution is not verified.

The clean extracted package checks included:

- The README setup command, dependency check, one-batch preview, generator command,
  and byte-for-byte dataset reproduction.
- Default paths from another working directory, including directory names with spaces.
- The actual Windows controls-launcher environment check, without opening the GUI.
- 120 complete default batches / 720 values, UTC source spacing, unique measurements,
  and exactly the four documented ten-batch threshold excursions.
- Missing/invalid/duplicate CSV rows, inconsistent timestamp conventions, and skipped
  incomplete groups using separate fixtures.
- Preview without credential resolution or requests; 30-second interval rejection;
  17/50/100/120-batch counts and pacing with mocked waits/sends.
- Sanitized timeout results, failed second requests, incomplete-run console status,
  and log-open failure before HTTP.
- Desktop-session partial failure/resume and interruptible cooldown behavior without
  opening widgets or making requests.
- Real reader/auth/discovery/history code driven by synthetic HTTP responses; both
  connections and six series, customized display names, saved-source-field matching,
  short/full keys, bounds, milliseconds, paging, server caps, empty results, and
  safe failure handling.
- CSV/summary output failures and preservation of existing exports.
- UTC-day paging across empty periods and exact-midnight retries after a sparse
  look-behind response, with inclusive/exclusive bounds and small server caps.
- Root .env credential loading with literal values, process-variable precedence,
  blank-credential preflight, sanitized parse errors, and discovery from private
  facility_urn before connection/parameter IDs are known. No dependency was added.
- An actual PowerShell `Tee-Object` capture and UTC-bounds pipeline with explicitly
  mocked sender results, labeled OFFLINE MOCK ONLY. This proves capture behavior,
  not that any measurements were sent or retained.
- Explicit archive-file selection, source-byte and SHA-256 manifest checks, ZIP
  integrity, and exclusion of private files and unlisted source copies.

Offline tests ran with socket operations blocked. Synthetic API values and console
results are test evidence only. They do not establish access, ingestion, retention,
chart behavior, or live API compatibility.

## Reproduce local checks

From a clean extraction, follow README setup and run:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B scripts/ingest-data-individual-stream-from-csv.py --steps 1
.\.venv\Scripts\python.exe -B scripts/generate_demo_data.py --output outputs/recreated-demo.csv
(Get-FileHash data/demo_hvac.csv).Hash -eq (Get-FileHash outputs/recreated-demo.csv).Hash
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Expected: no dependency errors; 120 complete batches / 0 skipped; preview only;
720 generated values; equal hashes; 38 passing tests on a supported Windows
environment with Tkinter. Platforms without Tkinter skip desktop-session tests,
and non-Windows platforms skip the cmd-specific check.

## Authorized read-only live discovery - November 7, 2026

APS client-credentials authentication with `data:read` succeeded using the private
root `.env`. Facility access, default-model/schema discovery, both connections and
all six saved JSON source-field mappings were successfully read from Tandem.
Separate read-only relationship/host lookups corroborated the equipment matches
and asset designations; the connection keys also agreed with the existing private
ingestion destinations. No match depended on parameter display names alone.

Both connection keys and six parameter IDs were populated in private readback JSON.
Facility-specific discovery/host reports remain in ignored local outputs. Public
examples retain placeholders; no credentials or facility-specific IDs were added
to public documentation.

The APS application's Client ID must be added to the intended facility as a
service/API key with Read permission. Creating the APS app alone does not grant
facility access. This prerequisite is explicit in the setup instructions.

Only authentication and metadata reads were authorized: OAuth token requests and
read-only scan POSTs are not measurement ingestion or Tandem configuration changes.
During that initial discovery step no measurements were sent and no historical
stream data was queried; subsequent historical export is recorded separately below.

## Authorized read-only historical export - November 7, 2026

An interval covering known prior sessions was queried using genuine API history:
`2026-11-02T00:00:00.000Z <= timestamp < 2026-11-06T00:00:00.000Z`.
The archived attempt log supplied dates only, never exported measurement values.
All six configured series returned 11 readings each: 66 total rows. Returned schema
names/units and millisecond timestamps were preserved. The interval also contained
records on a date absent from the local attempt log; not all historical rows can
be attributed to that log.

The initial default export returned 66 rows, but the original page-size-2 traversal
returned only 30. Read-only diagnostics showed that an empty small-page response
could precede later dated history. A UTC-day split alone still missed data because
a one-millisecond look-behind landed in an exhausted preceding day. The reader now
pages within UTC days and retries the exact window start if its initial look-behind
is empty. A regression test covers empty days, midnight boundaries, short server
pages, and continued retrieval of later records.

Fresh exports with the corrected reader returned 66 rows at both default page size
and page size 2 over the same stable interval. Measurement identities, timestamps,
values and units matched; the CSV files were byte-identical. Earlier partial small-
page exports and diagnostic reports remain preserved under ignored outputs for
traceability. Use the final comparison report to identify the validated export pair.

CSV files, adjacent summaries, per-series timestamps/samples, and the paging
comparison remain private ignored outputs. No new measurements, Tandem changes,
commits or pushes were performed during that read-only export. These results verify historical retrieval for the
recorded interval, not the full new-sample ingestion/UI walkthrough.

## Controlled one-batch ingestion/readback - November 7, 2026

A separate authorization permitted exactly one batch from the current synthetic
CSV. The first batch was previewed and its six values saved before any send.
Destinations, six saved source-field mappings, and current schema units were
verified read-only. The current sender was then invoked with `--send --steps 1`,
a fresh private log, and no outgoing timestamp fields.

Exactly one AHU request and one VAV request were made; both returned HTTP 200.
Sanitized console text, UTC client bounds, request outcomes and six attempted
measurement rows were preserved under ignored outputs. A persistent one-shot lock
and request guard prevented automatic resends.

After more than 60 seconds of collection/processing allowance, an exact client-
bounds query returned all three AHU values but no VAV values. A separately named
query padded by 60 seconds on each side returned exactly one point for each of
the six series. Every value matched its expected JSON field and number; returned
Fahrenheit/percentage units matched the sample, so no conversion was needed for
comparison. No expected/source/log values were inserted into API output.

The VAV server timestamp was 136 milliseconds after the recorded client end.
This explains its absence from the exact half-open interval. The observation
shows a client/server timing difference; it does not isolate processing latency
from clock offset. The padded window and actual returned timestamps were retained.

Final result: six confirmed series, zero missing values, zero request failures,
two measurement POSTs and zero resends. Earlier historical exports and the exact-
window partial result were preserved. No Tandem settings, longer replay, commits
or pushes were performed. This verifies the first synthetic batch through API
readback; charts, full model setup and threshold/dashboard behavior still require
separate verification.

## Live verification still required

Follow [LIVE_VERIFICATION.md](LIVE_VERIFICATION.md) with explicit authorization:

1. Verify the model import, parameter specifications/units, classification/template
   application, equipment/room relationships and saved UI configuration visually.
2. Record actual collection frequency and retention settings. The verified one-batch
   result does not establish longer-run collection behavior.
3. Inspect readable charts and reconcile hover values/timestamps/units with the
   actual one-batch export. A longer controlled replay requires separate authorization.
4. If testing parameter renaming, confirm stable IDs and updated display names
   through discovery/readback without changing JSON keys.
5. Exercise threshold patterns and create/save/reopen the native dashboard under
   separate authorization, including stream-card availability and readable ranges.

Historical API export and paging comparison passed for the recorded interval.
The first current-sample batch passed ingestion/readback; UI, longer-run collection,
and threshold/dashboard verification remain pending.
The live walkthrough follows public Autodesk guidance; account-specific controls
remain unverified until observed.

## Learning-path review - November 7, 2026

The README now leads from prerequisites and private configuration through offline
payload inspection, Tandem setup/mapping, captured controlled streaming, genuine
readback, charts, and native thresholds/dashboard creation. It separates supplied
working examples from learner configuration, verification, and interpretation.
Desktop controls follow the primary Python workflow as an optional convenience.

All 13 public Python files were reviewed for educational comments/docstrings.
Executable ASTs, excluding docstrings, matched their pre-review versions: no
execution logic changed. All 38 offline tests passed from the working folder with
socket connections and DNS blocked. All 10 README PowerShell blocks parsed without
syntax errors, and 35 local Markdown links/anchors resolved. These checks do not
execute live commands or validate external websites. No additional Tandem/APS
requests or measurements were made during this review. An independent beginner
walkthrough and the live UI/longer-run checks above remain outstanding.

## Optional desktop additions - November 7, 2026

The panel now records categorized UTC GUI messages and saves an explicitly labeled
GUI session log through Save As. It records original client run bounds, interval,
requested/completed batches, request outcomes, and completion/failure/interruption.
It also calls the existing reader for explicit historical exports: editable half-open
UTC bounds, labeled ±60-second suggestions, model/connection correspondence checks,
background retrieval, existing exclusive CSV/summary writing, and explicit OS opening.
The original sender bounds remain separate from the editable query. CLI entry points
and previously dated live evidence above are preserved.

Windows CPython 3.13.3: **56 offline tests passed, 0 skipped**, with socket connections
and DNS blocked. Coverage includes session-log categories/sanitization, replacement
confirmation and failed writes, padding across UTC midnight, short/full keys and
wrong-model/swapped-connection rejection, missing credentials/configuration, successful/
empty/partial/failed exports, both companion-file collisions and a racing collision,
background completion/control states, original bounds, and mocked OS opening/failures.
Existing sender, reader UTC-day paging, and setup/distribution regressions also passed.
The actual private ingestion/readback files passed a local ID correspondence check;
this did not authenticate or query Tandem, and their contents were not exposed.

An actual Tkinter window was opened locally with networking blocked, no private URL
loading, and sending/export disabled for inspection. Preview showed the real bundled
CSV; Save session log wrote those real preview messages using a mocked dialog selection.
A window-only screenshot was inspected at 980×900: UTC fields, export, save-log and
open-result controls were visible. This is visual/local evidence, not a live export
or a manual test of the native Save As dialog. No OS CSV application was launched;
OS opening was mocked in tests. macOS/Linux GUI execution remains unverified.

All **49 local Markdown links/anchors** resolved; **22 PowerShell command blocks**
parsed without syntax errors. The README map matches the **36-file** distribution
selection exactly. External websites were not re-queried. Commands containing live
sends or API reads were not executed during this work. No additional measurements,
APS/Tandem requests, configuration changes in Tandem, Git initialization, commits,
or pushes were made. New GUI export behavior and native dialog/OS integration still
need the separately authorized checks in the live checklist; previous CLI success
does not establish that result.

## Review package

The working project folder is the authoritative source. The ZIP is an optional
review copy built from those files, not a replacement project. After local cleanup,
obsolete copies, old archives, verification environments, caches, the superseded
CSV, and historical send logs are preserved in a separate backup outside the project.
Active private configuration and the working environment remain local and ignored.
The working folder's publishable files are compared byte-for-byte with the ZIP.
The initial cleanup passed 38 offline tests and checked ignore rules in a disposable
repository for the then-current 34-source-file set. The additions above now pass 56
tests; the two new public files are the script guide and local panel helper module.
Private .env, JSON configuration, environments, local editor settings, and generated
artifacts remain excluded. No Git repository was initialized in the actual working
folder or during the panel additions.

`scripts/build_distribution.py` selects exactly 37 source files and adds
`MANIFEST.sha256`. The review ZIP contains only current tutorial sources, tests,
documentation, placeholder directories, example configurations, and the original
MIT-licensed synthetic sample. It excludes credentials, private JSON, environments,
caches, generated logs/exports, earlier locally retained data, and obsolete copies.
It is a source review artifact, not proof of live completion.

For an extracted review archive, validate the listed file hashes with PowerShell:

```powershell
Get-Content MANIFEST.sha256 | ForEach-Object {
    $expected, $relative = $_ -split '  ', 2
    if ((Get-FileHash -LiteralPath $relative -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw "Manifest mismatch: $relative"
    }
}
```

No Git initialization, commit, or push was performed as part of this verification.

## Publication-file check - November 7, 2026

Git was first initialized for the subsequent publication-file check. The statements
above about no Git initialization describe the earlier verification phases; no
repository history was lost. No commit or push was made by this file check.

The current publication set has 37 source files. The additional maintenance file,
`.gitattributes`, preserves LF endings for `data/demo_hvac.csv`: Windows Git with
`core.autocrlf=true` must not change the fixed-seed dataset's bytes on checkout.
The README map and distribution selection include this rule. The earlier 36-file
GUI review record describes its then-current source set.

The actual Git index was checked against the complete working-folder inventory,
not inferred from the ZIP: 37 public files, with no additional unignored
untracked files. Private/generated paths passed real Git ignore checks;
the public examples and both .gitkeep files remained allowed. Staged blobs
passed a targeted offline scan for known local private values (including
common encodings), credential URLs, private keys, and common token patterns.
No secret values or matching source contents were printed. No unresolved
publication-file purpose, unused supporting helper, or obsolete source copy
was identified; no additional material needed moving to the existing backup.

A temporary checkout using core.autocrlf=true preserved the CSV byte-for-byte
against the generator. Four setup/distribution tests passed after adding the
maintenance rule. The updated review ZIP contains the same 37 source files
plus its generated MANIFEST.sha256; the manifest and archive itself are not
staged. Source/index/archive bytes and manifest hashes were compared.
External websites and live Tandem behavior were not rechecked. Pending live
UI/GUI/longer-run limitations above remain explicitly documented.
