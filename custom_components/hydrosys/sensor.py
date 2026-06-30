"""Sensors: system status and the next scheduled pump transition."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HydroSysConfigEntry
from .const import (
    STATUS_BLOCKED,
    STATUS_IDLE,
    STATUS_IRRIGATING,
    STATUS_MAINTENANCE,
    STATUS_WAITING,
)
from .controller import HydroSysController
from .entity import HydroSysEntity

_STATUS_OPTIONS = [
    STATUS_IDLE,
    STATUS_IRRIGATING,
    STATUS_WAITING,
    STATUS_BLOCKED,
    STATUS_MAINTENANCE,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroSysConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the status sensors."""
    controller = entry.runtime_data
    async_add_entities(
        [HydroSysStatusSensor(controller), HydroSysNextChangeSensor(controller)]
    )


class HydroSysStatusSensor(HydroSysEntity, SensorEntity):
    """Human-readable system status with phase and alarm attributes."""

    _attr_icon = "mdi:sprout"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = _STATUS_OPTIONS

    def __init__(self, controller: HydroSysController) -> None:
        """Initialise the status sensor."""
        super().__init__(controller, "status")

    @property
    def native_value(self) -> str:
        """Return the current status."""
        return self.coordinator.data.status

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose phase, water presence and alarm details."""
        data = self.coordinator.data
        return {
            "pump_phase": data.pump_phase,
            "water_present": data.water_present,
            **{f"alarm_{key}": value for key, value in data.alarms.items()},
        }


class HydroSysNextChangeSensor(HydroSysEntity, SensorEntity):
    """Timestamp of the next pump on/off transition."""

    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: HydroSysController) -> None:
        """Initialise the next-change sensor."""
        super().__init__(controller, "next_pump_change")

    @property
    def native_value(self) -> datetime | None:
        """Return when the pump phase next changes."""
        return self.coordinator.data.next_pump_change
