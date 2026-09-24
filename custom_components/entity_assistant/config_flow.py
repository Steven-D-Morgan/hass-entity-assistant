"""Config and options flow for the Entity Assistant integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
import voluptuous as vol

from .const import (
    ATTR_EXPORT_TYPE,
    ATTR_FILENAME,
    ATTR_INCLUDE_DISABLED,
    ATTR_INCLUDE_HIDDEN,
    ATTR_ONLY_ENABLED,
    ATTR_OUTPUT_FORMAT,
    ATTR_STALE_DAYS,
    ATTR_STALE_ONLY,
    ATTR_UTF8_BOM,
    DEFAULT_EXPORT_TYPE,
    DEFAULT_FILENAME,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_STALE_DAYS,
    DOMAIN,
    EXPORT_TYPES,
    OUTPUT_FORMATS,
)


class EntityAssistantConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EntityAssistantOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Entity Assistant", data={})

        return self.async_show_form(step_id="user")


class EntityAssistantOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_EXPORT_TYPE,
                    default=current.get(ATTR_EXPORT_TYPE, DEFAULT_EXPORT_TYPE),
                ): vol.In(EXPORT_TYPES),
                vol.Optional(
                    ATTR_FILENAME, default=current.get(ATTR_FILENAME, DEFAULT_FILENAME)
                ): str,
                vol.Optional(
                    ATTR_OUTPUT_FORMAT,
                    default=current.get(ATTR_OUTPUT_FORMAT, DEFAULT_OUTPUT_FORMAT),
                ): vol.In(OUTPUT_FORMATS),
                vol.Optional(
                    ATTR_INCLUDE_DISABLED,
                    default=current.get(ATTR_INCLUDE_DISABLED, True),
                ): bool,
                vol.Optional(
                    ATTR_INCLUDE_HIDDEN, default=current.get(ATTR_INCLUDE_HIDDEN, True)
                ): bool,
                vol.Optional(
                    ATTR_ONLY_ENABLED, default=current.get(ATTR_ONLY_ENABLED, False)
                ): bool,
                vol.Optional(ATTR_STALE_ONLY, default=current.get(ATTR_STALE_ONLY, False)): bool,
                vol.Optional(
                    ATTR_STALE_DAYS, default=current.get(ATTR_STALE_DAYS, DEFAULT_STALE_DAYS)
                ): int,
                vol.Optional(ATTR_UTF8_BOM, default=current.get(ATTR_UTF8_BOM, False)): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
