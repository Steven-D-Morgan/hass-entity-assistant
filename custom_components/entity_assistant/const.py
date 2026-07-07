"""Constants for the Entity Assistant integration."""

DOMAIN = "entity_assistant"

SERVICE_EXPORT_CSV = "export_csv"

ATTR_FILENAME = "filename"
ATTR_INCLUDE_DISABLED = "include_disabled"
ATTR_INCLUDE_HIDDEN = "include_hidden"

DEFAULT_FILENAME = "entity_export.csv"

CSV_COLUMNS = [
    "entity_id",
    "name",
    "original_name",
    "platform",
    "device_id",
    "device_name",
    "device_manufacturer",
    "device_model",
    "area_id",
    "area_name",
    "entity_category",
    "device_class",
    "unit_of_measurement",
    "state",
    "enabled",
    "disabled_by",
    "hidden_by",
    "unique_id",
]
