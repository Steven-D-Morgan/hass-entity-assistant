from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant


async def test_export_button_press_invokes_run_export(
    hass: HomeAssistant, setup_integration
) -> None:
    entity_id = "button.entity_assistant_export_entity_list"
    assert hass.states.get(entity_id) is not None

    with patch(
        "custom_components.entity_assistant.button.async_run_export",
        AsyncMock(return_value=("/config/entity_export.csv", 5)),
    ) as mock:
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()
    mock.assert_awaited_once()
    call_args = mock.await_args
    options = call_args.args[1]
    assert options.stale_only is False


async def test_orphaned_button_press_uses_stale_only(
    hass: HomeAssistant, setup_integration
) -> None:
    entity_id = "button.entity_assistant_export_orphaned_entities"
    assert hass.states.get(entity_id) is not None

    with patch(
        "custom_components.entity_assistant.button.async_run_export",
        AsyncMock(return_value=("/config/entity_export_stale.csv", 2)),
    ) as mock:
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()
    mock.assert_awaited_once()
    options = mock.await_args.args[1]
    assert options.stale_only is True


async def test_button_press_swallows_export_error(
    hass: HomeAssistant, setup_integration
) -> None:
    entity_id = "button.entity_assistant_export_entity_list"
    with patch(
        "custom_components.entity_assistant.button.async_run_export",
        AsyncMock(side_effect=OSError("disk full")),
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()
