from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.entity_assistant.const import (
    DOMAIN,
    EVENT_CHANGES_APPLIED,
    EVENT_ORPHANED_REMOVED,
    SERVICE_REMOVE_ORPHANED,
)


def _seed_orphans(hass: HomeAssistant) -> dict:
    integration = MockConfigEntry(domain="orphan_test", title="Orphan")
    integration.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={("orphan_test", "d1")},
        name="Orphan Device",
    )
    entity = ent_reg.async_get_or_create(
        "sensor",
        "orphan_test",
        "orphan_1",
        config_entry=integration,
        original_name="Orphan Sensor",
    )
    hass.config_entries._entries.pop(integration.entry_id, None)
    return {"entity_id": entity.entity_id, "device_id": device.id}


async def test_dry_run_default_returns_preview(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_orphans(hass)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    assert response["dry_run"] is True
    assert seed["entity_id"] in response["entity_ids"]
    assert seed["device_id"] in response["device_ids"]

    ent_reg = er.async_get(hass)
    assert ent_reg.async_get(seed["entity_id"]) is not None


async def test_dry_run_explicit_true(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_orphans(hass)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {"dry_run": True},
        blocking=True,
        return_response=True,
    )
    assert response["dry_run"] is True
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get(seed["entity_id"]) is not None


async def test_confirm_true_removes_entries(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_orphans(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {"dry_run": False, "confirm": True},
        blocking=True,
        return_response=True,
    )
    assert response["dry_run"] is False
    assert seed["entity_id"] in response["entity_ids"]
    assert ent_reg.async_get(seed["entity_id"]) is None
    assert dev_reg.async_get(seed["device_id"]) is None


async def test_confirm_alone_applies(hass: HomeAssistant, setup_integration) -> None:
    seed = _seed_orphans(hass)
    ent_reg = er.async_get(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {"confirm": True},
        blocking=True,
        return_response=True,
    )
    assert ent_reg.async_get(seed["entity_id"]) is None


async def test_dry_run_does_not_fire_event(hass: HomeAssistant, setup_integration) -> None:
    _seed_orphans(hass)
    events = []
    hass.bus.async_listen(EVENT_ORPHANED_REMOVED, events.append)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert events == []


async def test_confirm_fires_event(hass: HomeAssistant, setup_integration) -> None:
    _seed_orphans(hass)
    events = []
    hass.bus.async_listen(EVENT_ORPHANED_REMOVED, events.append)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {"confirm": True},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_non_admin_user_rejected(hass: HomeAssistant, setup_integration) -> None:
    _seed_orphans(hass)

    mock_user = MagicMock()
    mock_user.is_admin = False
    hass.auth.async_get_user = AsyncMock(return_value=mock_user)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_ORPHANED,
            {"confirm": True},
            context=Context(user_id="non_admin_id"),
            blocking=True,
            return_response=True,
        )


async def test_admin_user_allowed(hass: HomeAssistant, setup_integration) -> None:
    _seed_orphans(hass)

    mock_user = MagicMock()
    mock_user.is_admin = True
    hass.auth.async_get_user = AsyncMock(return_value=mock_user)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {"confirm": True},
        context=Context(user_id="admin_id"),
        blocking=True,
        return_response=True,
    )
    assert response is not None


async def test_missing_user_rejected(hass: HomeAssistant, setup_integration) -> None:
    _seed_orphans(hass)

    hass.auth.async_get_user = AsyncMock(return_value=None)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_ORPHANED,
            {"confirm": True},
            context=Context(user_id="ghost_id"),
            blocking=True,
            return_response=True,
        )


async def test_system_call_no_user_allowed(hass: HomeAssistant, setup_integration) -> None:
    _seed_orphans(hass)
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {"confirm": True},
        blocking=True,
        return_response=True,
    )
    assert response is not None


async def test_empty_registries_zero_counts(hass: HomeAssistant, setup_integration) -> None:
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {},
        blocking=True,
        return_response=True,
    )
    assert response["entities_removed"] == 0
    assert response["devices_removed"] == 0
    assert response["areas_removed"] == 0


async def test_cascading_area_cleanup(hass: HomeAssistant, setup_integration) -> None:
    area_reg = ar.async_get(hass)
    orphan_only_area = area_reg.async_create("Orphan Only Room")

    integration = MockConfigEntry(domain="cascade_test", title="Cascade")
    integration.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={("cascade_test", "d1")},
        name="Cascade Device",
    )
    dev_reg.async_update_device(device.id, area_id=orphan_only_area.id)
    ent_reg.async_get_or_create(
        "sensor",
        "cascade_test",
        "cascade_1",
        config_entry=integration,
        device_id=device.id,
        original_name="Cascade Sensor",
    )
    hass.config_entries._entries.pop(integration.entry_id, None)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {"confirm": True},
        blocking=True,
        return_response=True,
    )
    assert orphan_only_area.id in response["area_ids"]
    assert area_reg.async_get_area(orphan_only_area.id) is None


async def test_confirm_fires_both_events(hass: HomeAssistant, setup_integration) -> None:
    _seed_orphans(hass)
    orphaned_events = []
    applied_events = []
    hass.bus.async_listen(EVENT_ORPHANED_REMOVED, orphaned_events.append)
    hass.bus.async_listen(EVENT_CHANGES_APPLIED, applied_events.append)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        {"confirm": True},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert len(orphaned_events) == 1
    assert len(applied_events) == 1
    assert applied_events[0].data["producer"] == "remove_orphaned"
