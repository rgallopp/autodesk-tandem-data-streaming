# Configure a facility, connections, charts, thresholds, and a dashboard

This walkthrough is for an authorized facility and model of your choice. The CSV
labels `ahu-01` and `vav-3` are routing labels, not proof of real equipment identity.
The bundled CSV is [synthetic demonstration data](../data/README.md).

The UI instructions follow Autodesk's published guides. Interface labels and account
capabilities can differ. Inspect the saved result at each checkpoint; these steps
have not yet been exercised live for this release.

## 1. Create a facility and import models

1. Sign in to Tandem and choose the account where you may create a facility.
   Confirm you have permission to upload content; facility editing alone may not
   include model upload permission.
2. Open Facilities and choose Create New Facility. Enter a descriptive name,
   select the intended storage region and other required details, and create it.
   Record the region for later API discovery.
3. Open the facility's Files panel. Choose the add/import/upload action for a
   model file you are permitted to use, or an authorized connected source if
   available. Follow the upload prompts and wait for processing to finish.
4. Add any other necessary discipline models, then check visibility and alignment.
   Locate an identifiable AHU and VAV instance using the viewer or Inventory.
   Verify instance properties; a matching family/type name alone is insufficient.
5. Check that the model exposes usable rooms/spaces and that the intended room
   can be selected. If not, obtain a suitable model or correct its source content.
   A connection can exist without a room, but that does not demonstrate room relationships.

Bring an authorized model that meets these requirements; building models are not
bundled with the tutorial. If you cannot locate
two equipment instances or usable rooms, resolve that before configuring connections.

