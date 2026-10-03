"""DataUpdateCoordinator for SmartCafe Control - reads devices from HA sensor."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_PING_COUNT,
    CONF_SCAN_INTERVAL,
    DEFAULT_PING_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_SENSOR_ENTITY = "sensor.smartcafe_devices"


class PCManagerCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator that reads devices from HA sensor and pings them.

    Data structure:
        {
            "ip_address": {
                "name": str,
                "ip": str,
                "mac": str,
                "is_online": bool,
            }
        }
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=True,
        )
        self.data: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Read devices from HA sensor and ping them."""
        old_ips = set(self.data.keys())

        devices = self._read_devices_from_sensor()

        new_ips = {d["ip"] for d in devices if d.get("ip")}

        removed_ips = old_ips - new_ips
        if removed_ips:
            _LOGGER.info("Removing %d devices: %s", len(removed_ips), removed_ips)
            await self._remove_devices(removed_ips)

        if devices:
            tasks = [self._async_ping(d["ip"]) for d in devices if d.get("ip")]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            idx = 0
            for device in devices:
                ip = device.get("ip", "")
                if not ip:
                    continue

                result = results[idx]
                idx += 1

                is_online = False if isinstance(result, Exception) else result

                self.data[ip] = {
                    "name": device.get("name", ip),
                    "ip": ip,
                    "mac": device.get("mac", ""),
                    "is_online": is_online,
                }

        return self.data

    def _read_devices_from_sensor(self) -> list[dict]:
        """Read device list from HA sensor entity (pushed by add-on heartbeat)."""
        state = self.hass.states.get(DEVICE_SENSOR_ENTITY)
        if state is None:
            _LOGGER.debug("Sensor %s not found", DEVICE_SENSOR_ENTITY)
            return []
        return state.attributes.get("devices", [])

    async def _remove_devices(self, ips: set[str]) -> None:
        """Remove devices and their entities from HA."""
        entity_registry = er.async_get(self.hass)

        # 实体注册表里登记的平台名是 "switch" / "binary_sensor"，
        # 原版把这两个位置都填成了集成域名 DOMAIN，导致永远查不到实体、
        # 从服务端删掉的设备在 HA 里会残留。这里修正。
        for ip in ips:
            for platform, unique_id in (
                ("switch", f"pc_manager_{ip}_switch"),
                ("binary_sensor", f"pc_manager_{ip}_online"),
            ):
                entity_id = entity_registry.async_get_entity_id(
                    platform, DOMAIN, unique_id
                )
                if entity_id:
                    _LOGGER.info("Removing entity: %s", entity_id)
                    entity_registry.async_remove(entity_id)

            self.data.pop(ip, None)

    async def _async_ping(self, host: str) -> bool:
        """Ping a host and return True if reachable."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping",
                "-c",
                str(DEFAULT_PING_COUNT),
                "-W",
                "2",
                host,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=DEFAULT_PING_COUNT * 3 + 2)
            return proc.returncode == 0
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.debug("Ping error for %s: %s", host, err)
            return False

    def get_device_by_ip(self, ip: str) -> dict[str, Any] | None:
        """Get device data by IP address."""
        return self.data.get(ip)
