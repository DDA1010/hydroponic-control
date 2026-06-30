"""Config and options flow for Hydroponic Control."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AIR_TEMP_SENSOR,
    CONF_BLOCKED_RECHECK,
    CONF_DRY_RUN_DEBOUNCE,
    CONF_FAN_ON_OVERTEMP,
    CONF_FAN_SWITCH,
    CONF_FLOOR_LEAK_SENSOR,
    CONF_HEATER_ON_UNDERTEMP,
    CONF_HEATER_SWITCH,
    CONF_HUMIDITY_SENSOR,
    CONF_ILLUMINANCE_SENSOR,
    CONF_LIGHT_SWITCH,
    CONF_NAME,
    CONF_NOTIFY_SERVICE,
    CONF_PUMP_FAULT_DELAY,
    CONF_PUMP_MAX_RUNTIME,
    CONF_PUMP_POWER_SENSOR,
    CONF_PUMP_POWER_THRESHOLD,
    CONF_PUMP_SWITCH,
    CONF_SENSOR_TIMEOUT,
    CONF_SLOSH_GRACE,
    CONF_WATER_SENSOR,
    CONF_WATER_TEMP_SENSOR,
    CONF_WATER_WET_STATE,
    DEFAULT_BLOCKED_RECHECK,
    DEFAULT_DRY_RUN_DEBOUNCE,
    DEFAULT_NAME,
    DEFAULT_PUMP_FAULT_DELAY,
    DEFAULT_PUMP_MAX_RUNTIME,
    DEFAULT_PUMP_POWER_THRESHOLD,
    DEFAULT_SENSOR_TIMEOUT,
    DEFAULT_SLOSH_GRACE,
    DEFAULT_WATER_WET_STATE,
    DOMAIN,
)

_ACTUATOR_DOMAINS = ["switch", "input_boolean", "light"]


def _entity(domain: str | list[str], device_class: str | None = None):
    """Build an optional entity selector."""
    cfg = selector.EntitySelectorConfig(domain=domain)
    if device_class:
        cfg["device_class"] = device_class
    return selector.EntitySelector(cfg)


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_PUMP_SWITCH): _entity(_ACTUATOR_DOMAINS),
            vol.Optional(CONF_WATER_SENSOR): _entity("binary_sensor"),
            vol.Optional(
                CONF_WATER_WET_STATE, default=DEFAULT_WATER_WET_STATE
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["on", "off"],
                    translation_key="water_wet_state",
                )
            ),
            vol.Optional(CONF_LIGHT_SWITCH): _entity(_ACTUATOR_DOMAINS),
            vol.Optional(CONF_FAN_SWITCH): _entity(_ACTUATOR_DOMAINS),
            vol.Optional(CONF_HEATER_SWITCH): _entity(_ACTUATOR_DOMAINS),
            vol.Optional(CONF_FLOOR_LEAK_SENSOR): _entity("binary_sensor"),
            vol.Optional(CONF_WATER_TEMP_SENSOR): _entity("sensor", "temperature"),
            vol.Optional(CONF_AIR_TEMP_SENSOR): _entity("sensor", "temperature"),
            vol.Optional(CONF_HUMIDITY_SENSOR): _entity("sensor", "humidity"),
            vol.Optional(CONF_ILLUMINANCE_SENSOR): _entity("sensor", "illuminance"),
            vol.Optional(CONF_PUMP_POWER_SENSOR): _entity("sensor", "power"),
        }
    )


def _positive_number(unit: str, mode: str = "box"):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, step=1, unit_of_measurement=unit, mode=selector.NumberSelectorMode(mode)
        )
    )


def _options_schema(options: dict[str, Any]) -> vol.Schema:
    """Schema for safety / advanced tuning."""

    def o(key: str, fallback: Any) -> Any:
        return options.get(key, fallback)

    return vol.Schema(
        {
            vol.Optional(
                CONF_NOTIFY_SERVICE, default=o(CONF_NOTIFY_SERVICE, "")
            ): selector.TextSelector(),
            vol.Optional(
                CONF_PUMP_POWER_THRESHOLD,
                default=o(CONF_PUMP_POWER_THRESHOLD, DEFAULT_PUMP_POWER_THRESHOLD),
            ): _positive_number("W"),
            vol.Optional(
                CONF_DRY_RUN_DEBOUNCE,
                default=o(CONF_DRY_RUN_DEBOUNCE, DEFAULT_DRY_RUN_DEBOUNCE),
            ): _positive_number("s"),
            vol.Optional(
                CONF_SLOSH_GRACE, default=o(CONF_SLOSH_GRACE, DEFAULT_SLOSH_GRACE)
            ): _positive_number("s"),
            vol.Optional(
                CONF_PUMP_FAULT_DELAY,
                default=o(CONF_PUMP_FAULT_DELAY, DEFAULT_PUMP_FAULT_DELAY),
            ): _positive_number("s"),
            vol.Optional(
                CONF_SENSOR_TIMEOUT, default=o(CONF_SENSOR_TIMEOUT, DEFAULT_SENSOR_TIMEOUT)
            ): _positive_number("min"),
            vol.Optional(
                CONF_PUMP_MAX_RUNTIME,
                default=o(CONF_PUMP_MAX_RUNTIME, DEFAULT_PUMP_MAX_RUNTIME),
            ): _positive_number("min"),
            vol.Optional(
                CONF_BLOCKED_RECHECK,
                default=o(CONF_BLOCKED_RECHECK, DEFAULT_BLOCKED_RECHECK),
            ): _positive_number("s"),
            vol.Optional(
                CONF_FAN_ON_OVERTEMP, default=o(CONF_FAN_ON_OVERTEMP, True)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_HEATER_ON_UNDERTEMP, default=o(CONF_HEATER_ON_UNDERTEMP, True)
            ): selector.BooleanSelector(),
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Drop empty optional fields so they are treated as 'not configured'."""
    return {k: v for k, v in user_input.items() if v not in (None, "")}


class HydroControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the existing entities to orchestrate."""
        if user_input is not None:
            data = _clean(user_input)
            return self.async_create_entry(
                title=data.get(CONF_NAME, DEFAULT_NAME), data=data
            )
        return self.async_show_form(step_id="user", data_schema=_user_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HydroControlOptionsFlow()


class HydroControlOptionsFlow(OptionsFlow):
    """Handle safety / advanced tuning after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=_clean(user_input))
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(dict(self.config_entry.options)),
        )
