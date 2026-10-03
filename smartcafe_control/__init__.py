"""SmartCafe Control - manage PCs with WOL and ping monitoring."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import PCManagerCoordinator
from .rest_api import async_register_api

_LOGGER = logging.getLogger(__name__)

# REST 视图在一个 HA 进程里只能注册一次。
# 用模块级标志位而不是 hass.data：重载集成时 hass.data 会被清空，
# 但 HTTP 视图还在，重复注册会报错。
_API_REGISTERED = False


async def _ensure_api(hass: HomeAssistant) -> None:
    """注册 /api/pc_manager/* 的 REST 视图（只注册一次）。

    ⚠️ 这是本项目的关键一行为什么重要：
        智咖系统后台的「PC状态」那一列，读的是 /admin/pc-manager/status，
        它会转发到 HA 的 /api/pc_manager/status。

        而原版的 rest_api.py 里定义了 async_register_api()，
        __init__.py 却从来没有调用它 —— 于是这三个接口一直返回 404，
        智咖后台拿不到数据，就把所有设备一律显示成「离线」。

        所以：**这一行不能删**。删了智咖后台的 PC 状态就又变回永远离线。
    """
    global _API_REGISTERED
    if _API_REGISTERED:
        return
    await async_register_api(hass)
    _API_REGISTERED = True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # 有些安装方式（configuration.yaml 里写了 smartcafe_control:）只走这里、
    # 不走 async_setup_entry，所以两边都兜一下，保证视图一定被注册。
    await _ensure_api(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    if "coordinator" not in hass.data[DOMAIN]:
        coordinator = PCManagerCoordinator(hass, entry)
        hass.data[DOMAIN]["coordinator"] = coordinator
    else:
        coordinator: PCManagerCoordinator = hass.data[DOMAIN]["coordinator"]

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        await coordinator.async_config_entry_first_refresh()

    # 把 /api/pc_manager/* 注册出去（智咖后台的「PC状态」靠它）
    await _ensure_api(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        remaining = hass.config_entries.async_entries(DOMAIN)
        if len(remaining) <= 1:
            hass.data.pop(DOMAIN, None)

    return unload_ok
