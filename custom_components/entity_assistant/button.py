"""Button platform for Entity Assistant."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_EXPORT_TYPE,
    ATTR_FILENAME,
    ATTR_INCLUDE_DISABLED,
    ATTR_INCLUDE_HIDDEN,
    ATTR_ONLY_ENABLED,
    ATTR_OUTPUT_FORMAT,
    ATTR_STALE_DAYS,
    ATTR_STALE_ONLY,
    ATTR_UTF8_BOM,
    DEFAULT_EXPORT_TYPE,
    DEFAULT_FILENAME,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_STALE_DAYS,
    DEFAULT_STALE_FILENAME,
    DOMAIN,
)
from .export import ExportOptions, async_run_export

_LOGGER = logging.getLogger(__name__)


def _options_from_entry(entry: ConfigEntry) -> tuple[ExportOptions, str]:
    opts = entry.options
    options = ExportOptions(
        export_type=opts.get(ATTR_EXPORT_TYPE, DEFAULT_EXPORT_TYPE),
        include_disabled=opts.get(ATTR_INCLUDE_DISABLED, True),
        include_hidden=opts.get(ATTR_INCLUDE_HIDDEN, True),
        only_enabled=opts.get(ATTR_ONLY_ENABLED, False),
        stale_only=opts.get(ATTR_STALE_ONLY, False),
        stale_days=opts.get(ATTR_STALE_DAYS, DEFAULT_STALE_DAYS),
        utf8_bom=opts.get(ATTR_UTF8_BOM, False),
        output_format=opts.get(ATTR_OUTPUT_FORMAT, DEFAULT_OUTPUT_FORMAT),
    )
    filename: str = opts.get(ATTR_FILENAME, DEFAULT_FILENAME)
    return options, filename


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            EntityExportButton(entry),
            ExportOrphanedButton(entry),
        ]
    )


class EntityExportButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Export entity list"
    _attr_icon = "mdi:file-delimited-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_export_csv"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Entity Assistant",
            manufacturer="Entity Assistant",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        options, filename = _options_from_entry(self._entry)
        try:
            path, count = await async_run_export(
                self.hass, options, filename, triggered_by="button"
            )
        except Exception:
            return
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
        try:
            path, count = await async_run_export(
                self.hass, options, DEFAULT_STALE_FILENAME, triggered_by="button"
            )
        except Exception:
            return
        _LOGGER.info("Exported %d stale rows to %s", count, path)
