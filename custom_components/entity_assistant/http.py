"""HTTP download endpoint for Entity Assistant."""

from __future__ import annotations

from collections.abc import Mapping

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_EXPORT_TYPE,
    DEFAULT_STALE_DAYS,
    DOWNLOAD_FILENAME,
    DOWNLOAD_URL,
    EXPORT_TYPES,
)
from .export import ExportOptions, build_export, fire_export_failed, rows_to_csv


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() not in ("false", "0", "no")


def _as_set(value: str | None) -> frozenset[str] | None:
    if not value:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    return frozenset(items) if items else None


def _as_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def options_from_query(query: Mapping[str, str]) -> ExportOptions:
    export_type = query.get("export_type", DEFAULT_EXPORT_TYPE)
    if export_type not in EXPORT_TYPES:
        export_type = DEFAULT_EXPORT_TYPE
    return ExportOptions(
        export_type=export_type,
        include_disabled=_as_bool(query.get("include_disabled"), True),
        include_hidden=_as_bool(query.get("include_hidden"), True),
        only_enabled=_as_bool(query.get("only_enabled"), False),
        domains=_as_set(query.get("domains")),
        areas=_as_set(query.get("areas")),
        stale_only=_as_bool(query.get("stale_only"), False),
        stale_days=_as_int(query.get("stale_days"), DEFAULT_STALE_DAYS),
        utf8_bom=_as_bool(query.get("utf8_bom"), False),
    )


class EntityExportView(HomeAssistantView):
    url = DOWNLOAD_URL
    name = "api:entity_assistant:export"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        options = options_from_query(request.query)
        try:
            columns, rows = build_export(self.hass, options)
            csv_text = rows_to_csv(columns, rows, utf8_bom=options.utf8_bom)
        except Exception as err:
            fire_export_failed(self.hass, options, "http", "", err)
            return web.Response(
                status=500,
                text=f"Entity Assistant export failed: {type(err).__name__}",
                headers={"Cache-Control": "no-store"},
            )

        return web.Response(
            body=csv_text.encode("utf-8"),
            content_type="text/csv",
            charset="utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{DOWNLOAD_FILENAME}"',
                "Cache-Control": "no-store",
            },
        )
