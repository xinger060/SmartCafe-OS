"""REST API for PC Manager -供ha-assistant调用."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .switch import _send_wol

_LOGGER = logging.getLogger(__name__)

# API路径前缀
URL_PREFIX = "/api/pc_manager"


class PCManagerDevicesView(HomeAssistantView):
    """View to handle device list requests."""

    url = f"{URL_PREFIX}/devices"
    name = "api:pc_manager:devices"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Get all devices."""
        hass = request.app["hass"]
        coordinator = hass.data[DOMAIN].get("coordinator")

        if not coordinator:
            return web.json_response({"devices": [], "count": 0})

        devices = []
        for ip, data in coordinator.data.items():
            devices.append({
                "ip": ip,
                "name": data.get("name", ip),
                "mac": data.get("mac", ""),
                "is_online": data.get("is_online", False),
            })

        return web.json_response({"devices": devices, "count": len(devices)})


class PCManagerStatusView(HomeAssistantView):
    """View to handle status requests."""

    url = f"{URL_PREFIX}/status"
    name = "api:pc_manager:status"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Get status of all devices."""
        hass = request.app["hass"]
        coordinator = hass.data[DOMAIN].get("coordinator")

        if not coordinator:
            return web.json_response({"devices": {}, "count": 0})

        status = {}
        for ip, data in coordinator.data.items():
            status[ip] = {
                "name": data.get("name", ip),
                "is_online": data.get("is_online", False),
            }

        return web.json_response({"devices": status, "count": len(status)})


class PCManagerWakeView(HomeAssistantView):
    """View to handle wake-on-LAN requests."""

    url = f"{URL_PREFIX}/devices/{{ip}}/wake"
    name = "api:pc_manager:wake"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Wake a device using WOL."""
        hass = request.app["hass"]
        ip = request.match_info["ip"]

        coordinator = hass.data[DOMAIN].get("coordinator")
        if not coordinator:
            return web.json_response({"error": "Coordinator not found"}, status=404)

        device_data = coordinator.data.get(ip)
        if not device_data:
            return web.json_response({"error": "Device not found"}, status=404)

        mac = device_data.get("mac", "")
        if not mac:
            return web.json_response({"error": "No MAC address configured"}, status=400)

        try:
            await hass.async_add_executor_job(_send_wol, mac)
            _LOGGER.info("WOL sent to %s (%s)", ip, mac)
            return web.json_response({"success": True, "message": f"WOL packet sent to {mac}"})
        except Exception as err:
            _LOGGER.error("WOL failed for %s: %s", ip, err)
            return web.json_response({"error": str(err)}, status=500)


async def async_register_api(hass: HomeAssistant) -> None:
    """Register the REST API views."""
    hass.http.register_view(PCManagerDevicesView)
    hass.http.register_view(PCManagerStatusView)
    hass.http.register_view(PCManagerWakeView)
    _LOGGER.info("PC Manager REST API registered at %s", URL_PREFIX)
