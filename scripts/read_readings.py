"""Discover Tandem IDs or export actual API history for every configured series.

Learner configuration lives in root .env and private config/readback.json. CSV
sensor labels and payload fields come from measurements.py; returned names/units
come from the facility schema. This reader never uses the source CSV or send log.
"""

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

from measurements import FIELDS
from tandem_api import ApiError, TandemReader, full_key

ROOT = Path(__file__).resolve().parents[1]
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
COLUMNS = ["timestamp_utc", "timestamp_epoch_ms", "equipment_id", "connection_key",
           "field", "parameter_id", "parameter_name", "value", "unit"]


def utc_bound(text):
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Use an ISO 8601 query bound with a timezone.") from None
    if stamp.tzinfo is None or stamp.utcoffset() is None or stamp.microsecond % 1000:
        raise ValueError("Bounds require a timezone and at most millisecond precision.")
    delta = stamp.astimezone(timezone.utc) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def utc_text(stamp):
    from datetime import timedelta
    return (EPOCH + timedelta(milliseconds=stamp)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def load_config(path):
    with path.open(encoding="utf-8-sig") as source:
        config = json.load(source)
    if (not isinstance(config, dict) or not isinstance(config.get("connections"), dict)
            or set(config["connections"]) != set(FIELDS)):
        raise ValueError("Readback config must contain every equipment ID from measurements.py.")
    seen = set()
    for equipment, fields in FIELDS.items():
        item = config["connections"][equipment]
        if (not isinstance(item, dict) or not isinstance(item.get("parameters"), dict)
                or set(item["parameters"]) != set(fields.values())):
            raise ValueError("Readback config must map every payload field to a qualified parameter ID.")
        key = full_key(item.get("connection_key"))
        if key in seen:
            raise ValueError("Each equipment item needs a distinct connection.")
        seen.add(key)
        item["connection_key"] = key
        params = list(item["parameters"].values())
        if any(not isinstance(p, str) or ":" not in p for p in params) or len(set(params)) != len(params):
            raise ValueError("Use distinct qualified parameter IDs on each connection.")
    return config


def discovery_facility(path):
    """Allow discovery with only facility_urn filled; IDs are discovered afterwards."""
    with path.open(encoding="utf-8-sig") as source:
        config = json.load(source)
    facility = config.get("facility_urn") if isinstance(config, dict) else None
    if not isinstance(facility, str) or not facility.startswith("urn:adsk.dtt:"):
        raise ValueError("Fill facility_urn in private readback config, or pass --facility-urn.")
    return facility


def collect(reader, config, start, end, page_size=1000):
    """Validate saved field-to-ID mappings, then read each series with API metadata."""
    discovery = reader.discover(config.get("facility_urn"))
    connections = {c["connection_key"]: c for c in discovery["connections"]}
    # Validate all IDs/mappings before making any history requests.
    for item in config["connections"].values():
        connection = connections.get(item["connection_key"])
        if connection is None:
            raise ValueError("Configured connection was not found in this facility.")
        mapped = {p["parameter_id"]: p.get("source_field") for p in connection["parameters"]}
        if not set(item["parameters"].values()).issubset(mapped):
            raise ValueError("A configured parameter is not mapped on its connection. Run discovery again.")
        if any(mapped[pid] != field for field, pid in item["parameters"].items()):
            raise ValueError("A parameter maps to a different or unsupported source field. Check discovery and saved mappings.")
        if not set(item["parameters"].values()).issubset(discovery["attributes"]):
            raise ValueError("A configured parameter is absent from the model schema.")
    rows, counts = [], {}
    for equipment, item in config["connections"].items():
        for field, parameter in item["parameters"].items():
            prop = discovery["attributes"][parameter]
            values = reader.history(discovery["model_urn"], item["connection_key"], parameter,
                                    start, end, page_size)
            counts[f"{equipment}/{field}"] = len(values)
            for stamp, value in values:
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                    raise ApiError("Expected numeric API readings; export stopped without manufacturing values.")
                rows.append(dict(zip(COLUMNS, [utc_text(stamp), stamp, equipment, item["connection_key"],
                            field, parameter, prop.get("name", ""), value, prop.get("forgeUnit", "") or ""])))
    rows.sort(key=lambda row: (row["timestamp_epoch_ms"], row["equipment_id"], row["field"]))
    summary = {"source": "Autodesk Tandem API", "facility_urn": discovery["facility_urn"],
               "model_urn": discovery["model_urn"], "from_utc_inclusive": utc_text(start),
               "to_utc_exclusive": utc_text(end), "exported_at_utc": datetime.now(timezone.utc).isoformat(),
                "counts": counts, "total_measurements": len(rows),
                "page_size": page_size, "history_query_windows": "UTC calendar days",
               "empty_series": [name for name, count in counts.items() if count == 0]}
    return rows, summary


def write_export(path, rows, summary):
    """Write both artifacts exclusively; remove this call's files on failure.

    A two-file transaction cannot be atomic across process termination. A usable
    export requires both the CSV and adjacent summary with matching counts.
    Exclusive creation protects existing files, including a competing export.
    """
    summary_path = path.with_suffix(path.suffix + ".summary.json")
    if path.exists() or summary_path.exists():
        raise ValueError("Output already exists; choose a fresh --output path.")
    path.parent.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        # Serialize metadata first so a nonserializable summary creates no CSV.
        metadata = json.dumps(summary, indent=2, allow_nan=False)
        with summary_path.open("x", encoding="utf-8") as target:
            created.append(summary_path)
            target.write(metadata)
        with path.open("x", newline="", encoding="utf-8") as target:
            created.append(path)
            writer = csv.DictWriter(target, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    except BaseException:
        for created_path in reversed(created):
            created_path.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true", help="List connections and mapped parameter IDs; no history query")
    parser.add_argument("--facility-urn", help="Discovery facility URN; defaults to facility_urn in --config")
    parser.add_argument("--config", type=Path, default=ROOT / "config/readback.json")
    parser.add_argument("--from-utc", help="Inclusive ISO 8601 bound with timezone")
    parser.add_argument("--to-utc", help="Exclusive ISO 8601 bound with timezone")
    parser.add_argument("--page-size", type=int, default=1000, help="2..1000; short pages are also followed")
    parser.add_argument("--region", help="Optional Tandem Region header; use your facility's documented region code")
    parser.add_argument("--output", type=Path, help="New output path; never overwrites an earlier export")
    args = parser.parse_args(argv)
    if not 2 <= args.page_size <= 1000:
        parser.error("page-size must be 2..1000")
    if args.discover:
        if not args.facility_urn:
            args.facility_urn = discovery_facility(args.config)
        output = args.output or ROOT / "outputs/discovery.json"
        config = None
    else:
        if not args.from_utc or not args.to_utc:
            parser.error("Export requires --from-utc and --to-utc")
        start, end = utc_bound(args.from_utc), utc_bound(args.to_utc)
        if start >= end:
            parser.error("from-utc must be earlier than to-utc")
        config = load_config(args.config)
        output = args.output or ROOT / "outputs/readback.csv"
    summary_path = output.with_suffix(output.suffix + ".summary.json")
    if output.exists() or (not args.discover and summary_path.exists()):
        raise ValueError("Output already exists; choose a fresh --output path.")
    reader = TandemReader(region=args.region)
    try:
        if args.discover:
            discovery = reader.discover(args.facility_urn)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8") as target:
                json.dump(discovery, target, indent=2)
            for connection in discovery["connections"]:
                print(connection["name"], connection["connection_key"])
                for prop in connection["parameters"]:
                    field = prop['source_field'] or '(unsupported/unrecognized path)'
                    print(f"  {prop['parameter_id']}: {prop['name']} ({prop['unit']}); source field {field}")
            print(f"Discovery written to {output}. No measurement ingestion performed.")
            return 0
        rows, summary = collect(reader, config, start, end, args.page_size)
        write_export(output, rows, summary)
        for series, count in summary["counts"].items():
            print(f"{series}: {count} stored measurements")
        print(f"Exported {len(rows)} API measurements to {output}")
        if summary["empty_series"]:
            print("Some configured series returned zero points. See summary and troubleshooting.")
            return 3
        return 0
    finally:
        reader.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ApiError, ValueError, OSError) as error:
        # Only the explicit ApiError messages are safe to echo; other exceptions may
        # contain user-supplied JSON or filesystem content.
        print(str(error) if isinstance(error, ApiError) else
              "Check config, IDs, timezone-aware bounds and output paths. See docs/READBACK.md.", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Readback interrupted; no complete export should be assumed.", file=sys.stderr)
        sys.exit(130)