Expected result: a new facility containing processed, visible models, two identified
equipment instances, and selectable rooms/spaces. See Autodesk's
[facility/model tutorial](https://www.autodesk.com/learn/ondemand/tutorial/create-a-new-facility-and-add-models-in-tandem)
and [UI reference](https://help.autodesk.com/cloudhelp/ENU/Tandem-Getting-Started/files/tandem-navigate-ui.html).

## 2. Choose classifications

In Manage -> Classifications, inspect the supported library and select a system
appropriate to your model. OmniClass is one option; select actual library classes
for the AHU, VAV, and logical connections. Record the system, code, and description.
Do not invent standard codes. A custom classification requires your own authorized
classification definition.

Equipment and its connection need not share a class. The connection class determines
which measurement parameters can be mapped. If one class is shared by both
connections, assign all six measurement parameters to that class.

Expected result: identified, available classes and an explicit choice for each asset
and connection. [Autodesk Specify](https://help.autodesk.com/cloudhelp/ENU/Tandem-Specify/files/tandem-specify.html)
explains classifications, parameters, and templates.

## 3. Create six numeric parameters and units

In Manage -> Parameters, choose Create Parameter for each row below.
Set a numeric data type, Element context, the matching measurement specification,
unit, and sensible precision (two decimals suits the sample).

| Equipment | Exact CSV sensor | Flat JSON key | Example display name | Synthetic source unit |
|---|---|---|---|---|
| ahu-01 | Chilled Water Temperature | chilled_water_temperature | Chilled Water Temperature | Fahrenheit |
| ahu-01 | Heat Pipe Leaving Tempera | heat_pipe_leaving_temperature | Heat Pipe Leaving Temperature | Fahrenheit |
| ahu-01 | Outside Air Humidity | outside_air_humidity | Outside Air Humidity | percent RH, 0-100 |
| vav-3 | Discharge Air Temperature | discharge_air_temperature | Discharge Air Temperature | Fahrenheit |
| vav-3 | Zone Humidity | zone_humidity | Zone Humidity | percent RH, 0-100 |
| vav-3 | Zone Temperature | zone_temperature | Zone Temperature | Fahrenheit |

Use the full heat-pipe name for display; the truncated CSV sensor label remains an
exact lookup key. Other display names are also allowed. Do not change the JSON key
to match a customized display name. Later discovery supplies the actual parameter IDs.

Temperature and relative humidity require different specifications. Configure
humidity consistently with the available percentage/ratio scale: a sample input of
49.23 means 49.23 percent RH, not 0.4923 percent or 4923 percent. Check the first
payload against the displayed result. Choose incoming units deliberately when saving
mappings. Labeling a Fahrenheit number as Celsius does not convert it.

Expected result: six saved numeric parameters with explicit specifications and
units. For a custom dataset, establish its units independently; the Python sender
does not convert them.

## 4. Assign and apply a facility template

1. In Manage -> Facility Templates, add or edit a template using the chosen
   classification system.
2. Select the AHU connection's class, choose Assign parameters, and assign its three
   parameters. Repeat for the VAV class. If both share a class, assign all six there.
3. Save/update the template.
4. Open the facility -> Assets -> Apply Template, select the template and apply it.
   When changing a template later, update the facility's applied template as well.
5. Check that the intended classifications now expose the parameters.

Expected result: choosing the connection class offers the correct measurement
parameters. "No parameters found for current classification" means you should check
class assignments and the facility's applied template, not modify JSON keys.

## 5. Classify equipment and make assets

Locate the verified AHU and VAV instances. Select each, assign its actual equipment
classification, and use Make Asset if it is not already designated as an asset.
Inspect the resulting asset properties. Avoid applying the operation to a type when
you intend to designate a particular instance.

Expected result: the intended two equipment instances are classified assets.
Asset designation, classification, and a connection's host relationship are
different operations. See [asset concepts](https://help.autodesk.com/cloudhelp/ENU/Tandem-Manage/files/tandem-usage.html).

## 6. Create connections and assign hosts and rooms

1. Open Connections -> Create -> Individual. Name the AHU connection
   `AHU-01 CSV Demo` and select the class with its measurement parameters.
2. Under Properties -> Relationships, use Assign to Host, select the verified AHU
   instance, confirm, and inspect the saved host relationship.
3. Inspect Rooms under Relationships. If needed, assign the intended available
   room and save. Host selection does not by itself establish a verified room.
4. Repeat for `VAV-3 CSV Demo`, with its own class, host, and room.
5. Use Copy Link on each actual Individual connection. Save each secret-bearing
   ingestion link only in the corresponding private configuration entry described
   in the README, or use the CLI's hidden prompts.

Expected result: two distinct destinations, each on the intended equipment and room.
A logical connection can contain three measurement streams; no new sensor geometry
is needed. [Autodesk's connection guide](https://www.autodesk.com/learn/ondemand/curated/tandem-quick-start-guide/3aVQtYTWsDbl9Zimpd5sC2)
explains the panels and host concepts.

## 7. Establish JSON mappings and collection

Preview the first batch with the README command. Expected AHU JSON:

```json
{"chilled_water_temperature": 54.08, "heat_pipe_leaving_temperature": 57.81, "outside_air_humidity": 49.23}
```

Expected VAV JSON:

```json
{"discharge_air_temperature": 59.58, "zone_humidity": 45.22, "zone_temperature": 71.85}
```

1. Use the README's captured one-batch command (`--send --steps 1`) only when
   authorized. It supplies the sample used below; do not run a second uncaptured
   command just because you are following this detailed guide as well.
2. Open the Connections menu -> Configure Connections. Select the relevant
   connection/class and inspect the incoming payload.
3. Map each parameter to its matching flat JSON key in the table above: three keys
   for AHU and three for VAV. CSV columns `value`, `sensor`, and `equipment_id`
   are not sent and must not be selected as payload paths.
4. Verify incoming and destination units. Leave any custom timestamp path unset:
   this replay posts no timestamps and uses Tandem server time.
5. Save, reopen, and inspect all mappings. Review any shared-class effects before
   saving; configuration can affect other connections.
6. Record actual collection frequency, retention, and offline timeout. Use
   one-minute collection where available for this demonstration. A longer collection
   interval changes historical point counts.
7. Wait at least 60 seconds after the last attempt on each connection. Send another
   test if the first payload was used only to establish the mapping.

Expected result: six correct latest values and persisted mappings, verified against
the known first payload and units. This is not yet a history-count test.
The sender does not change collection settings and requires at least 60-second
replay intervals. [Autodesk ingestion guidance](https://aps.autodesk.com/blog/adding-iot-sensors-tandem-api)
documents a one-minute minimum; successful faster POSTs are not evidence of distinct
retained points.

## 8. Read charts and reconcile history

First complete the README's controlled streaming and genuine readback checkpoints,
allowing collection and processing time. One batch verifies individual points; use
a deliberately captured multi-batch run when you need a trend.

1. Refresh Connections/Streams and check equipment/room associations and latest values.
2. Open Streams, select the intended connection and parameters, and switch to
   Graph/Charts. Select a range covering the **current replay**, not the source dates.
   Account for the UI timezone when entering recorded UTC bounds.
3. Start with one series. Check the name, unit, timestamp and value by hovering over
   points. Zoom in to reduce display aggregation.
4. Give temperature and humidity separate views/axes; do not interpret percent RH
   against a temperature axis. Use visible legends and a range that makes variation
   readable, without implying an unlabelled common scale.
5. Check all six series and both connections. If they are not readable together,
   inspect smaller groups rather than hiding missing series.
6. Compare your [API export](READBACK.md) for the same interval with the charts and
   send attempts: names, IDs, timestamps, units, values, and counts. If you adjust the
   interval, export it to a new filename so that the comparison remains explicit.
7. Record differences and investigate units, mapping, processing delay, collection
   buckets, retention, and query bounds. Use the guide's padded-window procedure
   only when needed, labeling any expanded interval.

Expected result: interpretable history for the intended series, with an explained
reconciliation. Latest cards, Offline status, and Usage capacity do not establish
the number of retained points. A heatmap is optional and depends on suitable rooms
and relationships.

## 9. Configure demonstration thresholds

These settings illustrate native Tandem visualization, not operating/safety limits.
They assume the bundled sample's Fahrenheit and percent-RH units; convert bounds
deliberately if you configure different destination units.

| Series | Lower alert | Lower warning | Upper warning | Upper alert |
|---|---:|---:|---:|---:|
| Chilled Water Temperature (F) | 45 | 48 | 60 | 64 |
| Heat Pipe Leaving Temperature (F) | 48 | 50 | 68 | 72 |
| Outside Air Humidity (percent RH) | 20 | 30 | 70 | 80 |
| Discharge Air Temperature (F) | 50 | 52 | 66 | 70 |
| Zone Humidity (percent RH) | 20 | 30 | 60 | 70 |
| Zone Temperature (F) | 65 | 68 | 75 | 78 |

1. In Streams, select the intended parameter/connection and open Thresholds.
2. Create or edit a threshold definition for that parameter. Enter a descriptive
   demonstration name and the corresponding lower/upper warning and alert bounds.
3. Confirm the scope: the intended parameter and connections, not every stream
   indiscriminately. Save/apply the definition and reopen it to verify persistence.
4. Return to Graph view and inspect the displayed threshold bands/coloring using the
   correct unit scale. Repeat for the other desired parameters.
5. After a longer replay, inspect normal -> excursion -> normal sections using hover
   values and API rows. Retained history and displayed status need not update instantly.

For an initial upper-temperature demonstration, change the captured replay command
to `--steps 40 --interval 60` and use fresh console, bounds, and export filenames.
This includes normal batches 1-20, elevated Zone Temperature in batches 21-30,
and normal batches 31-40. It sends 240 values in 80 requests and takes about
39 minutes plus requests. The upper alert bound is 78 F; event values are about 80 F.

A full `--steps 120` run also reaches Outside Air Humidity batches 61-70
(about 85 percent RH), Chilled Water Temperature batches 91-100 (about 65 F),
and low Zone Temperature batches 101-110 (about 64 F).
Each ten-reading event spans 135 source minutes from first to last reading and
returns to baseline on the next 15-minute boundary. At 60-second replay spacing,
the first-to-last event requests span about nine minutes plus overhead; the next
normal batch follows about one minute later. Do not equate source duration with
replay duration or promise a fixed number of retained buckets.

Expected result: saved thresholds and observed history consistent with the known
patterns and units. Follow [Autodesk's threshold tutorial](https://www.autodesk.com/learn/ondemand/tutorial/create-and-set-thresholds)
for the current account UI. Threshold visualization here does not add custom rules,
notifications, or status writeback code.

## 10. Create, save, and reopen a native Tandem dashboard

1. From Facilities, select this facility and use the dashboard creation action
   (`+ New` in the facility details panel), or the Dashboards control inside the
   facility. Create a named dashboard such as `HVAC CSV demonstration`.
2. Choose the available blank/operations layout or template suitable for stream
   data. Inspect the available card types before proceeding: the lesson needs
   historical stream/time-series cards, not only asset-data completeness cards.
3. In dashboard editing, add a stream/time-series card and select the AHU connection
   and its temperature parameters. Give it a readable title and units.
4. Add a separate AHU humidity card. Add VAV temperature and humidity cards, selecting
   the actual connections/parameters identified above. Ensure all six series are
   represented without combining incompatible units on an unlabelled axis.
5. Select the measured replay interval in each chart or the shared time control
   when available. Check timezone, legend, unit scale and hover values.
6. Optionally add latest-value/gauge cards to complement history. They do not replace
   the historical charts or prove point counts.
7. Arrange the cards and use Save. For an existing dashboard use Save as new if you
   intend to preserve the earlier version.
8. Leave the dashboard, reopen it from the facility's dashboard list, and verify
   the saved cards, connection selections, names, units, layout, and time controls.
   Recompare a known event value with the Streams chart and API CSV.

Expected result: a reopened native dashboard with readable history for all six series,
including distinct temperature and humidity presentations. If your account does not
expose historical stream cards, record that feature/access limitation and obtain
appropriate access; do not claim a completeness-only dashboard satisfies this step.

The [UI reference](https://help.autodesk.com/cloudhelp/ENU/Tandem-Getting-Started/files/tandem-navigate-ui.html)
documents dashboard entry points, [Autodesk's dashboard introduction](https://intandem.autodesk.com/resource/introducing-tandems-new-dashboards-beta/)
describes stream cards and operations layouts, and the
[save/reopen tutorial](https://www.autodesk.com/learn/ondemand/tutorial/create-and-manage-views-in-tandem)
explains saved dashboard behavior. Account-specific availability and the exact card
editor controls remain live verification items.
