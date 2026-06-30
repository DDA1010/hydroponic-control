"""Sensors: system status, problem summary, and next pump transition."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HydroControlConfigEntry
from .const import (
    ALARM_DRY_RUN,
    ALARM_LEAK,
    ALARM_PUMP_FAULT,
    ALARM_SENSOR_FAULT,
    ALARM_WATER_TEMP,
    STATUS_BLOCKED,
    STATUS_IDLE,
    STATUS_IRRIGATING,
    STATUS_MAINTENANCE,
    STATUS_WAITING,
)
from .controller import HydroController
from .entity import HydroEntity

_STATUS_OPTIONS = [
    STATUS_IDLE,
    STATUS_IRRIGATING,
    STATUS_WAITING,
    STATUS_BLOCKED,
    STATUS_MAINTENANCE,
]

_PROBLEM_OK = "ok"
_ALARM_PRIORITY = [ALARM_LEAK, ALARM_DRY_RUN, ALARM_PUMP_FAULT, ALARM_WATER_TEMP, ALARM_SENSOR_FAULT]
_PROBLEM_OPTIONS = [_PROBLEM_OK] + _ALARM_PRIORITY


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the status sensors."""
    controller = entry.runtime_data
    async_add_entities(
        [
            HydroStatusSensor(controller),
            HydroProblemSensor(controller),
            HydroNextChangeSensor(controller),
        ]
    )


class HydroStatusSensor(HydroEntity, SensorEntity):
    """Human-readable system status with phase and alarm attributes."""

    _attr_icon = "mdi:sprout"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = _STATUS_OPTIONS

    def __init__(self, controller: HydroController) -> None:
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


class HydroProblemSensor(HydroEntity, SensorEntity):
    """Shows which alarm is currently active (or 'ok' when all clear)."""

    _attr_icon = "mdi:alert-circle"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = _PROBLEM_OPTIONS

    def __init__(self, controller: HydroController) -> None:
        """Initialise the problem sensor."""
        super().__init__(controller, "problem")

    @property
    def native_value(self) -> str:
        """Return the highest-priority active alarm, or 'ok'."""
        alarms = self.coordinator.data.alarms
        for alarm in _ALARM_PRIORITY:
            if alarms.get(alarm):
                return alarm
        return _PROBLEM_OK

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        """List all currently active alarms."""
        return {
            "active_alarms": [
                key for key, active in self.coordinator.data.alarms.items() if active
            ]
        }


class HydroNextChangeSensor(HydroEntity, SensorEntity):
    """Timestamp of the next pump on/off transition."""

    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: HydroController) -> None:
        """Initialise the next-change sensor."""
        super().__init__(controller, "next_pump_change")

    @property
    def native_value(self) -> datetime | None:
        """Return when the pump phase next changes."""
        return self.coordinator.data.next_pump_change
