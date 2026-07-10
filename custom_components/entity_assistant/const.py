"""Constants for the Entity Assistant integration."""

from homeassistant.const import Platform

DOMAIN = "entity_assistant"

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]

# Services
SERVICE_EXPORT_CSV = "export_csv"
SERVICE_GET_DOWNLOAD_URL = "get_download_url"

# Service / option attributes
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

DEFAULT_FILENAME = "entity_export.csv"
DEFAULT_EXPIRES = 300
DEFAULT_STALE_DAYS = 30

# Export modes
EXPORT_TYPE_ENTITIES = "entities"
EXPORT_TYPE_DEVICES = "devices"
EXPORT_TYPE_AREAS = "areas"
EXPORT_TYPES = [EXPORT_TYPE_ENTITIES, EXPORT_TYPE_DEVICES, EXPORT_TYPE_AREAS]
DEFAULT_EXPORT_TYPE = EXPORT_TYPE_ENTITIES

# Event fired after every export
EVENT_EXPORT_COMPLETED = "entity_assistant_export_completed"

# HTTP download endpoint
DOWNLOAD_URL = "/api/entity_assistant/export.csv"
DOWNLOAD_FILENAME = "entity_export.csv"

# CSV columns per export type
ENTITY_COLUMNS = [
    "entity_id",
    "name",
    "original_name",
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

COLUMNS_BY_TYPE = {
    EXPORT_TYPE_ENTITIES: ENTITY_COLUMNS,
    EXPORT_TYPE_DEVICES: DEVICE_COLUMNS,
    EXPORT_TYPE_AREAS: AREA_COLUMNS,
}
