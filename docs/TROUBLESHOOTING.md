# Troubleshooting

| Symptom | Action |
|---|---|
| `py` missing | Install Python with pip, reopen the terminal, or use the actual installed `python` command for setup. |
| `uv trampoline` / copied environment fails | Run `scripts/setup_environment.py` with an installed system Python, not the broken `.venv` interpreter. The script preserves an unusable environment and creates a new one. |
| Setup cannot rename the environment | Close the GUI, terminals, editors, and Python processes using it; verify write access to the project. |
| Package download blocked | Check network, proxy, and package-index access. Run installation with the environment's interpreter. Do not disable certificate verification. |
| `No module named requests` | Run setup or install `requirements-lock.txt` using the interpreter that will execute the scripts. |
| Tkinter missing | Use the CLI, or install your platform's Tk support for optional desktop controls. On Linux this may be a separate OS package. |
| PowerShell activation blocked | Use the explicit `.venv\Scripts\python.exe` path; activation is unnecessary. |
| CSV/config validation fails | Check required headings, exact equipment/sensor names, numeric finite values, dates, duplicate rows, JSON syntax, and distinct URLs. Preserve the original CSV. |
| CSV error gives a line number | Fix missing cells, invalid dates/numbers, duplicate readings, or mixed timezone-aware/timezone-free timestamps on that line. Raw cell values are intentionally not echoed. |
| Unexpected sample values/counts | The default is the fixed-seed `data/demo_hvac.csv`: 120 complete batches, 720 values. A separately supplied CSV requires `--csv`; its counts and units may differ. |
| Old configuration ignored | CLI `TANDEM_AHU_URL` / `TANDEM_VAV_URL` override the file. Clear stale variables; the GUI only loads the file/fields. A malformed file must still be corrected. |
| No measurement parameters available | Assign parameters to the connection class in the template and apply/update the template in the facility. |
| Ingestion HTTP 401/403 | Recopy the Individual link from the actual connection and check that its secret is current. APS readback credentials are a separate authentication method. |
| Ingestion HTTP 404 | Check the current facility, connection, endpoint, and newly copied link. Do not infer a unique cause from 404 alone. |
| `NETWORK_ERROR` / timeout | Check connectivity, proxy, and certificates. The request may have arrived despite a lost response; inspect Tandem and the log before retrying. |
| Only AHU has an entry | The sender may have stopped on AHU failure or been interrupted before VAV. Check status and logs. |
| HTTP 200 but no useful history | Save mappings, check numeric types and source/destination units, actual collection frequency, retention, processing delay, connection selection, and chart range. |
| Latest card becomes Offline | The finite replay stopped or no data arrived within the configured offline timeout. This is separate from historical data retention. |
| Old values repeat after restart | A new CLI invocation restarts at the first source group. The GUI only retains progress while open. |
| Missing APS credentials | Fill root `.env` keys `APS_CLIENT_ID` and `APS_CLIENT_SECRET`, or set those process variables. Empty/stale process variables take precedence; remove them to use file values. |
| Invalid .env assignment/quotes | Use only the two APS keys, once each, with literal single-line values and matching outer quotes if quoted. Facility/connection/parameter IDs belong in private readback JSON. |
| APS authentication HTTP 401 | Verify Client ID and current Client Secret for the same APS application. Refresh the variables in this terminal. Never share their values. |
| Tandem API HTTP 403 | Confirm the application is added as a service to this facility, has suitable permission and `data:read`, and the account permits API access. |
| API HTTP 404 / missing default model | Check facility URN versus model URN, service access, connection existence, and documented region routing. |
| API HTTP 429 | Stop, inspect other callers and service limits, and retry deliberately later. The reader does not run tight retries. |
| Output exists | Choose a new `--output`; existing exports are preserved. |
| Discovery lists no mapped parameters | Save connection mappings in Tandem, refresh, and run discovery again to a new file. |
| Readback config rejected | Match every equipment/field in `measurements.py` with actual distinct connection keys and qualified parameter IDs from discovery. |
| Parameter ID exists but export stops | Verify that its saved source field matches the configured JSON key. A swapped valid ID or unrecognized mapping path is rejected; display names may vary. |
| Discovery response rejected | Do not share the raw response or integration configuration. Record the sanitized error and verify the actual API response shape with an authorized maintainer. |
| CSV/summary write failure | Choose writable fresh paths. Handled failures remove newly created files; existing exports are preserved. After abrupt termination, require a complete matching CSV/summary pair and successful completion before using results. |
| No threshold event in a short run | Six batches are normal baseline data. The first high Zone Temperature event is batches 21-30; use 40 batches to see normal values before/after it. |
| Dashboard has no stream history cards | Check account feature availability and permissions. A data-completeness card is not a substitute for historical stream charts. |
| Empty/too few API readings (exit 3) | Check IDs, saved mappings, known chart history, UTC bounds, collection bucket alignment, processing delay and retention. Preserve zero counts; never pad CSV rows. |
| Too many API readings | Exclude earlier mapping/test runs and other senders. Label any expanded query window. |
| API and chart values differ | Inspect source-unit conversion, schema units, chart axes/aggregation, timestamps, and whether the selected parameter IDs match. |
| Paging/bounds/change error | Stop concurrent sending, wait for collection, and retry to a new file. Run the small-page comparison in the live checklist. Do not treat an incomplete query as a completed export. |
| Small-page export omits later dates | Use the current UTC-day paging implementation with exact-boundary retries. Earlier single-range paging could stop on an empty response before later days. Preserve earlier exports and compare the same stable interval with default and small pages. |
| GUI Save session log is disabled | Wait for the send/export worker to finish. Save the actual categorized UTC messages as a GUI session log, distinct from terminal stdout. |
| GUI export setup/matching error | Check the current masked ingestion URLs (including session overrides) against `config/readback.json` and discovery. Fill root `.env` APS keys separately. Both equipment destinations must match by model and connection ID, not display name. No setup wizard or automatic remapping occurs. |
| GUI query fields are blank | Enter known historical UTC bounds, or use last-run padding after a deliberate send. A historical export never requires a new send. |
| GUI query includes unexpected points | The suggestion pads client bounds by 60 seconds each side. Preserve the original bounds and identify other runs' data; edit the query rather than replacing server timestamps. |
| GUI CSV/summary filename collision | Choose a fresh filename; either companion file prevents replacement. Session-log replacement is a separate explicitly confirmed operation. |
| GUI Open CSV/Open folder fails | The export stays saved. Use its displayed path manually and check OS file associations. Excel is optional. Result buttons clear on a new export attempt and remain disabled after failure. |
| GUI closing waits during export | Background retrieval finishes or reports failure before exit. Stop controls sending, not historical queries. For region-specific requests use the CLI's `--region` option. |

Allow at least 60 seconds between attempts on each connection. Run only one sender.
The CLI cooldown lasts within a run, and the GUI's lasts within its open session;
neither prevents another process from sending. There is no durable resume or automatic
rollback if one request succeeds before another fails.

When requesting help, share the command with secrets removed, checkpoint, sanitized
status, expected behavior, and checks performed. Do not share ingestion URLs,
authorization headers, environment dumps, APS secrets, or raw integration settings.
