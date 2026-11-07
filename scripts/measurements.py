"""CSV equipment -> exact sensor label -> outgoing flat JSON field.

Adapt this table with docs/ADAPTING.md for other equipment. Tandem display names
are independent: private readback config maps these fields to discovered IDs.
Units belong to the dataset and saved Tandem mappings, not to this lookup table.
"""

FIELDS = {
    "ahu-01": {
        "Chilled Water Temperature": "chilled_water_temperature",
        "Heat Pipe Leaving Tempera": "heat_pipe_leaving_temperature",
        "Outside Air Humidity": "outside_air_humidity",
    },
    "vav-3": {
        "Discharge Air Temperature": "discharge_air_temperature",
        "Zone Humidity": "zone_humidity",
        "Zone Temperature": "zone_temperature",
    },
}
