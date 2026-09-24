"""Constants for the Entity Assistant integration."""

from homeassistant.const import Platform

DOMAIN = "entity_assistant"

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]

SERVICE_EXPORT_CSV = "export_csv"
SERVICE_GET_DOWNLOAD_URL = "get_download_url"
SERVICE_REMOVE_ORPHANED = "remove_orphaned"

ATTR_FILENAME = "filename"
ATTR_INCLUDE_DISABLED = "include_disabled"
ATTR_INCLUDE_HIDDEN = "include_hidden"
ATTR_ONLY_ENABLED = "only_enabled"
ATTR_EXPORT_TYPE = "export_type"
ATTR_DOMAINS = "domains"
ATTR_AREAS = "areas"
ATTR_EXPIRES = "expires"
ATTR_STALE_ONLY = "stale_only"
ATTR_STALE_DAYS = "stale_days"
ATTR_UTF8_BOM = "utf8_bom"
ATTR_OUTPUT_FORMAT = "output_format"
ATTR_SORT_BY = "sort_by"
ATTR_SORT_DIR = "sort_dir"
ATTR_DRY_RUN = "dry_run"
ATTR_CONFIRM = "confirm"

DEFAULT_FILENAME = "entity_export.csv"
DEFAULT_STALE_FILENAME = "entity_export_stale.csv"
DEFAULT_EXPIRES = 120
DEFAULT_STALE_DAYS = 30

EXPORT_TYPE_ENTITIES = "entities"
EXPORT_TYPE_DEVICES = "devices"
EXPORT_TYPE_AREAS = "areas"
EXPORT_TYPE_FLOORS = "floors"
EXPORT_TYPE_LABELS = "labels"
EXPORT_TYPES = [
    EXPORT_TYPE_ENTITIES,
    EXPORT_TYPE_DEVICES,
    EXPORT_TYPE_AREAS,
    EXPORT_TYPE_FLOORS,
    EXPORT_TYPE_LABELS,
]
DEFAULT_EXPORT_TYPE = EXPORT_TYPE_ENTITIES

OUTPUT_FORMAT_CSV = "csv"
OUTPUT_FORMAT_JSON = "json"
OUTPUT_FORMAT_YAML = "yaml"
OUTPUT_FORMATS = [OUTPUT_FORMAT_CSV, OUTPUT_FORMAT_JSON, OUTPUT_FORMAT_YAML]
DEFAULT_OUTPUT_FORMAT = OUTPUT_FORMAT_CSV

OUTPUT_FORMAT_CONTENT_TYPES = {
    OUTPUT_FORMAT_CSV: "text/csv",
    OUTPUT_FORMAT_JSON: "application/json",
    OUTPUT_FORMAT_YAML: "application/yaml",
}

SORT_DIR_ASC = "asc"
SORT_DIR_DESC = "desc"
SORT_DIRS = [SORT_DIR_ASC, SORT_DIR_DESC]
DEFAULT_SORT_DIR = SORT_DIR_ASC

EVENT_EXPORT_COMPLETED = "entity_assistant_export_completed"
EVENT_EXPORT_FAILED = "entity_assistant_export_failed"
EVENT_ORPHANED_REMOVED = "entity_assistant_orphaned_removed"

DOWNLOAD_URL = "/api/entity_assistant/export.csv"
DOWNLOAD_FILENAME_BASE = "entity_export"
DOWNLOAD_FILENAME = "entity_export.csv"

ENTITY_COLUMNS = [
    "entity_id",
    "registry_id",
    "name",
    "original_name",
    "icon",
    "platform",
    "config_entry",
    "device_id",
    "device_name",
    "device_manufacturer",
    "device_model",
    "area_id",
    "area_name",
    "floor",
    "labels",
    "aliases",
    "categories",
    "entity_category",
    "device_class",
    "unit_of_measurement",
    "state",
    "available",
    "last_changed",
    "last_changed_days",
    "stale",
    "stale_reason",
    "enabled",
    "disabled_by",
    "hidden_by",
    "unique_id",
]

DEVICE_COLUMNS = [
    "device_id",
    "name",
    "name_by_user",
    "manufacturer",
    "model",
    "sw_version",
    "hw_version",
    "area_id",
    "area_name",
    "floor",
    "labels",
    "config_entries",
    "via_device_id",
    "entity_count",
    "available_entity_count",
    "disabled_by",
    "stale",
    "stale_reason",
]

AREA_COLUMNS = [
    "area_id",
    "name",
    "icon",
    "floor_id",
    "floor",
    "labels",
    "aliases",
    "device_count",
    "entity_count",
    "picture",
    "stale",
    "stale_reason",
]

FLOOR_COLUMNS = [
    "floor_id",
    "name",
    "level",
    "icon",
    "aliases",
    "area_count",
]

LABEL_COLUMNS = [
    "label_id",
    "name",
    "color",
    "icon",
    "description",
    "entity_count",
    "device_count",
    "area_count",
]

COLUMNS_BY_TYPE = {
    EXPORT_TYPE_ENTITIES: ENTITY_COLUMNS,
    EXPORT_TYPE_DEVICES: DEVICE_COLUMNS,
    EXPORT_TYPE_AREAS: AREA_COLUMNS,
    EXPORT_TYPE_FLOORS: FLOOR_COLUMNS,
    EXPORT_TYPE_LABELS: LABEL_COLUMNS,
}
