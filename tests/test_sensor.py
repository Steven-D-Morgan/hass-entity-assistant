from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.entity_assistant.const import (
    EVENT_EXPORT_COMPLETED,
    EVENT_EXPORT_FAILED,
)


async def test_sensor_present_after_setup(
    hass: HomeAssistant, setup_integration
) -> None:
    state = hass.states.get("sensor.entity_assistant_last_export")
    assert state is not None


async def test_sensor_updates_on_export_completed(
    hass: HomeAssistant, setup_integration
) -> None:
    hass.bus.async_fire(
        EVENT_EXPORT_COMPLETED,
        {
            "path": "/config/entity_export.csv",
            "row_count": 42,
            "export_type": "entities",
            "triggered_by": "service",
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.entity_assistant_last_export")
    assert state.state not in ("unknown", "unavailable")
    assert state.attributes["row_count"] == 42
    assert state.attributes["path"] == "/config/entity_export.csv"
    assert state.attributes["export_type"] == "entities"
    assert state.attributes["triggered_by"] == "service"


async def test_sensor_updates_on_export_failed(
    hass: HomeAssistant, setup_integration
) -> None:
    hass.bus.async_fire(
        EVENT_EXPORT_FAILED,
        {
            "path": "/config/entity_export.csv",
            "error": "disk full",
            "error_type": "OSError",
            "export_type": "entities",
            "triggered_by": "button",
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.entity_assistant_last_export")
    assert state.attributes["last_error"] == "disk full"
    assert state.attributes["last_error_type"] == "OSError"
    assert state.attributes["last_error_triggered_by"] == "button"
