"""Coordinator for FreeMyIP."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_IP_ADDRESS, CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHECKIP_V4_URL,
    CHECKIP_V6_URL,
    CONF_API_ECONOMY,
    CONF_ENABLE_IPV6,
    DOMAIN,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    TIMEOUT,
    UPDATE_URL,
)

_LOGGER = logging.getLogger(__name__)


class FreeMyIPDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for FreeMyIP updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.config_entry = entry
        self.data = {CONF_DOMAIN: entry.data.get(CONF_DOMAIN, "")}
        self._cache = Store(hass, version=1, key=f"{DOMAIN}_{entry.entry_id}_data")
        interval = entry.options.get(CONF_SCAN_INTERVAL, 23)
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=interval) if interval > 0 else None,
        )

    async def async_update(self, call: ServiceCall) -> None:
        economy = call.data.get(CONF_API_ECONOMY, False)
        if not isinstance(economy, bool):
            economy = False
        await self._async_update_data(is_economy=economy)

    async def _async_update_data(self, is_economy: bool = False) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        domain = self.config_entry.data.get(CONF_DOMAIN, "")
        token = self.config_entry.data.get(CONF_TOKEN, "")
        ipv6_enabled = self.config_entry.options.get(CONF_ENABLE_IPV6, True)

        current_v4 = "unknown"
        current_v6 = "unknown"

        try:
            async with session.get(CHECKIP_V4_URL, timeout=TIMEOUT) as resp:
                resp.raise_for_status()
                current_v4 = (await resp.text()).strip()
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.debug("IPv4 detection unavailable")

        if ipv6_enabled:
            try:
                async with session.get(CHECKIP_V6_URL, timeout=TIMEOUT) as resp:
                    resp.raise_for_status()
                    current_v6 = (await resp.text()).strip()
            except (aiohttp.ClientError, TimeoutError):
                _LOGGER.debug("IPv6 detection unavailable")

        previous_v4 = self.data.get("ip_v4", "unknown")
        previous_v6 = self.data.get("ip_v6", "unknown")
        self.data["ip_v4"] = current_v4
        self.data["ip_v6"] = current_v6

        should_update = True
        if self.config_entry.options.get(CONF_API_ECONOMY, True) or is_economy:
            should_update = (current_v4 != "unknown" and current_v4 != previous_v4) or (
                ipv6_enabled and current_v6 != "unknown" and current_v6 != previous_v6
            )

        last_update = self.data.get("last_update", "unknown")

        if should_update:
            update_statuses: list[str] = []

            async def _call_update(params: dict[str, str]) -> str:
                for attempt in range(RETRY_ATTEMPTS):
                    try:
                        async with session.get(UPDATE_URL, params=params, timeout=TIMEOUT) as resp:
                            resp.raise_for_status()
                            text = (await resp.text()).strip()
                            return "ok" if "OK" in text.upper() else "error"
                    except (aiohttp.ClientError, TimeoutError) as err:
                        if attempt == RETRY_ATTEMPTS - 1:
                            raise UpdateFailed(f"Update call failed: {err}") from err
                        await asyncio.sleep(RETRY_DELAY)
                return "error"

            base_params = {"domain": domain, "token": token, "verbose": "yes"}

            if current_v4 != "unknown":
                base_params["myip"] = current_v4
            update_statuses.append(await _call_update(dict(base_params)))

            if ipv6_enabled and current_v6 != "unknown":
                ipv6_params = {"domain": domain, "token": token, "verbose": "yes", "myip": current_v6}
                update_statuses.append(await _call_update(ipv6_params))

            self.data["status"] = "good" if all(s == "ok" for s in update_statuses) else "error"
            self.data["update_result"] = self.data["status"]
            if self.data["status"] == "good":
                last_update = datetime.now().isoformat()
        else:
            self.data["status"] = "nochg"
            self.data["update_result"] = "unchanged"

        self.data["last_update"] = last_update

        if current_v4 != "unknown":
            self.data["subdomains"] = [
                {
                    CONF_DOMAIN: domain,
                    CONF_IP_ADDRESS: current_v4,
                    CONF_TYPE: "A",
                    "last_update": last_update,
                }
            ]
        else:
            self.data["subdomains"] = []

        if ipv6_enabled and current_v6 != "unknown":
            self.data["subdomains"].append(
                {
                    CONF_DOMAIN: domain,
                    CONF_IP_ADDRESS: current_v6,
                    CONF_TYPE: "AAAA",
                    "last_update": last_update,
                }
            )

        self.data["cache_time"] = datetime.now().isoformat()
        await self._cache.async_save(self.data)

        async_dismiss(self.hass, notification_id=f"{DOMAIN}_{self.config_entry.entry_id}_network_update_error")
        if self.data["status"] == "error":
            async_create(
                self.hass,
                f"FreeMyIP: failed to update domain {domain}.",
                title="FreeMyIP Update Error",
                notification_id=f"{DOMAIN}_{self.config_entry.entry_id}_network_update_error",
            )

        return self.data
