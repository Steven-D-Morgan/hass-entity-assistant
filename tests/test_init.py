from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.entity_assistant import async_migrate_entry
from custom_components.entity_assistant.const import (
    DOMAIN,
    SERVICE_EXPORT_CSV,
    SERVICE_GET_DOWNLOAD_URL,
    SERVICE_REMOVE_ORPHANED,
)


async def test_setup_entry_registers_services(hass: HomeAssistant, setup_integration) -> None:
    assert hass.services.has_service(DOMAIN, SERVICE_EXPORT_CSV)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_DOWNLOAD_URL)
    assert hass.services.has_service(DOMAIN, SERVICE_REMOVE_ORPHANED)


async def test_unload_entry_removes_services(hass: HomeAssistant, setup_integration) -> None:
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, SERVICE_EXPORT_CSV)
    assert not hass.services.has_service(DOMAIN, SERVICE_GET_DOWNLOAD_URL)
    assert not hass.services.has_service(DOMAIN, SERVICE_REMOVE_ORPHANED)


async def test_export_csv_service_returns_metadata(hass: HomeAssistant, setup_integration) -> None:
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_EXPORT_CSV,
        {"filename": "test_export.csv"},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    assert "path" in response
    assert "row_count" in response


async def test_export_csv_return_data_returns_rows(hass: HomeAssistant, setup_integration) -> None:
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_EXPORT_CSV,
        {"return_data": True},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    assert "path" not in response
    assert isinstance(response["columns"], list)
    assert "entity_id" in response["columns"]
    assert isinstance(response["rows"], list)
    assert response["truncated"] is False
    assert response["row_count"] == len(response["rows"])


async def test_export_csv_return_data_respects_max_rows(
    hass: HomeAssistant, setup_integration
) -> None:
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_EXPORT_CSV,
        {"return_data": True, "max_rows": 1},
        blocking=True,
        return_response=True,
    )
    assert len(response["rows"]) <= 1
    assert response["truncated"] == (response["row_count"] > 1)


async def test_migrate_entry_current_version(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=1)
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry) is True


async def test_migrate_entry_future_version_rejected(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry) is False


async def test_onboarding_notifies_on_first_setup(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    await async_setup_component(hass, "http", {"http": {}})
    with patch(
        "custom_components.entity_assistant.persistent_notification.async_create"
    ) as mock_notify:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    mock_notify.assert_called_once()
    assert entry.data.get("onboarded") is True


async def test_onboarding_skipped_when_already_onboarded(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"onboarded": True}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    await async_setup_component(hass, "http", {"http": {}})
    with patch(
        "custom_components.entity_assistant.persistent_notification.async_create"
    ) as mock_notify:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    mock_notify.assert_not_called()


async def test_get_download_url_service_returns_url(hass: HomeAssistant, setup_integration) -> None:
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DOWNLOAD_URL,
        {"expires": 60},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    assert "url" in response
    assert response["expires_in"] == 60
    assert "authSig=" in response["url"]
