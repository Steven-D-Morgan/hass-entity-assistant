"""Config flow for the Entity Assistant integration.

The integration takes no configuration — it only provides the
``entity_assistant.export_csv`` service. This single-step flow exists purely
so the integration is discoverable and addable from the Home Assistant UI
(Settings -> Devices & Services) and shows up in the integrations list.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class EntityAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entity Assistant."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (single instance, no options)."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Entity Assistant", data={})

        return self.async_show_form(step_id="user")
