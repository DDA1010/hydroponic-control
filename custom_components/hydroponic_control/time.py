"""Time entities: light photoperiod start/end."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HydroControlConfigEntry
from .const import (
    CONF_LIGHT_SWITCH,
    DEFAULT_LIGHT_OFF,
    DEFAULT_LIGHT_ON,
    SETTING_LIGHT_OFF,
    SETTING_LIGHT_ON,
)
from .controller import HydroController, _parse_time
from .entity import HydroSettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the time entities (only when a light switch is configured)."""
    controller = entry.runtime_data
    if not entry.data.get(CONF_LIGHT_SWITCH):
        return
    async_add_entities(
        [
            HydroTimeEntity(
                controller, "light_on", SETTING_LIGHT_ON, _parse_time(DEFAULT_LIGHT_ON)
            ),
            HydroTimeEntity(
                controller, "light_off", SETTING_LIGHT_OFF, _parse_time(DEFAULT_LIGHT_OFF)
            ),
        ]
    )


class HydroTimeEntity(HydroSettingEntity, RestoreEntity, TimeEntity):
    """A persisted time-of-day that feeds the light schedule."""

    def __init__(
        self,
        controller: HydroController,
        key: str,
        setting_key: str,
        default: time,
    ) -> None:
        """Initialise the time entity."""
        HydroSettingEntity.__init__(self, controller, key)
        self._setting_key = setting_key
        self._attr_native_value = default

    async def async_added_to_hass(self) -> None:
        """Restore the last value and seed the controller setting."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (
            None,
            "",
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            try:
                self._attr_native_value = _parse_time(last.state)
            except (ValueError, IndexError):
                pass
        self.controller.set_setting(self._setting_key, self._attr_native_value)

    async def async_set_value(self, value: time) -> None:
        """Handle a user changing the time."""
        self._attr_native_value = value
        self.controller.set_setting(self._setting_key, value)
        self.async_write_ha_state()
