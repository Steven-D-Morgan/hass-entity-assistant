"""The Entity Assistant integration.

Exports the Home Assistant device/entity registry (entity_id, area,
device metadata, current state, etc.) to CSV — via a service call, an
"Export entity list" button, or an authenticated HTTP download endpoint.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_FILENAME,
    ATTR_INCLUDE_DISABLED,
    ATTR_INCLUDE_HIDDEN,
    DEFAULT_FILENAME,
    DOMAIN,
    PLATFORMS,
    SERVICE_EXPORT_CSV,
)
from .export import build_rows, resolve_path, write_csv
from .http import EntityExportView

_LOGGER = logging.getLogger(__name__)

_VIEW_REGISTERED = f"{DOMAIN}_view_registered"

EXPORT_CSV_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_FILENAME, default=DEFAULT_FILENAME): cv.string,
        vol.Optional(ATTR_INCLUDE_DISABLED, default=True): cv.boolean,
        vol.Optional(ATTR_INCLUDE_HIDDEN, default=True): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Entity Assistant from a config entry."""

    async def handle_export_csv(call: ServiceCall) -> ServiceResponse:
        filename = call.data[ATTR_FILENAME]
        include_disabled = call.data[ATTR_INCLUDE_DISABLED]
        include_hidden = call.data[ATTR_INCLUDE_HIDDEN]

        path = resolve_path(hass, filename)
        rows = build_rows(hass, include_disabled, include_hidden)
        await hass.async_add_executor_job(write_csv, path, rows)

        _LOGGER.info("Exported %d entities to %s", len(rows), path)

        return {"path": path, "entity_count": len(rows)}

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_CSV,
        handle_export_csv,
        schema=EXPORT_CSV_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    # HTTP views cannot be unregistered, so register the download view only once.
    if not hass.data.get(_VIEW_REGISTERED):
        hass.http.register_view(EntityExportView(hass))
        hass.data[_VIEW_REGISTERED] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry, its platforms, and the service."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.services.async_remove(DOMAIN, SERVICE_EXPORT_CSV)
    return unload_ok
