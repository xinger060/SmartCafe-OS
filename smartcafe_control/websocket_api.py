"""WebSocket API for PC Manager - CSV export."""

from __future__ import annotations

import csv
import io

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_HOST_IP,
    CONF_MAC,
    CONF_NAME,
    CONF_PING_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_SUBNET_MASK,
    DEFAULT_PING_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SUBNET_MASK,
    DOMAIN,
)


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register WebSocket commands for PC Manager."""

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/export_csv",
        }
    )
    @websocket_api.async_response
    async def handle_export_csv(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
    ) -> None:
        """Handle CSV export request."""
        entries = hass.config_entries.async_entries(DOMAIN)

        output = io.StringIO()
        # UTF-8 BOM
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow(
            ["名称", "IP", "MAC", "子网掩码", "扫描间隔", "Ping次数"]
        )

        for entry in entries:
            name = entry.data.get(CONF_NAME, entry.title)
            host_ip = entry.data.get(CONF_HOST_IP, "")
            mac = entry.data.get(CONF_MAC, "")
            subnet = entry.options.get(CONF_SUBNET_MASK, DEFAULT_SUBNET_MASK)
            scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ping_count = entry.options.get(CONF_PING_COUNT, DEFAULT_PING_COUNT)
            writer.writerow([name, host_ip, mac, subnet, scan_interval, ping_count])

        csv_content = output.getvalue()
        output.close()

        connection.send_result(
            msg["id"],
            {
                "csv": csv_content,
                "count": len(entries),
            },
        )

    websocket_api.async_register_command(hass, handle_export_csv)
