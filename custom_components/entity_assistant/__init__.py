"""The Entity Assistant integration.

Exports the Home Assistant registries (entities, devices, or areas) to CSV —
via a service, an "Export entity list" button, or an authenticated HTTP
download endpoint (with a signed-URL helper). Fires an event on completion and
tracks the last export in a sensor.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from urllib.parse import urlencode

import voluptuous as vol

from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    ATTR_AREAS,
    ATTR_DOMAINS,
    ATTR_EXPIRES,
    ATTR_EXPORT_TYPE,
    ATTR_FILENAME,
    ATTR_INCLUDE_DISABLED,
    ATTR_INCLUDE_HIDDEN,
    ATTR_ONLY_ENABLED,
    ATTR_STALE_DAYS,
    ATTR_STALE_ONLY,
    DEFAULT_EXPIRES,
    DEFAULT_EXPORT_TYPE,
    DEFAULT_FILENAME,
    DEFAULT_STALE_DAYS,
    DOMAIN,
    DOWNLOAD_URL,
    EXPORT_TYPES,
    PLATFORMS,
    SERVICE_EXPORT_CSV,
    SERVICE_GET_DOWNLOAD_URL,
)
from .export import ExportOptions, async_run_export
from .http import EntityExportView

_LOGGER = logging.getLogger(__name__)

_VIEW_REGISTERED = f"{DOMAIN}_view_registered"

# Shared option fields for both services.
_OPTION_FIELDS = {
    vol.Optional(ATTR_EXPORT_TYPE, default=DEFAULT_EXPORT_TYPE): vol.In(EXPORT_TYPES),
    vol.Optional(ATTR_INCLUDE_DISABLED, default=True): cv.boolean,
    vol.Optional(ATTR_INCLUDE_HIDDEN, default=True): cv.boolean,
    vol.Optional(ATTR_ONLY_ENABLED, default=False): cv.boolean,
    vol.Optional(ATTR_DOMAINS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_AREAS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_STALE_ONLY, default=False): cv.boolean,
    vol.Optional(ATTR_STALE_DAYS, default=DEFAULT_STALE_DAYS): cv.positive_int,
}

EXPORT_CSV_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_FILENAME, default=DEFAULT_FILENAME): cv.string, **_OPTION_FIELDS}
)

GET_DOWNLOAD_URL_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_EXPIRES, default=DEFAULT_EXPIRES): cv.positive_int, **_OPTION_FIELDS}
)


def _options_from_call(call: ServiceCall) -> ExportOptions:
    """Build ExportOptions from a service call's data."""
    domains = call.data.get(ATTR_DOMAINS)
    areas = call.data.get(ATTR_AREAS)
    return ExportOptions(
        export_type=call.data[ATTR_EXPORT_TYPE],
        include_disabled=call.data[ATTR_INCLUDE_DISABLED],
        include_hidden=call.data[ATTR_INCLUDE_HIDDEN],
        only_enabled=call.data[ATTR_ONLY_ENABLED],
        domains=frozenset(domains) if domains else None,
        areas=frozenset(areas) if areas else None,
        stale_only=call.data[ATTR_STALE_ONLY],
        stale_days=call.data[ATTR_STALE_DAYS],
    )


def _options_to_query(options: ExportOptions) -> dict[str, str]:
    """Serialize options to download-URL query parameters."""
    query = {
        "export_type": options.export_type,
        "include_disabled": str(options.include_disabled).lower(),
        "include_hidden": str(options.include_hidden).lower(),
        "only_enabled": str(options.only_enabled).lower(),
        "stale_only": str(options.stale_only).lower(),
        "stale_days": str(options.stale_days),
    }
    if options.domains:
        query["domains"] = ",".join(sorted(options.domains))
    if options.areas:
        query["areas"] = ",".join(sorted(options.areas))
    return query


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Entity Assistant from a config entry."""

    async def handle_export_csv(call: ServiceCall) -> ServiceResponse:
        options = _options_from_call(call)
        path, count = await async_run_export(
            hass, options, call.data[ATTR_FILENAME], triggered_by="service"
        )
        return {"path": path, "row_count": count}

    @callback
    def handle_get_download_url(call: ServiceCall) -> ServiceResponse:
        options = _options_from_call(call)
        expires = call.data[ATTR_EXPIRES]

        query = urlencode(_options_to_query(options))
        path = f"{DOWNLOAD_URL}?{query}"
        signed = async_sign_path(hass, path, timedelta(seconds=expires))

        try:
            url = f"{get_url(hass, prefer_external=True)}{signed}"
        except NoURLAvailableError:
            url = signed

        return {"url": url, "expires_in": expires}

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_CSV,
        handle_export_csv,
        schema=EXPORT_CSV_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DOWNLOAD_URL,
        handle_get_download_url,
        schema=GET_DOWNLOAD_URL_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    # HTTP views cannot be unregistered, so register the download view only once.
    if not hass.data.get(_VIEW_REGISTERED):
        hass.http.register_view(EntityExportView(hass))
        hass.data[_VIEW_REGISTERED] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry, its platforms, and the services."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.services.async_remove(DOMAIN, SERVICE_EXPORT_CSV)
        hass.services.async_remove(DOMAIN, SERVICE_GET_DOWNLOAD_URL)
    return unload_ok
