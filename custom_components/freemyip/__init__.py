"""Integrate FreeMyIP at https://freemyip.com/."""

from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.const import CONF_DOMAIN, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_API_ECONOMY,
    CONF_ENABLE_IPV6,
    DOMAIN,
    SERVICE_REFRESH,
)
from .coordinator import FreeMyIPDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the FreeMyIP component."""
    _LOGGER.debug("Initializing FreeMyIP component")
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
    """Migrate old config entries to new format."""
    _LOGGER.debug("Migrating config entry %s", config_entry.entry_id)
    if config_entry.version == 1:
        new_options = {**config_entry.options}
        if CONF_API_ECONOMY not in new_options:
            new_options[CONF_API_ECONOMY] = True
        if CONF_ENABLE_IPV6 not in new_options:
            new_options[CONF_ENABLE_IPV6] = True
        hass.config_entries.async_update_entry(config_entry, options=new_options)
        _LOGGER.info("Migrated config entry %s options: economy/ipv6 defaults applied", config_entry.entry_id)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Configure based on config entry."""
    _LOGGER.debug("Configuring FreeMyIP for entry %s with domain %s", entry.entry_id, entry.data.get("domain"))
    if not entry.data.get("domain"):
        _LOGGER.error("Invalid config entry: missing domain for entry %s", entry.entry_id)
        async_create(
            hass,
            f"FreeMyIP: Invalid config entry for ID {entry.entry_id}. Domain is missing.",
            title="FreeMyIP Configuration Error",
            notification_id=f"{DOMAIN}_{entry.entry_id}_config_error",
        )
        return False
    async_dismiss(
        hass,
        notification_id=f"{DOMAIN}_{entry.entry_id}_config_error",
    )

    if not await async_migrate_entry(hass, entry):
        return False

    coordinator = FreeMyIPDataUpdateCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except (ValueError, ConnectionError) as err:
        _LOGGER.error("Failed to refresh config entry %s: %s", entry.entry_id, err)
        async_create(
            hass,
            f"FreeMyIP: Error while loading configuration for {entry.data.get('domain')}: {err}",
            title="FreeMyIP Initialization Error",
            notification_id=f"{DOMAIN}_{entry.entry_id}_init_error",
        )
        return False
    async_dismiss(
        hass,
        notification_id=f"{DOMAIN}_{entry.entry_id}_init_error",
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    async def refresh(call: ServiceCall) -> None:
        """Handle service call to update IP address."""
        if len(hass.data[DOMAIN]) != 1:
            _LOGGER.error("Expected exactly one config entry, found %d", len(hass.data[DOMAIN]))
            async_create(
                hass,
                f"FreeMyIP: Invalid number of config entries: {len(hass.data[DOMAIN])}. Only one instance is allowed.",
                title="FreeMyIP Service Error",
                notification_id=f"{DOMAIN}_service_error",
            )
            return
        async_dismiss(
            hass,
            notification_id=f"{DOMAIN}_service_error",
        )
        entry_id = next(iter(hass.data[DOMAIN]))
        _LOGGER.debug("Service call to refresh IP address for entry %s", entry_id)
        coordinator: FreeMyIPDataUpdateCoordinator = hass.data[DOMAIN][entry_id]
        await coordinator.async_update(call)

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_register(DOMAIN, SERVICE_REFRESH, refresh)
    else:
        _LOGGER.debug("Service %s already registered", SERVICE_REFRESH)

    return True


async def options_update_listener(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Reloading FreeMyIP integration for entry %s due to options update", config_entry.entry_id)
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading FreeMyIP config entry %s", entry.entry_id)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    return unload_ok
