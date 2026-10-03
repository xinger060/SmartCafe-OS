"""Constants for the SmartCafe Control integration."""

from __future__ import annotations

import ipaddress

DOMAIN = "smartcafe_control"

# Config entry data keys (stored in data)
CONF_NAME = "name"
CONF_HOST_IP = "host_ip"
CONF_MAC = "mac"

# HA Assistant connection config
CONF_HA_ASSISTANT_URL = "ha_assistant_url"
CONF_HA_ASSISTANT_TOKEN = "ha_assistant_token"

# Config entry options keys (stored in options)
CONF_SUBNET_MASK = "subnet_mask"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PING_COUNT = "ping_count"

# Defaults
DEFAULT_SUBNET_MASK = "/20"
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_PING_COUNT = 2

# WOL
WOL_PORT = 9

# Platforms
PLATFORMS = ["switch", "binary_sensor"]


def normalize_subnet_mask(value: str) -> str:
    """Normalize a dotted-decimal subnet mask to /xx CIDR format.

    Accepts:
      - Dotted-decimal: "255.255.240.0", "255.255.255.0"

    Returns:
      A string like "/20".

    Raises:
      ValueError if the input is not a valid dotted-decimal subnet mask.
    """
    value = value.strip()

    try:
        network = ipaddress.IPv4Network(f"0.0.0.0/{value}", strict=False)
        return f"/{network.prefixlen}"
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid subnet mask: {value}") from err


def get_broadcast_address(host_ip: str, cidr_mask: str) -> str:
    """Calculate broadcast address from host IP and CIDR mask.

    Args:
        host_ip: e.g. "192.168.1.100"
        cidr_mask: e.g. "/20"

    Returns:
        Broadcast address string, e.g. "192.168.15.255"
    """
    prefix_len = int(cidr_mask.lstrip("/"))
    host = ipaddress.IPv4Address(host_ip)
    # Build network: use host as network address, apply prefix
    net = ipaddress.IPv4Network(f"{host}/{prefix_len}", strict=False)
    return str(net.broadcast_address)
