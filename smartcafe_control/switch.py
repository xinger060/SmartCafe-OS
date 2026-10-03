"""Switch platform for SmartCafe Control - WOL wake-on-LAN switch."""

from __future__ import annotations

import logging
import socket
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, CONF_HOST_IP, DOMAIN, WOL_PORT

_LOGGER = logging.getLogger(__name__)

_trackeds: set[str] = set()


def _send_wol(mac_address: str) -> None:
    """Send a Wake-on-LAN magic packet (synchronous)."""
    if len(mac_address) != 17:
        raise ValueError(f"Invalid MAC address: {mac_address}")

    mac_bytes = bytes.fromhex(mac_address.replace(":", "").replace("-", ""))
    magic_packet = b"\xff" * 6 + mac_bytes * 16

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, ("<broadcast>", WOL_PORT))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartCafe switch from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]

    entities = []
    for ip, device_data in coordinator.data.items():
        if ip not in _trackeds:
            _trackeds.add(ip)
            entities.append(PCManagerSwitch(coordinator, ip, device_data))

    async_add_entities(entities)

    @callback
    def _on_update() -> None:
        new_entities = []
        for ip, device_data in coordinator.data.items():
            if ip not in _trackeds:
                _trackeds.add(ip)
                new_entities.append(PCManagerSwitch(coordinator, ip, device_data))
        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(_on_update)


class PCManagerSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a PC power switch via Wake-on-LAN."""

    _attr_has_entity_name = True
    _attr_translation_key = "pc_power"
    _attr_icon = "mdi:desktop-tower-monitor"

    def __init__(self, coordinator, ip: str, device_data: dict) -> None:
        super().__init__(coordinator)
        self._ip = ip
        self._device_data = device_data
        self._attr_unique_id = f"pc_manager_{ip}_switch"
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

    def turn_on(self, **kwargs: Any) -> None:
        device_data = self.coordinator.data.get(self._ip)
        mac = device_data.get("mac", "") if device_data else ""

        if not mac:
            _LOGGER.error("No MAC address configured for %s", self._ip)
            return

        try:
            _send_wol(mac)
            _LOGGER.info("WOL magic packet sent to %s (%s)", self._ip, mac)
        except Exception as err:
            _LOGGER.error("Failed to send WOL to %s: %s", self._ip, err)

    def turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("Turn off called for %s - not implemented", self._ip)
