"""Diagnostics support for HydroSYS."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import HydroSysConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HydroSysConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = entry.runtime_data
    return {
        "data": dict(entry.data),
        "options": dict(entry.options),
        "settings": {key: str(value) for key, value in controller.settings.items()},
        "state": {
            "status": controller.data.status,
            "pump_phase": controller.data.pump_phase,
            "water_present": controller.data.water_present,
            "next_pump_change": (
                controller.data.next_pump_change.isoformat()
                if controller.data.next_pump_change
                else None
            ),
            "alarms": controller.data.alarms,
        },
    }
