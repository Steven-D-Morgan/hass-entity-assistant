"""Button platform for Entity Assistant."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_FILENAME, DEFAULT_STALE_FILENAME, DOMAIN
from .export import ExportOptions, async_run_export, remove_orphaned

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([
        EntityExportButton(entry),
        ExportOrphanedButton(entry),
        RemoveOrphanedButton(entry),
    ])


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


class ExportOrphanedButton(ButtonEntity):

    _attr_has_entity_name = True
    _attr_name = "Export orphaned entities"
    _attr_icon = "mdi:file-alert-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_export_orphaned"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Entity Assistant",
            manufacturer="Entity Assistant",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        options = ExportOptions(stale_only=True)
        path, count = await async_run_export(
            self.hass, options, DEFAULT_STALE_FILENAME, triggered_by="button"
        )
        _LOGGER.info("Exported %d stale rows to %s", count, path)


class RemoveOrphanedButton(ButtonEntity):

    _attr_has_entity_name = True
    _attr_name = "Remove orphaned entries"
    _attr_icon = "mdi:trash-can-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_remove_orphaned"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Entity Assistant",
            manufacturer="Entity Assistant",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        result = remove_orphaned(self.hass, triggered_by="button")
        _LOGGER.info(
            "Removed %d entities, %d devices, %d areas",
            result["entities_removed"],
            result["devices_removed"],
            result["areas_removed"],
        )
