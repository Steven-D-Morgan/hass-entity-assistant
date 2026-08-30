"""Button platform for Entity Assistant."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_FILENAME, DOMAIN
from .export import ExportOptions, async_run_export

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([EntityExportButton(entry)])


class EntityExportButton(ButtonEntity):

    _attr_has_entity_name = True
    _attr_name = "Export entity list"
    _attr_icon = "mdi:file-delimited-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_export_csv"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Entity Assistant",
            manufacturer="Entity Assistant",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        path, count = await async_run_export(
            self.hass, ExportOptions(), DEFAULT_FILENAME, triggered_by="button"
        )
        _LOGGER.info("Exported %d rows to %s", count, path)
