"""HTTP download endpoint for Entity Assistant."""

from __future__ import annotations

from collections.abc import Mapping

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_EXPORT_TYPE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_SORT_DIR,
    DEFAULT_STALE_DAYS,
    DOWNLOAD_FILENAME_BASE,
    DOWNLOAD_URL,
    EXPORT_TYPES,
    OUTPUT_FORMAT_CONTENT_TYPES,
    OUTPUT_FORMATS,
    SORT_DIRS,
)
from .export import ExportOptions, build_export, fire_export_failed, serialize_export


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
    output_format = query.get("output_format", DEFAULT_OUTPUT_FORMAT)
    if output_format not in OUTPUT_FORMATS:
        output_format = DEFAULT_OUTPUT_FORMAT
    sort_dir = query.get("sort_dir", DEFAULT_SORT_DIR)
    if sort_dir not in SORT_DIRS:
        sort_dir = DEFAULT_SORT_DIR
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
        output_format=output_format,
        sort_by=query.get("sort_by") or None,
        sort_dir=sort_dir,
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
            body = serialize_export(columns, rows, options.output_format, utf8_bom=options.utf8_bom)
        except Exception as err:
            fire_export_failed(self.hass, options, "http", "", err)
            return web.Response(
                status=500,
                text=f"Entity Assistant export failed: {type(err).__name__}",
                headers={"Cache-Control": "no-store"},
            )

        content_type = OUTPUT_FORMAT_CONTENT_TYPES[options.output_format]
        download_name = f"{DOWNLOAD_FILENAME_BASE}.{options.output_format}"
        return web.Response(
            body=body.encode("utf-8"),
            content_type=content_type,
            charset="utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{download_name}"',
                "Cache-Control": "no-store",
            },
        )
