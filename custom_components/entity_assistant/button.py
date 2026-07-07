"""Button platform for Entity Assistant.

Adds an "Export entity list" button so the export can be triggered from the
integration's device page, a dashboard, or an automation.
"""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_FILENAME, DOMAIN
from .export import ExportOptions, async_run_export

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the export button from a config entry."""
    async_add_entities([EntityExportButton(entry)])


class EntityExportButton(ButtonEntity):
    """Button that exports the entity list to the default CSV file."""

    _attr_has_entity_name = True
    _attr_name = "Export entity list"
    _attr_icon = "mdi:file-delimited-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the button and attach it to the integration device."""
        self._attr_unique_id = f"{entry.entry_id}_export_csv"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Entity Assistant",
            manufacturer="Entity Assistant",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Handle the button press: write the default entity CSV export."""
        path, count = await async_run_export(
            self.hass, ExportOptions(), DEFAULT_FILENAME, triggered_by="button"
        )
        _LOGGER.info("Exported %d rows to %s", count, path)
