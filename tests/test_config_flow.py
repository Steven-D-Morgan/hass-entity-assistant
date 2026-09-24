from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.entity_assistant.const import DOMAIN


async def test_user_step_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Entity Assistant"


async def test_single_instance_abort(hass: HomeAssistant) -> None:
    existing = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_stores_defaults(hass: HomeAssistant, setup_integration) -> None:
    result = await hass.config_entries.options.async_init(setup_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "export_type": "devices",
            "filename": "custom.csv",
            "output_format": "json",
            "stale_days": 14,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_integration.options["export_type"] == "devices"
    assert setup_integration.options["filename"] == "custom.csv"
    assert setup_integration.options["output_format"] == "json"
    assert setup_integration.options["stale_days"] == 14
