"""Button entity: one-shot manual pump run (safety-gated)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HydroControlConfigEntry
from .controller import HydroController
from .entity import HydroSettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the manual pump-run button."""
    async_add_entities([HydroRunPumpButton(entry.runtime_data)])


class HydroRunPumpButton(HydroSettingEntity, ButtonEntity):
    """One-shot: run the pump for the configured on-time, honouring safety gates."""

    _attr_icon = "mdi:pump"

    def __init__(self, controller: HydroController) -> None:
        """Initialise the button."""
        HydroSettingEntity.__init__(self, controller, "run_pump")

    async def async_press(self) -> None:
        """Run one manual pulse (no-op + warning if the safety gate is closed)."""
        await self.controller.async_run_pump()
