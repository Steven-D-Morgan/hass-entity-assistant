"""The Entity Assistant integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from urllib.parse import urlencode

from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    Context,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url
import voluptuous as vol

from .const import (
    ATTR_AREAS,
    ATTR_CONFIRM,
    ATTR_DOMAINS,
    ATTR_DRY_RUN,
    ATTR_EXPIRES,
    ATTR_EXPORT_TYPE,
    ATTR_FILENAME,
    ATTR_INCLUDE_DISABLED,
    ATTR_INCLUDE_HIDDEN,
    ATTR_ONLY_ENABLED,
    ATTR_STALE_DAYS,
    ATTR_STALE_ONLY,
    ATTR_UTF8_BOM,
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
    SERVICE_REMOVE_ORPHANED,
)
from .export import ExportOptions, async_run_export, remove_orphaned
from .http import EntityExportView

_LOGGER = logging.getLogger(__name__)

_VIEW_REGISTERED = f"{DOMAIN}_view_registered"

REMOVE_ORPHANED_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DRY_RUN, default=True): cv.boolean,
        vol.Optional(ATTR_CONFIRM, default=False): cv.boolean,
    }
)


async def _async_require_admin(hass: HomeAssistant, context: Context) -> None:
    if context.user_id is None:
        return
    user = await hass.auth.async_get_user(context.user_id)
    if user is None or not user.is_admin:
        raise Unauthorized(context=context)


_OPTION_FIELDS = {
    vol.Optional(ATTR_EXPORT_TYPE, default=DEFAULT_EXPORT_TYPE): vol.In(EXPORT_TYPES),
    vol.Optional(ATTR_INCLUDE_DISABLED, default=True): cv.boolean,
    vol.Optional(ATTR_INCLUDE_HIDDEN, default=True): cv.boolean,
    vol.Optional(ATTR_ONLY_ENABLED, default=False): cv.boolean,
    vol.Optional(ATTR_DOMAINS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_AREAS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_STALE_ONLY, default=False): cv.boolean,
    vol.Optional(ATTR_STALE_DAYS, default=DEFAULT_STALE_DAYS): cv.positive_int,
    vol.Optional(ATTR_UTF8_BOM, default=False): cv.boolean,
}

EXPORT_CSV_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_FILENAME, default=DEFAULT_FILENAME): cv.string, **_OPTION_FIELDS}
)

GET_DOWNLOAD_URL_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_EXPIRES, default=DEFAULT_EXPIRES): cv.positive_int, **_OPTION_FIELDS}
)


def _options_from_call(call: ServiceCall) -> ExportOptions:
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
        utf8_bom=call.data[ATTR_UTF8_BOM],
    )


def _options_to_query(options: ExportOptions) -> dict[str, str]:
    query = {
        "export_type": options.export_type,
        "include_disabled": str(options.include_disabled).lower(),
        "include_hidden": str(options.include_hidden).lower(),
        "only_enabled": str(options.only_enabled).lower(),
        "stale_only": str(options.stale_only).lower(),
        "stale_days": str(options.stale_days),
        "utf8_bom": str(options.utf8_bom).lower(),
    }
    if options.domains:
        query["domains"] = ",".join(sorted(options.domains))
    if options.areas:
        query["areas"] = ",".join(sorted(options.areas))
    return query


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

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

    async def handle_remove_orphaned(call: ServiceCall) -> ServiceResponse:
        await _async_require_admin(hass, call.context)
        should_apply = call.data[ATTR_CONFIRM]
        return remove_orphaned(hass, triggered_by="service", dry_run=not should_apply)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED,
        handle_remove_orphaned,
        schema=REMOVE_ORPHANED_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if not hass.data.get(_VIEW_REGISTERED):
        hass.http.register_view(EntityExportView(hass))
        hass.data[_VIEW_REGISTERED] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.services.async_remove(DOMAIN, SERVICE_EXPORT_CSV)
        hass.services.async_remove(DOMAIN, SERVICE_GET_DOWNLOAD_URL)
        hass.services.async_remove(DOMAIN, SERVICE_REMOVE_ORPHANED)
    return unload_ok
