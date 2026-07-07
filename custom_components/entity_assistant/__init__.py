"""The Entity Assistant integration.

Exports the Home Assistant device/entity registry (entity_id, area,
device metadata, current state, etc.) to a CSV file via a service call.
"""
from __future__ import annotations

import csv
import io
import logging
import os

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    ATTR_FILENAME,
    ATTR_INCLUDE_DISABLED,
    ATTR_INCLUDE_HIDDEN,
    CSV_COLUMNS,
    DEFAULT_FILENAME,
    DOMAIN,
    SERVICE_EXPORT_CSV,
)

_LOGGER = logging.getLogger(__name__)

EXPORT_CSV_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_FILENAME, default=DEFAULT_FILENAME): cv.string,
        vol.Optional(ATTR_INCLUDE_DISABLED, default=True): cv.boolean,
        vol.Optional(ATTR_INCLUDE_HIDDEN, default=True): cv.boolean,
    }
)


def _resolve_path(hass: HomeAssistant, filename: str) -> str:
    """Resolve a user-supplied filename to a path inside the config dir.

    Guards against path traversal so the export can only be written
    somewhere under the Home Assistant configuration directory.
    """
    config_dir = os.path.realpath(hass.config.config_dir)
    target = os.path.realpath(os.path.join(config_dir, filename))
    if target != config_dir and not target.startswith(config_dir + os.sep):
        raise vol.Invalid(
            f"filename must resolve to a path inside the config directory ({config_dir})"
        )
    return target


def _build_rows(
    hass: HomeAssistant, include_disabled: bool, include_hidden: bool
) -> list[dict[str, str]]:
    """Build one CSV row per entity, enriched with device and area data."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    rows: list[dict[str, str]] = []

    for entity in sorted(ent_reg.entities.values(), key=lambda e: e.entity_id):
        if entity.disabled and not include_disabled:
            continue
        if entity.hidden and not include_hidden:
            continue

        device = dev_reg.async_get(entity.device_id) if entity.device_id else None

        # Entity-level area override falls back to the device's area.
        area_id = entity.area_id or (device.area_id if device else None)
        area = area_reg.async_get_area(area_id) if area_id else None

        state = hass.states.get(entity.entity_id)
        state_value = state.state if state else ""
        unit = ""
        device_class = entity.device_class or entity.original_device_class or ""
        if state:
            unit = state.attributes.get("unit_of_measurement", "") or ""
            if not device_class:
                device_class = state.attributes.get("device_class", "") or ""

        rows.append(
            {
                "entity_id": entity.entity_id,
                "name": entity.name or entity.original_name or "",
                "original_name": entity.original_name or "",
                "platform": entity.platform or "",
                "device_id": entity.device_id or "",
                "device_name": (device.name_by_user or device.name) if device else "",
                "device_manufacturer": device.manufacturer if device else "",
                "device_model": device.model if device else "",
                "area_id": area_id or "",
                "area_name": area.name if area else "",
                "entity_category": entity.entity_category or "",
                "device_class": device_class,
                "unit_of_measurement": unit,
                "state": state_value,
                "enabled": "false" if entity.disabled else "true",
                "disabled_by": entity.disabled_by or "",
                "hidden_by": entity.hidden_by or "",
                "unique_id": entity.unique_id or "",
            }
        )

    return rows


def _write_csv(path: str, rows: list[dict[str, str]]) -> None:
    """Write rows to disk (runs in the executor — blocking IO)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write(buffer.getvalue())


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Entity Assistant from a config entry and register its service."""

    async def handle_export_csv(call: ServiceCall) -> ServiceResponse:
        filename = call.data[ATTR_FILENAME]
        include_disabled = call.data[ATTR_INCLUDE_DISABLED]
        include_hidden = call.data[ATTR_INCLUDE_HIDDEN]

        path = _resolve_path(hass, filename)
        rows = _build_rows(hass, include_disabled, include_hidden)
        await hass.async_add_executor_job(_write_csv, path, rows)

        _LOGGER.info("Exported %d entities to %s", len(rows), path)

        return {"path": path, "entity_count": len(rows)}

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_CSV,
        handle_export_csv,
        schema=EXPORT_CSV_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry and remove the service."""
    hass.services.async_remove(DOMAIN, SERVICE_EXPORT_CSV)
    return True
