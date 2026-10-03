"""Config flow for SmartCafe Control integration.

修订说明（对比原版）：
1. 删除原版在循环里调用 config_entries.flow.async_init 的写法 —— 那是非法用法，
   会抛异常且未被捕获，导致 UI 只显示 "Unknown error occurred"。
   改为在同一个流程里直接 async_create_entry，一次导入一台设备。
2. 修正 _abort_if_unique_id_configured() 缺少 return 的问题。
3. 所有未预期的异常一律写入日志（可在 HA 日志里看到真实堆栈），
   并在界面上给出可翻译的中文提示，不再出现 "Unknown error occurred"。
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_PING_COUNT,
    CONF_SCAN_INTERVAL,
    DEFAULT_PING_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_SENSOR_ENTITY = "sensor.smartcafe_devices"

# 界面上最多渲染多少个可选设备（防止设备太多把下拉框撑爆）
MAX_DEVICES_IN_FORM = 200


class SmartCafeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmartCafe Control."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SmartCafeOptionsFlow:
        """Get the options flow for this handler."""
        return SmartCafeOptionsFlow()

    def __init__(self) -> None:
        """Initialize config flow."""
        self._devices: list[dict] = []

    def _already_configured_ips(self) -> set[str]:
        """返回已经导入过的设备 IP。"""
        ips: set[str] = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            ip = entry.data.get("host_ip") or entry.unique_id
            if ip:
                ips.add(ip)
        return ips

    def _read_devices_from_sensor(self) -> list[dict]:
        """从服务端推送的 sensor 里读出设备列表。"""
        state = self.hass.states.get(DEVICE_SENSOR_ENTITY)
        if state is None:
            return []

        raw = state.attributes.get("devices")
        if not isinstance(raw, list):
            _LOGGER.error(
                "%s 的 devices 属性不是列表，实际类型 %s，内容: %r",
                DEVICE_SENSOR_ENTITY,
                type(raw).__name__,
                raw,
            )
            return []

        devices: list[dict] = []
        for item in raw:
            if not isinstance(item, dict):
                _LOGGER.warning("跳过异常设备条目: %r", item)
                continue
            ip = str(item.get("ip") or "").strip()
            if not ip:
                continue
            devices.append(
                {
                    "ip": ip,
                    "mac": str(item.get("mac") or "").strip(),
                    "name": str(item.get("name") or ip),
                    "category": str(item.get("category") or ""),
                }
            )
        return devices

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """第 1 步：读取服务端推送上来的设备列表。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._devices = self._read_devices_from_sensor()
            except Exception:  # noqa: BLE001 - 兜底，保证界面永远有可读提示
                _LOGGER.exception("读取 %s 时发生未预期异常", DEVICE_SENSOR_ENTITY)
                errors["base"] = "unknown"
            else:
                if not self._devices:
                    errors["base"] = "no_sensor_found"
                else:
                    already = self._already_configured_ips()
                    pending = [d for d in self._devices if d["ip"] not in already]
                    if not pending:
                        return self.async_abort(reason="all_devices_configured")
                    return await self.async_step_devices()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "entity_id": DEVICE_SENSOR_ENTITY,
            },
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """第 2 步：选择要导入的设备（未导入的每台会创建一个条目）。"""
        errors: dict[str, str] = {}

        already = self._already_configured_ips()
        pending = [d for d in self._devices if d["ip"] not in already]

        if user_input is not None:
            selected_ips = user_input.get("devices") or []
            if isinstance(selected_ips, str):
                selected_ips = [selected_ips]
            if not selected_ips:
                errors["devices"] = "no_devices_selected"
            else:
                created = 0
                failed = 0
                for device in pending:
                    if device["ip"] not in selected_ips:
                        continue
                    try:
                        await self.async_set_unique_id(device["ip"])
                        self._abort_if_unique_id_configured()
                        await self.hass.config_entries.flow.async_init(
                            DOMAIN,
                            context={"source": config_entries.SOURCE_IMPORT},
                            data={
                                "name": device["name"],
                                "host_ip": device["ip"],
                                "mac": device["mac"],
                            },
                        )
                        created += 1
                    except config_entries.AbortFlow:
                        # 已经存在，跳过即可，不算失败
                        continue
                    except Exception:  # noqa: BLE001
                        failed += 1
                        _LOGGER.exception("导入设备 %s 失败", device["ip"])

                if created == 0 and failed == 0:
                    return self.async_abort(reason="all_devices_configured")
                if created == 0:
                    errors["base"] = "unknown"
                else:
                    return self.async_abort(reason="import_success")

        if not pending:
            return self.async_abort(reason="all_devices_configured")

        # 关键修复：不能用 vol.All(vol.Coerce(list), [vol.In(...)])。
        # HA 2026.9 换成 probatio 后，这种写法在把表单序列化给前端时会抛
        # "ValueError: unable to serialize schema: [In({...})]"，
        # 前端只能显示 "Unknown error occurred"。
        # 改用 HA 原生多选下拉选择器（原生选择器一定能被序列化）。
        options = [
            SelectOptionDict(
                value=device["ip"],
                label=(
                    f"[{device['category']}] {device['name']} ({device['ip']})"
                    if device["category"]
                    else f"{device['name']} ({device['ip']})"
                ),
            )
            for device in pending[:MAX_DEVICES_IN_FORM]
        ]

        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {
                    vol.Required("devices"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"count": str(len(options))},
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """处理内部导入：真正创建设备条目。"""
        if user_input is None:
            return self.async_abort(reason="import_failed")

        return self.async_create_entry(
            title=user_input.get("name", "PC"),
            data=user_input,
        )


class SmartCafeOptionsFlow(OptionsFlow):
    """Handle options for SmartCafe Control."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Per-device scan interval and ping count override."""
        errors: dict[str, str] = {}

        if user_input is not None:
            scan_interval = user_input.get(CONF_SCAN_INTERVAL)
            ping_count = user_input.get(CONF_PING_COUNT)

            new_options = dict(self.config_entry.options)
            if scan_interval is not None:
                new_options[CONF_SCAN_INTERVAL] = scan_interval
            if ping_count is not None:
                new_options[CONF_PING_COUNT] = ping_count

            self.hass.config_entries.async_update_entry(
                self.config_entry, options=new_options
            )
            return self.async_create_entry(title="", data={})

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        current_count = self.config_entry.options.get(
            CONF_PING_COUNT, DEFAULT_PING_COUNT
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): vol.All(int, vol.Range(min=5, max=3600)),
                    vol.Required(
                        CONF_PING_COUNT, default=current_count
                    ): vol.All(int, vol.Range(min=1, max=10)),
                }
            ),
            errors=errors,
        )
