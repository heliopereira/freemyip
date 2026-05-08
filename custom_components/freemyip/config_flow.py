"""Config flow for FreeMyIP."""

from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_DOMAIN, CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CHECKIP_V4_URL,
    CHECKIP_V6_URL,
    CONF_API_ECONOMY,
    CONF_ENABLE_IPV6,
    DEFAULT_INTERVAL,
    DOMAIN,
    TIMEOUT,
    UPDATE_URL,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN_REGEX = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$"
UPDATE_TOKEN_REGEX = r"^[A-Za-z0-9]{16,128}$"


class UpdateTokenError(Exception):
    """Exception for invalid update token."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidDomain(HomeAssistantError):
    """Error to indicate the domain format is invalid."""


class InvalidUpdateTokenFormat(HomeAssistantError):
    """Error to indicate update token format looks invalid."""


async def validate_update_token(hass: core.HomeAssistant, data: dict[str, Any]) -> None:
    """Validate update token against FreeMyIP updater endpoint."""
    session: aiohttp.ClientSession = async_get_clientsession(hass)
    params = {"domain": data[CONF_DOMAIN], "token": data[CONF_TOKEN], "verbose": "yes"}

    try:
        async with session.get(UPDATE_URL, params=params, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            body = (await resp.text()).strip()
            if "ERROR" in body.upper():
                raise UpdateTokenError("Invalid update token or domain")
    except aiohttp.ClientResponseError as error:
        if error.status == 401:
            raise UpdateTokenError("Invalid update token") from error
        if error.status == 429:
            raise CannotConnect("Rate limit exceeded") from error
        raise CannotConnect(f"Updater API error: {error.message}") from error
    except (TimeoutError, aiohttp.ClientError) as error:
        raise CannotConnect(f"Network error: {error}") from error


async def validate_input(hass: core.HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""
    if not re.match(DOMAIN_REGEX, data[CONF_DOMAIN]):
        raise InvalidDomain("Invalid domain format")
    if not re.match(UPDATE_TOKEN_REGEX, data[CONF_TOKEN]):
        raise InvalidUpdateTokenFormat("Invalid update token format")
    await validate_update_token(hass, data)
    return {"title": f"{DOMAIN} {data[CONF_DOMAIN]}"}


async def detect_public_ips(hass: core.HomeAssistant) -> dict[str, str]:
    """Detect current public IPv4/IPv6 addresses for setup hints."""
    session: aiohttp.ClientSession = async_get_clientsession(hass)

    async def _get_ip(url: str) -> str:
        try:
            async with session.get(url, timeout=TIMEOUT) as resp:
                resp.raise_for_status()
                return (await resp.text()).strip()
        except (TimeoutError, aiohttp.ClientError):
            return "unavailable"

    ipv4 = await _get_ip(CHECKIP_V4_URL)
    ipv6 = await _get_ip(CHECKIP_V6_URL)
    ipv6_supported = "yes" if ipv6 != "unavailable" else "no"
    return {"ipv4": ipv4, "ipv6": ipv6, "ipv6_supported": ipv6_supported}


class FreeMyIPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    @staticmethod
    @core.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return FreeMyIPOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        ip_info = await detect_public_ips(self.hass)
        ipv6_default = ip_info["ipv6"] != "unavailable"
        data_schema = vol.Schema(
            {
                vol.Required(CONF_DOMAIN): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, multiline=False)),
                vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD, multiline=False)),
                vol.Required(CONF_API_ECONOMY, default=True): BooleanSelector(BooleanSelectorConfig()),
                vol.Required(CONF_ENABLE_IPV6, default=ipv6_default): BooleanSelector(BooleanSelectorConfig()),
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER,
                        min=0,
                        max=120,
                        step=1,
                        unit_of_measurement="minutes",
                    )
                ),
            }
        )

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                unique_id = user_input[CONF_DOMAIN]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_DOMAIN: user_input[CONF_DOMAIN],
                        CONF_TOKEN: user_input[CONF_TOKEN],
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                        CONF_API_ECONOMY: user_input[CONF_API_ECONOMY],
                        CONF_ENABLE_IPV6: user_input[CONF_ENABLE_IPV6],
                    },
                )
            except InvalidDomain:
                errors["base"] = "invalid_domain"
            except InvalidUpdateTokenFormat:
                errors["base"] = "invalid_update_token_format"
            except UpdateTokenError:
                errors["base"] = "unauthorized"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during validation")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            last_step=False,
            description_placeholders={
                "ipv4": ip_info["ipv4"],
                "ipv6": ip_info["ipv6"],
                "ipv6_supported": ip_info["ipv6_supported"],
            },
        )


class FreeMyIPOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """Handle the options flow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        ip_info = await detect_public_ips(self.hass)
        options = self.options
        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_ECONOMY, default=options.get(CONF_API_ECONOMY, True)): BooleanSelector(
                    BooleanSelectorConfig()
                ),
                vol.Required(
                    CONF_ENABLE_IPV6,
                    default=options.get(CONF_ENABLE_IPV6, ip_info["ipv6"] != "unavailable"),
                ): BooleanSelector(BooleanSelectorConfig()),
                vol.Required(CONF_SCAN_INTERVAL, default=options.get(CONF_SCAN_INTERVAL, DEFAULT_INTERVAL)): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER,
                        min=0,
                        max=120,
                        step=1,
                        unit_of_measurement="minutes",
                    )
                ),
                vol.Required(CONF_TOKEN, default=self.config_entry.data.get(CONF_TOKEN, "")): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD, multiline=False)
                ),
            }
        )

        if user_input is not None:
            token = user_input[CONF_TOKEN]
            if not re.match(UPDATE_TOKEN_REGEX, token):
                return self.async_show_form(
                    step_id="init",
                    data_schema=data_schema,
                    errors={"base": "invalid_update_token_format"},
                    last_step=True,
                    description_placeholders=ip_info,
                )
            try:
                await validate_update_token(
                    self.hass,
                    {
                        CONF_DOMAIN: self.config_entry.data[CONF_DOMAIN],
                        CONF_TOKEN: token,
                    },
                )
            except UpdateTokenError:
                return self.async_show_form(
                    step_id="init",
                    data_schema=data_schema,
                    errors={"base": "unauthorized"},
                    last_step=True,
                    description_placeholders=ip_info,
                )
            except CannotConnect:
                return self.async_show_form(
                    step_id="init",
                    data_schema=data_schema,
                    errors={"base": "cannot_connect"},
                    last_step=True,
                    description_placeholders=ip_info,
                )

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKEN: token},
            )
            user_input = {k: v for k, v in user_input.items() if k != CONF_TOKEN}
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            last_step=True,
            description_placeholders=ip_info,
        )
