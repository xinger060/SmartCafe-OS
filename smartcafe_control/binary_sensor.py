"""Binary sensor platform for SmartCafe Control - online status via ping."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_trackeds: set[str] = set()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartCafe binary sensor from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]

    entities = []
    for ip, device_data in coordinator.data.items():
        if ip not in _trackeds:
            _trackeds.add(ip)
            entities.append(PCManagerBinarySensor(coordinator, ip, device_data))

    async_add_entities(entities)

    @callback
    def _on_update() -> None:
        new_entities = []
        for ip, device_data in coordinator.data.items():
            if ip not in _trackeds:
                _trackeds.add(ip)
                new_entities.append(PCManagerBinarySensor(coordinator, ip, device_data))
        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(_on_update)


class PCManagerBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a PC online status sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "pc_online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:desktop-tower-monitor"

    def __init__(self, coordinator, ip: str, device_data: dict) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._ip = ip
        self._device_data = device_data
        self._attr_unique_id = f"pc_manager_{ip}_online"
        self._attr_name = device_data.get("name", ip)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": device_data.get("name", ip),
            "manufacturer": "SmartCafe",
        }

    @property
    def is_on(self) -> bool | None:
        device_data = self.coordinator.data.get(self._ip)
        if device_data:
            return device_data.get("is_online", False)
        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
