# Official references and licensing

Inspected Autodesk's [Python REST tutorials](https://github.com/autodesk-tandem/tutorial-rest-python)
at revision `aa7d0738c10407f3cc0064d07f1d2259377f6d1a`, reconfirmed November 7, 2026.
Use the revision links below to distinguish the inspected code from future changes.

| Reference | What was inspected and used as protocol guidance |
|---|---|
| [list-stream-data.py](https://github.com/autodesk-tandem/tutorial-rest-python/blob/aa7d0738c10407f3cc0064d07f1d2259377f6d1a/streams/list-stream-data.py) | Two-legged `data:read`, default model, schema, connection discovery, history response keyed by parameter and epoch milliseconds |
| [export-stream-data.py](https://github.com/autodesk-tandem/tutorial-rest-python/blob/aa7d0738c10407f3cc0064d07f1d2259377f6d1a/streams/export-stream-data.py) | Parameter identification through stream configuration `sourceMapping`, full/short connection keys, queried history and CSV formatting |
| [common/auth.py](https://github.com/autodesk-tandem/tutorial-rest-python/blob/aa7d0738c10407f3cc0064d07f1d2259377f6d1a/common/auth.py) | APS v2 token endpoint, client credentials, Basic authentication, requested scopes |
| [common/tandemClient.py](https://github.com/autodesk-tandem/tutorial-rest-python/blob/aa7d0738c10407f3cc0064d07f1d2259377f6d1a/common/tandemClient.py) | Facility/schema/scan/config/history endpoints, Bearer and optional Region headers; exporter bulk-query helper also inspected |
| [common/utils.py](https://github.com/autodesk-tandem/tutorial-rest-python/blob/aa7d0738c10407f3cc0064d07f1d2259377f6d1a/common/utils.py), [constants.py](https://github.com/autodesk-tandem/tutorial-rest-python/blob/aa7d0738c10407f3cc0064d07f1d2259377f6d1a/common/constants.py), [encoding.py](https://github.com/autodesk-tandem/tutorial-rest-python/blob/aa7d0738c10407f3cc0064d07f1d2259377f6d1a/common/encoding.py) | Default model URN, stream flags and qualified columns, 20-byte short/24-byte full logical keys |
| [Individual ingestion](https://github.com/autodesk-tandem/tutorial-rest-python/blob/aa7d0738c10407f3cc0064d07f1d2259377f6d1a/streams/ingest-data-individual-stream.py) | Individual authenticated ingestion and server time when no timestamp is posted |

The upstream exporter uses pandas, bulk queries and a wide table, grouping returned
timestamps to seconds. This tutorial independently implements a long-form CSV with
the standard library, keeps exact millisecond timestamps, explicitly selects every
configured series, and pages the documented single-series GET endpoint. No upstream
`common` package or implementation files are copied or bundled.

## Project authorship and adaptations

This independent tutorial is authored and maintained by [rgallopp](https://github.com/rgallopp).
The Individual ingestion workflow informs
`scripts/ingest-data-individual-stream-from-csv.py`; CSV grouping, routing, preview,
validation, pacing and sanitized logging are project implementations. The discovery
and export workflows inform `scripts/tandem_api.py` and `scripts/read_readings.py`;
they are independently implemented protocol adaptations, not a vendored Autodesk SDK.
The desktop panel, setup, packaging, tests and fixed-seed data generator are project
support code. No Autodesk or university endorsement is claimed.

The learner configures model access, classifications, parameter specifications/units,
template assignments, hosts/rooms, secret destinations, saved JSON mappings, APS
service access, IDs and query bounds. Example display names are customizable.

## Autodesk product/API guidance

- [Ingestion guidance](https://aps.autodesk.com/blog/adding-iot-sensors-tandem-api):
  numeric payloads, optional timestamps, authentication and one-minute minimum interval.
- [Reading stream data](https://aps.autodesk.com/blog/tandem-data-api-reading-stream-data):
  default model/schema, `from`/`to`, `limit`, `sort=asc`, and `substream`.
- [History endpoint reference](https://aps.autodesk.com/en/docs/tandem/v1/reference/quick_reference/tandem-data-streams-elementID-GET):
  read scope, time bounds, limit and ascending/descending sort. Cross-day empty-page
  and exact-boundary handling are project workarounds established through live checks,
  not behavior guaranteed by the reference examples.
- [Specify overview](https://help.autodesk.com/cloudhelp/ENU/Tandem-Specify/files/tandem-specify.html):
  classifications, parameters, facility templates.
- [Connections and visualization](https://www.autodesk.com/learn/ondemand/curated/tandem-quick-start-guide/3aVQtYTWsDbl9Zimpd5sC2):
  hosts, rooms, Streams Graph and Time Navigation.
- [Usage and asset designation](https://help.autodesk.com/cloudhelp/ENU/Tandem-Manage/files/tandem-usage.html):
  Make Asset, collection frequency/retention, and reserved capacity versus captured points.
- [Stream configuration response](https://aps.autodesk.com/en/docs/tandem/v1/reference/quick_reference/tandem-data-stream-configs-GET):
  parameter IDs and sourceMapping path objects; only known flat fields are exposed by discovery.
- [Facility/model import](https://www.autodesk.com/learn/ondemand/tutorial/create-a-new-facility-and-add-models-in-tandem),
  [thresholds](https://www.autodesk.com/learn/ondemand/tutorial/create-and-set-thresholds), and
  [saved views/dashboards](https://www.autodesk.com/learn/ondemand/tutorial/create-and-manage-views-in-tandem):
  UI workflow references; account-specific controls still require live verification.
- [Dashboard stream cards and layouts](https://intandem.autodesk.com/resource/introducing-tandems-new-dashboards-beta/):
  operations-dashboard capabilities; verify availability in the intended account.
- [Autodesk Tandem team's historical-frequency explanation](https://forums.autodesk.com/t5/tandem-forum/icymi-autodesk-tandem-s-latest-webinar-q-amp-a-amp-dashboard/td-p/13409486):
  one-minute logging. Check actual current collection configuration; do not interpret
  sub-minute successful POSTs as guaranteed additional retained points.

## Applicable licenses

Original project code and documentation are covered by the root [MIT license](../LICENSE).
That grant includes the original reproducible `data/demo_hvac.csv`. It excludes
earlier locally retained data, Autodesk products, building models, upstream examples
and third-party dependencies.

At the inspected upstream revision, GitHub's license metadata is null and no root
LICENSE/ LICENSE.md/ LICENSE.txt file was present. Public visibility is not an
open-source license grant. The upstream examples are cited as API references;
do not copy their implementation into a distribution without establishing applicable
permission. No Autodesk license is invented or applied to this project's code.

Installed dependency metadata identifies these separate licenses. Packages are
installed by pip, not vendored into the source ZIP:

| Dependency | License |
|---|---|
| requests | Apache-2.0 |
| certifi | MPL-2.0 |
| charset-normalizer | MIT |
| idna | BSD-3-Clause |
| urllib3 | MIT |

Python and optional Tcl/Tk are distributed separately under their own licenses.
Retain applicable notices if redistributing dependencies. The public sample is
generated by this project's fixed-seed script; see [data notes](../data/README.md).
No permission is inferred for earlier locally retained files excluded from the archive.
No university or third-party model files are included or licensed by this project.
