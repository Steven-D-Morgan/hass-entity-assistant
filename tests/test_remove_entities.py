from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.entity_assistant.const import DOMAIN, SERVICE_REMOVE_ENTITIES


def _loaded_entry(hass: HomeAssistant, domain: str = "demo") -> MockConfigEntry:
    entry = MockConfigEntry(domain=domain, title=domain)
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry


async def test_remove_by_domain_confirm(hass: HomeAssistant, setup_integration) -> None:
    entry = _loaded_entry(hass)
    ent_reg = er.async_get(hass)
    tracker = ent_reg.async_get_or_create(
        "device_tracker", "demo", "beacon_1", config_entry=entry, original_name="Beacon"
    )
    sensor = ent_reg.async_get_or_create(
        "sensor", "demo", "keep_1", config_entry=entry, original_name="Keep"
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ENTITIES,
        {"domains": ["device_tracker"], "confirm": True},
        blocking=True,
        return_response=True,
    )
    assert response["dry_run"] is False
    assert tracker.entity_id in response["removed_keys"]
    assert sensor.entity_id not in response["removed_keys"]
    assert ent_reg.async_get(tracker.entity_id) is None
    assert ent_reg.async_get(sensor.entity_id) is not None


async def test_dry_run_default_removes_nothing(hass: HomeAssistant, setup_integration) -> None:
    entry = _loaded_entry(hass)
    ent_reg = er.async_get(hass)
    tracker = ent_reg.async_get_or_create(
        "device_tracker", "demo", "beacon_1", config_entry=entry, original_name="Beacon"
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ENTITIES,
        {"domains": ["device_tracker"]},
        blocking=True,
        return_response=True,
    )
    assert response["dry_run"] is True
    assert response["counts"]["removed"] == 1
    assert ent_reg.async_get(tracker.entity_id) is not None


async def test_skips_unloaded_config_entry(hass: HomeAssistant, setup_integration) -> None:
    retry = MockConfigEntry(domain="retry", title="Retry")
    retry.add_to_hass(hass)
    retry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    ent_reg = er.async_get(hass)
    offline = ent_reg.async_get_or_create(
        "device_tracker", "retry", "offline_1", config_entry=retry, original_name="Offline"
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ENTITIES,
        {"domains": ["device_tracker"], "confirm": True},
        blocking=True,
        return_response=True,
    )
    assert offline.entity_id not in response["removed_keys"]
    assert ent_reg.async_get(offline.entity_id) is not None


async def test_restored_only_filters_live_entities(hass: HomeAssistant, setup_integration) -> None:
    entry = _loaded_entry(hass)
    ent_reg = er.async_get(hass)
    restored = ent_reg.async_get_or_create(
        "sensor", "demo", "restored_1", config_entry=entry, original_name="Restored"
    )
    live = ent_reg.async_get_or_create(
        "sensor", "demo", "live_1", config_entry=entry, original_name="Live"
    )
    hass.states.async_set(live.entity_id, "42")

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ENTITIES,
        {"restored_only": True, "confirm": True},
        blocking=True,
        return_response=True,
    )
    assert restored.entity_id in response["removed_keys"]
    assert live.entity_id not in response["removed_keys"]
    assert ent_reg.async_get(restored.entity_id) is None
    assert ent_reg.async_get(live.entity_id) is not None


async def test_nothing_selected_removes_nothing(hass: HomeAssistant, setup_integration) -> None:
    entry = _loaded_entry(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "sensor", "demo", "s1", config_entry=entry, original_name="S1"
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ENTITIES,
        {"confirm": True},
        blocking=True,
        return_response=True,
    )
    assert response["counts"]["removed"] == 0


async def test_non_admin_rejected(hass: HomeAssistant, setup_integration) -> None:
    mock_user = MagicMock()
    mock_user.is_admin = False
    hass.auth.async_get_user = AsyncMock(return_value=mock_user)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_ENTITIES,
            {"domains": ["sensor"], "confirm": True},
            context=Context(user_id="non_admin"),
            blocking=True,
            return_response=True,
        )
