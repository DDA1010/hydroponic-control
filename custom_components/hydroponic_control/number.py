"""Number entities: user-adjustable pump timing and temperature limits."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HydroControlConfigEntry
from .const import (
    DEFAULT_PUMP_OFF_MINUTES,
    DEFAULT_PUMP_ON_MINUTES,
    DEFAULT_WATER_TEMP_MAX,
    DEFAULT_WATER_TEMP_MIN,
    MAX_PUMP_MINUTES,
    MAX_TEMP,
    MIN_PUMP_MINUTES,
    MIN_TEMP,
    SETTING_PUMP_OFF,
    SETTING_PUMP_ON,
    SETTING_TEMP_MAX,
    SETTING_TEMP_MIN,
)
from .controller import HydroController
from .entity import HydroSettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number entities."""
    controller = entry.runtime_data
    async_add_entities(
        [
            HydroNumber(
                controller, "pump_on_minutes", SETTING_PUMP_ON,
                DEFAULT_PUMP_ON_MINUTES, MIN_PUMP_MINUTES, MAX_PUMP_MINUTES, 0.1,
                unit=UnitOfTime.MINUTES,
            ),
            HydroNumber(
                controller, "pump_off_minutes", SETTING_PUMP_OFF,
                DEFAULT_PUMP_OFF_MINUTES, MIN_PUMP_MINUTES, MAX_PUMP_MINUTES, 0.1,
                unit=UnitOfTime.MINUTES,
            ),
            HydroNumber(
                controller, "water_temp_max", SETTING_TEMP_MAX,
                DEFAULT_WATER_TEMP_MAX, MIN_TEMP, MAX_TEMP, 0.5,
                unit=UnitOfTemperature.CELSIUS,
                device_class=NumberDeviceClass.TEMPERATURE,
            ),
            HydroNumber(
                controller, "water_temp_min", SETTING_TEMP_MIN,
                DEFAULT_WATER_TEMP_MIN, MIN_TEMP, MAX_TEMP, 0.5,
                unit=UnitOfTemperature.CELSIUS,
                device_class=NumberDeviceClass.TEMPERATURE,
            ),
        ]
    )


class HydroNumber(HydroSettingEntity, RestoreNumber):
    """A persisted, adjustable number that feeds a controller setting."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        controller: HydroController,
        key: str,
        setting_key: str,
        default: float,
        min_value: float,
        max_value: float,
        step: float,
        unit: str | None = None,
        device_class: NumberDeviceClass | None = None,
    ) -> None:
        """Initialise the number entity."""
        HydroSettingEntity.__init__(self, controller, key)
        self._setting_key = setting_key
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_native_value = default

    async def async_added_to_hass(self) -> None:
        """Restore the last value and seed the controller setting."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = last.native_value
        self.controller.set_setting(self._setting_key, self._attr_native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Handle a user changing the value."""
        self._attr_native_value = value
        self.controller.set_setting(self._setting_key, value)
        self.async_write_ha_state()
