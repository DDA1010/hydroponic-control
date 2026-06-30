"""Select entity: the operating mode (auto/manual/maintenance/vacation)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HydroSysConfigEntry
from .const import MODE_AUTO, MODES, SETTING_MODE
from .controller import HydroSysController
from .entity import HydroSysControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroSysConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the mode select entity."""
    async_add_entities([HydroSysModeSelect(entry.runtime_data)])


class HydroSysModeSelect(HydroSysControlEntity, RestoreEntity, SelectEntity):
    """Operating mode for the whole system."""

    _attr_icon = "mdi:state-machine"
    _attr_options = MODES

    def __init__(self, controller: HydroSysController) -> None:
        """Initialise the select entity."""
        HydroSysControlEntity.__init__(self, controller, "mode")
        self._attr_current_option = MODE_AUTO

    async def async_added_to_hass(self) -> None:
        """Restore the last mode and seed the controller setting."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in MODES:
            self._attr_current_option = last.state
        self.controller.set_setting(SETTING_MODE, self._attr_current_option)

    async def async_select_option(self, option: str) -> None:
        """Handle a mode change."""
        self._attr_current_option = option
        self.controller.set_setting(SETTING_MODE, option)
        self.async_write_ha_state()
