"""Sensor platform for Entity Assistant.

Exposes a "Last export" timestamp sensor that updates whenever an export
completes (via the button, service, or HTTP endpoint's write path).
"""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_EXPORT_COMPLETED

_RESTORED_ATTRS = ("row_count", "path", "export_type", "triggered_by")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the last-export sensor from a config entry."""
    async_add_entities([LastExportSensor(entry)])


class LastExportSensor(SensorEntity, RestoreEntity):
    """Timestamp of the most recent export, with details as attributes."""

    _attr_has_entity_name = True
    _attr_name = "Last export"
    _attr_icon = "mdi:history"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor and attach it to the integration device."""
        self._attr_unique_id = f"{entry.entry_id}_last_export"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Entity Assistant",
            manufacturer="Entity Assistant",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_native_value: datetime | None = None
        self._attr_extra_state_attributes: dict[str, str | int | None] = {}

    async def async_added_to_hass(self) -> None:
        """Restore the last value and subscribe to export events."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = dt_util.parse_datetime(last_state.state)
            self._attr_extra_state_attributes = {
                attr: last_state.attributes.get(attr) for attr in _RESTORED_ATTRS
            }

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_EXPORT_COMPLETED, self._handle_export)
        )

    @callback
    def _handle_export(self, event: Event) -> None:
        """Update state when an export completes."""
        self._attr_native_value = event.time_fired
        self._attr_extra_state_attributes = {
            "row_count": event.data.get("row_count"),
            "path": event.data.get("path"),
            "export_type": event.data.get("export_type"),
            "triggered_by": event.data.get("triggered_by"),
        }
        self.async_write_ha_state()
