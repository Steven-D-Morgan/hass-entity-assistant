from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.entity_assistant.const import (
    DOMAIN,
    SERVICE_EXPORT_CSV,
    SERVICE_GET_DOWNLOAD_URL,
    SERVICE_REMOVE_ORPHANED,
)


async def test_setup_entry_registers_services(
    hass: HomeAssistant, setup_integration
) -> None:
    assert hass.services.has_service(DOMAIN, SERVICE_EXPORT_CSV)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_DOWNLOAD_URL)
    assert hass.services.has_service(DOMAIN, SERVICE_REMOVE_ORPHANED)


async def test_unload_entry_removes_services(
    hass: HomeAssistant, setup_integration
) -> None:
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, SERVICE_EXPORT_CSV)
    assert not hass.services.has_service(DOMAIN, SERVICE_GET_DOWNLOAD_URL)
    assert not hass.services.has_service(DOMAIN, SERVICE_REMOVE_ORPHANED)


async def test_export_csv_service_returns_metadata(
    hass: HomeAssistant, setup_integration
) -> None:
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


async def test_get_download_url_service_returns_url(
    hass: HomeAssistant, setup_integration
) -> None:
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
