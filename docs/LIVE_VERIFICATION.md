# Controlled end-to-end verification

Use a facility you are allowed to modify. The reader is read-only with respect to
measurement data; the sender intentionally adds measurements. Run this checklist
before claiming the tutorial is verified live. Record observed results rather than
turning the checklist into a claim of success. Current results are in [VERIFICATION.md](VERIFICATION.md).

## Preflight

1. Use a clean setup and run the offline tests. Record Python, requests, OS, and date.
2. Confirm two intended equipment hosts/rooms, asset classification/designation,
   numeric parameters, the synthetic sample's documented units, template application, and six saved
   mappings. Record actual collection frequency, retention, and offline timeout.
3. Confirm APS authentication and facility access before a long replay. If mappings
   have already been saved, confirm discovery as well. After the one-batch mapping
   test below, match both keys, six IDs, and saved source fields in private
   `config/readback.json` to the UI. Credentials must remain outside shared evidence.
4. Ensure other senders are stopped. Allow at least one collection interval and
   at least 60 seconds since any prior request to each connection.

## Establish the one-batch mappings

Preview one batch and compare its exact six numeric values with the setup table.
Send one batch, save/verify mappings, and if necessary send a fresh test after the
cooldown. Inspect the latest cards for both equipment items. This establishes
payload routing and current values; it does not prove a history point count.
Keep this test outside the measured run below. Never publish credential-bearing
connection panels in screenshots.

Run discovery after mappings are saved. Verify each current display name and source
field. In a controlled test, customize a display name without recreating its
parameter, rerun discovery to a fresh file, and confirm the unchanged ID and current
name appear in an actual export. Do not change CSV labels or JSON keys for this rename.

## Run and inspect history

1. Wait until the mapping/test interval is outside the next run's history window.
   Record the UTC start/end with the commands in the README.
2. Send six batches with `--interval 60` and a fresh `--log logs/verification-send.csv`.
   Capture console output. Expected successful attempts: 12 requests, 36 measurement
   values, six values per series, roughly five minutes plus request time. Check the
   process exit code, both equipment IDs, all fields, and HTTP outcomes.
3. Wait for the recorded collection interval and processing. Open Streams → Graph,
   choose the UTC run range converted to the UI's timezone, and check all six series.
   Record visible timestamps/values, units, equipment/room relationships and range.
   Hover/zoom to distinguish actual points from display aggregation. Latest cards,
   offline status, and Usage/reserved capacity are insufficient history evidence.

## Retrieve and verify actual API data

1. Use the run bounds and a fresh CSV output. Expected reader behavior: both
   connections and all six configured series are queried, each count is printed,
   and a CSV plus summary is written. Preserve genuine returned timestamps/values.
2. Review each series count, earliest/latest returned time, and first/last values.
   Compare with chart hover values and send attempts, accounting for any configured
   unit conversion. Do not assume the client send timestamp equals stored time.
3. Repeat the same stable window with `--page-size 2` and a different output filename.
   Compare sorted `(connection_key, parameter_id, timestamp_epoch_ms, value, unit)`
   rows with the default-page export. They must match, demonstrating that paging did
   not silently lose measurements. Wait until ingestion/collection has settled first.
4. Query a deliberately empty interval to a new filename: expect explicit zero
   counts, a header-only CSV, summary, and exit code 3, not fabricated source values.
5. If collection bucket alignment excludes an edge point, create a separately labeled
   export with one collection interval of padding. Investigate old test readings in
   that window. Do not force exact counts by changing timestamps or inserting rows.

For a stable one-minute configuration, six posted batches suggest approximately six
history points per series, but the acceptance criterion is an explained reconciliation
with actual recorded history. Faster 30-second sends do not guarantee additional
separate retained points. Any discrepancy remains part of the verification record.

## Verify thresholds and the native dashboard

1. Apply the documented demonstration bounds from [the walkthrough](TANDEM_SETUP.md#9-configure-demonstration-thresholds),
   checking units, scope and persistence. These are teaching thresholds, not operating limits.
2. Use a separate captured 40-batch run at 60-second spacing to reach Zone Temperature
   batches 21-30 and normal data before/after it. Expect 80 requests, 240 supplied values,
   and about 39 minutes plus requests. Compare the approximately 80 F event against the
   78 F upper alert using actual chart/API values.
3. For full pattern validation, use 120 batches to cover all four documented events.
   Verify event bounds against returned history without replacing server timestamps
   with source dates or client request times.
4. Create and save a native dashboard using the walkthrough. Reopen it and verify
   all six series, temperature/humidity separation, selected interval and known values.
   Record unavailable stream-card features as unresolved account limitations.

## Verify the optional panel separately

These are additional authorized live checks, not results established by offline
widgets/tests or by earlier CLI exports. Do not send merely to test historical export.

1. Restart the current launcher after setup. Preview and save a GUI session log;
   opening/preview must make no requests. Check UTC categories and absence of URLs,
   credentials, and raw sensitive errors. Label it GUI evidence, not terminal stdout.
2. Using the existing private configuration, enter a stable known historical UTC
   interval. Export without sending. Check that the current panel URLs correspond
   to the readback model and both connection keys. Compare all six CSV series and
   the companion summary to a fresh CLI export of the same stable interval.
3. Verify the native Save As dialog, collision handling for either output file,
   per-series/empty counts, responsive background state, and disabled sending during
   export. Check explicit Open CSV/Open folder on the local OS without requiring Excel.
4. Only if a new send has separate authorization, capture its GUI session, confirm
   original UTC bounds and requested/completed counts, and compare genuine readback.
   Verify that the suggested ±60s query padding leaves original bounds unchanged.
   Inspect other-run points in the expanded window; never automatically resend.
5. Save the GUI session log after exporting, inspect all artifacts for sensitive
   information, and record failures and actual observed behavior. Chart/threshold/
   dashboard checks remain separate native Tandem verification tasks.

## Record the outcome

Keep an ignored local record with: UTC date/range, sanitized environment versions,
facility/configuration identifiers, collection/retention settings, HTTP outcomes,
counts per series, CSV/summary paths, page-size comparison, unit interpretation,
chart observations/screenshots, and unresolved discrepancies. Update the public
verification status only with sanitized conclusions supported by those artifacts.

Do not claim API readback passed if only mocks, the source CSV, or the send log were
checked. Do not claim chart display passed if only HTTP status or latest cards were
checked. API success and chart inspection are separate verification steps.
