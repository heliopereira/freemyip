"""Sensors for FreeMyIP IPv4/IPv6 updates."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_IP_ADDRESS, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENABLE_IPV6, DOMAIN, SHORT_NAME
from .coordinator import FreeMyIPDataUpdateCoordinator


class FreeMyIPBaseEntity(CoordinatorEntity[FreeMyIPDataUpdateCoordinator], RestoreSensor):
    """Base entity class for FreeMyIP."""

    _attr_available = False
    _attr_force_update = True
    _attr_has_entity_name = True

    def __init__(self, coordinator: FreeMyIPDataUpdateCoordinator, domain: str) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._attr_attribution = "Data provided by FreeMyIP"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, domain)},
            manufacturer="FreeMyIP",
            model="Dynamic DNS Service",
            name=f"{SHORT_NAME} {domain}",
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_sensor_data():
            self._attr_native_value = state.native_value
        self._attr_available = True


class FreeMyIPStatusSensor(FreeMyIPBaseEntity, SensorEntity):
    """Status sensor for FreeMyIP update calls."""

    def __init__(self, coordinator: FreeMyIPDataUpdateCoordinator) -> None:
        super().__init__(coordinator, coordinator.data[CONF_DOMAIN])
        self._attr_name = "Status"
        self._attr_unique_id = f"{DOMAIN}_{coordinator.data[CONF_DOMAIN]}_status"

    @property
    def native_value(self) -> StateType:
        return self.coordinator.data.get("status", "unknown")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            CONF_DOMAIN: self.coordinator.data.get(CONF_DOMAIN, "unknown"),
            "ipv4": self.coordinator.data.get("ip_v4", "unknown"),
            "ipv6": self.coordinator.data.get("ip_v6", "unknown"),
            "last_update": self.coordinator.data.get("last_update", "unknown"),
        }


class FreeMyIPLastUpdateSensor(FreeMyIPBaseEntity, SensorEntity):
    """Sensor for successful update timestamp."""

    _attr_icon = "mdi:clock"

    def __init__(self, coordinator: FreeMyIPDataUpdateCoordinator) -> None:
        super().__init__(coordinator, coordinator.data[CONF_DOMAIN])
        self._attr_name = "Last Update"
        self._attr_unique_id = f"{DOMAIN}_{coordinator.data[CONF_DOMAIN]}_last_update"

    @property
    def native_value(self) -> StateType:
        return self.coordinator.data.get("last_update", "unknown")


class FreeMyIPDomainSensor(FreeMyIPBaseEntity, SensorEntity):
    """Sensor for FreeMyIP IPv4/IPv6 values."""

    _attr_icon = "mdi:ip"

    def __init__(self, coordinator: FreeMyIPDataUpdateCoordinator, domain: str, record_type: str) -> None:
        super().__init__(coordinator, domain)
        self._domain = domain
        self._record_type = record_type
        if record_type == "A":
            self._attr_name = "IPv4"
            self._attr_unique_id = f"{DOMAIN}_{domain}_ipv4"
        else:
            self._attr_name = "IPv6"
            self._attr_unique_id = f"{DOMAIN}_{domain}_ipv6"

    @property
    def native_value(self) -> StateType:
        for subdomain in self.coordinator.data.get("subdomains", []):
            if subdomain.get(CONF_DOMAIN) == self._domain and subdomain.get(CONF_TYPE) == self._record_type:
                return subdomain.get(CONF_IP_ADDRESS, "unknown")
        return "unknown"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FreeMyIP sensors from the config entry."""
    coordinator: FreeMyIPDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[SensorEntity] = [
        FreeMyIPStatusSensor(coordinator),
        FreeMyIPLastUpdateSensor(coordinator),
    ]

    domain = coordinator.data.get(CONF_DOMAIN)
    if domain:
        entities.append(FreeMyIPDomainSensor(coordinator, domain, "A"))
        if coordinator.config_entry.options.get(CONF_ENABLE_IPV6, True):
            entities.append(FreeMyIPDomainSensor(coordinator, domain, "AAAA"))

    async_add_entities(entities)
