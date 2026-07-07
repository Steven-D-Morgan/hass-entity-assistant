"""HTTP download endpoint for Entity Assistant.

Serves the entity export as a downloadable CSV on demand, so it can be
fetched directly instead of writing a file to the config directory.
"""
from __future__ import annotations

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOWNLOAD_FILENAME, DOWNLOAD_URL
from .export import build_rows, rows_to_csv


def _as_bool(value: str | None, default: bool = True) -> bool:
    """Parse a query-string flag."""
    if value is None:
        return default
    return value.lower() not in ("false", "0", "no")


class EntityExportView(HomeAssistantView):
    """Serve the entity export as a downloadable CSV file (authenticated)."""

    url = DOWNLOAD_URL
    name = "api:entity_assistant:export"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Store the hass instance."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Return the current entity registry as a CSV attachment.

        Optional query flags: include_disabled, include_hidden (default true).
        """
        include_disabled = _as_bool(request.query.get("include_disabled"))
        include_hidden = _as_bool(request.query.get("include_hidden"))

        rows = build_rows(self.hass, include_disabled, include_hidden)
        csv_text = rows_to_csv(rows)

        return web.Response(
            body=csv_text.encode("utf-8"),
            content_type="text/csv",
            charset="utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{DOWNLOAD_FILENAME}"'
            },
        )
