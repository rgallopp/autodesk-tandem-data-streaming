# Adapt the worked example

Keep the same flow: CSV → equipment routing → numeric payload fields → connection
mappings → historical streams → API export. HVAC-specific names are examples.

For a first adaptation, customize only a parameter's display name, rerun discovery,
and verify its unchanged ID/source field and new exported name. No credential-code
changes are needed. For a different dataset or equipment, work through these steps:

1. Use a CSV you are authorized to use, with `timestamp,equipment_id,sensor,value`.
   Use ISO 8601 timestamps consistently, finite numeric values, and explicit external
   documentation of units and timezone. This replay groups identical timestamp text;
   do not mix equivalent timestamps written with different offsets or formats.
   Mixing timezone-aware and timezone-free values is rejected with a safe line-number
   error. The bundled synthetic sample uses UTC consistently.
2. Edit the small `FIELDS` dictionary in `scripts/measurements.py`. Its outer keys
   are equipment IDs; inner keys must exactly match source sensor labels; inner
   values are the outgoing JSON field names. One equipment item may have one or
   several measurements. Keep each item's field names distinct.
3. Update private `config/config.json` with one distinct Individual ingestion URL
   per equipment ID. The existing AHU/VAV environment-variable shortcuts apply only
   to those original two IDs; for other equipment use the JSON file or hidden prompts.
4. Create numeric parameters with the correct specifications/units, assign them
   through the facility template, configure the equipment assets and connections,
   and map your new fields. Give each connection an intentional host/room.
5. Preview before sending. A complete source group must contain every mapped
   equipment/sensor pair. Missing groups are skipped for the whole batch. Unknown
   pairs, duplicate readings, invalid dates, and nonfinite numbers are rejected.
   This deliberate policy is suitable for synchronized examples; asynchronous real
   sensors may need a different policy, outside this small replay tutorial.
6. Run discovery and edit private `config/readback.json` to include every new
   equipment ID and payload field with its actual connection/parameter IDs. The
   reader checks IDs and saved source fields against `FIELDS`, so it does not silently
   leave out new series or accept swapped IDs. Customize parameter display names
   independently of the flat JSON keys; readback retains current names from the schema.
7. Update example configuration, documentation tables, expected counts, and tests
   if you publish a different worked dataset. The supplied dataset regression test
   intentionally describes the reproducible `data/demo_hvac.csv` and its generator.

For a different CSV using the same equipment and sensor labels, use the CLI's
`--csv path/to/authorized.csv` option; there is no need to overwrite the default sample.
The optional desktop panel always uses the bundled default sample.

For example, a small alternative mapping could be:

```python
FIELDS = {
    "pump-01": {"Discharge Pressure": "discharge_pressure"},
    "meter-01": {"Power": "power", "Energy": "energy"},
}
```

This has three values and two HTTP requests per complete batch, not six values.
For `B` completed batches, requests = `B × equipment count`, measurement values =
`B × total mapped fields`, and values sent per series = `B`. Approximate replay
duration is `(B - 1) × interval + HTTP request time`. Stored historical counts still
depend on Tandem collection, processing, units, mappings, retention, and query bounds.
The CSV's source time is retained only in the local attempt log; historical replay
with explicitly posted source timestamps would require a separate deliberate change.
