"""Config flow for Wallos."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import WallosApiClient, WallosApiError, WallosAuthError, WallosConnectionError
from .const import (
    CONF_CONVERT_CURRENCY,
    CONF_DUE_SOON_DAYS,
    CONF_PER_SUBSCRIPTION,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_CONVERT_CURRENCY,
    DEFAULT_DUE_SOON_DAYS,
    DEFAULT_PER_SUBSCRIPTION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


class WallosConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, url: str, api_key: str, verify_ssl: bool) -> tuple[dict, str | None]:
        client = WallosApiClient(async_get_clientsession(self.hass), url, api_key, verify_ssl)
        try:
            return await client.get_user(), None
        except WallosAuthError:
            return {}, "invalid_auth"
        except WallosConnectionError:
            return {}, "cannot_connect"
        except WallosApiError:
            return {}, "unknown"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = _normalize_url(user_input[CONF_URL])
            user, error = await self._validate(
                url, user_input[CONF_API_KEY], user_input[CONF_VERIFY_SSL]
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(f"{url}_{user.get('id', 'user')}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Wallos ({user.get('username') or url})",
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=(user_input or {}).get(CONF_URL, "http://")): str,
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_VERIFY_SSL, default=True): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            _, error = await self._validate(
                entry.data[CONF_URL], user_input[CONF_API_KEY], entry.data.get(CONF_VERIFY_SSL, True)
            )
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> WallosOptionsFlow:
        return WallosOptionsFlow()


class WallosOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        o = self.config_entry.options

        def num(lo: int, hi: int, unit: str | None = None) -> NumberSelector:
            return NumberSelector(
                NumberSelectorConfig(
                    min=lo, max=hi, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement=unit
                )
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=o.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): num(5, 1440, "min"),
                vol.Required(
                    CONF_CONVERT_CURRENCY,
                    default=o.get(CONF_CONVERT_CURRENCY, DEFAULT_CONVERT_CURRENCY),
                ): bool,
                vol.Required(
                    CONF_DUE_SOON_DAYS, default=o.get(CONF_DUE_SOON_DAYS, DEFAULT_DUE_SOON_DAYS)
                ): num(1, 60, "d"),
                vol.Required(
                    CONF_PER_SUBSCRIPTION,
                    default=o.get(CONF_PER_SUBSCRIPTION, DEFAULT_PER_SUBSCRIPTION),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
