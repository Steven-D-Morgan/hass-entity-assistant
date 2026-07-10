"""HTTP download endpoint for Entity Assistant.

Serves the export as a downloadable CSV on demand, so it can be fetched
directly instead of writing a file to the config directory.
"""
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
from .export import ExportOptions, build_export, rows_to_csv


def _as_bool(value: str | None, default: bool) -> bool:
    """Parse a query-string flag."""
    if value is None:
        return default
    return value.lower() not in ("false", "0", "no")


def _as_set(value: str | None) -> frozenset[str] | None:
    """Parse a comma-separated query value into a set, or None if absent."""
    if not value:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    return frozenset(items) if items else None


def _as_int(value: str | None, default: int) -> int:
    """Parse a non-negative integer query value, falling back to default."""
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def options_from_query(query: Mapping[str, str]) -> ExportOptions:
    """Build ExportOptions from HTTP/URL query parameters."""
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
    )


class EntityExportView(HomeAssistantView):
    """Serve the export as a downloadable CSV file (authenticated)."""

    url = DOWNLOAD_URL
    name = "api:entity_assistant:export"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Store the hass instance."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Return the current export as a CSV attachment.

        Query flags: export_type, include_disabled, include_hidden,
        only_enabled, domains, areas.
        """
        options = options_from_query(request.query)
        columns, rows = build_export(self.hass, options)
        csv_text = rows_to_csv(columns, rows)

        return web.Response(
            body=csv_text.encode("utf-8"),
            content_type="text/csv",
            charset="utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{DOWNLOAD_FILENAME}"'
            },
        )
