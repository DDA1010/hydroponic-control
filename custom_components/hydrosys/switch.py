"""Switch entity: master enable for the irrigation cycle (+ services)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HydroSysConfigEntry
from .const import (
    ATTR_MINUTES,
    SERVICE_RESET_ALARMS,
    SERVICE_RUN_PUMP,
    SETTING_IRRIGATION_ENABLED,
)
from .controller import HydroSysController
from .entity import HydroSysControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroSysConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the irrigation switch and register entity services."""
    async_add_entities([HydroSysIrrigationSwitch(entry.runtime_data)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RUN_PUMP,
        {vol.Optional(ATTR_MINUTES): vol.All(vol.Coerce(float), vol.Range(min=0.1))},
        "async_run_pump_service",
    )
    platform.async_register_entity_service(
        SERVICE_RESET_ALARMS,
        cv.make_entity_service_schema({}),
        "async_reset_alarms_service",
    )


class HydroSysIrrigationSwitch(HydroSysControlEntity, RestoreEntity, SwitchEntity):
    """Enables/disables the automatic irrigation cycle (user intent)."""

    _attr_icon = "mdi:water-sync"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, controller: HydroSysController) -> None:
        """Initialise the switch."""
        HydroSysControlEntity.__init__(self, controller, "irrigation")
        self._attr_is_on = True

    async def async_added_to_hass(self) -> None:
        """Restore the last state and seed the controller setting."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            self._attr_is_on = last.state == "on"
        self.controller.set_setting(SETTING_IRRIGATION_ENABLED, self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable irrigation."""
        self._attr_is_on = True
        self.controller.set_setting(SETTING_IRRIGATION_ENABLED, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable irrigation."""
        self._attr_is_on = False
        self.controller.set_setting(SETTING_IRRIGATION_ENABLED, False)
        self.async_write_ha_state()

    # -- entity services -------------------------------------------------- #
    async def async_run_pump_service(self, minutes: float | None = None) -> None:
        """Service: run a single manual pump pulse (gated by safety)."""
        await self.controller.async_run_pump(minutes)

    async def async_reset_alarms_service(self) -> None:
        """Service: clear latched alarms and attempt to resume."""
        self.controller.async_reset_alarms()
