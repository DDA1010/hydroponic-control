"""Binary sensors: individual alarm states."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HydroControlConfigEntry
from .const import (
    ALARM_DRY_RUN,
    ALARM_LEAK,
    ALARM_PUMP_FAULT,
    ALARM_SENSOR_FAULT,
    ALARM_WATER_TEMP,
    CONF_FLOOR_LEAK_SENSOR,
    CONF_PUMP_POWER_SENSOR,
    CONF_WATER_SENSOR,
    CONF_WATER_TEMP_SENSOR,
)
from .controller import HydroController
from .entity import HydroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors that exist for the configured sources."""
    controller = entry.runtime_data
    data = entry.data

    entities: list[BinarySensorEntity] = []

    if data.get(CONF_WATER_SENSOR):
        entities.append(
            HydroAlarmSensor(controller, ALARM_DRY_RUN, BinarySensorDeviceClass.PROBLEM)
        )
        entities.append(
            HydroAlarmSensor(controller, ALARM_SENSOR_FAULT, BinarySensorDeviceClass.PROBLEM)
        )
    if data.get(CONF_WATER_TEMP_SENSOR):
        entities.append(
            HydroAlarmSensor(controller, ALARM_WATER_TEMP, BinarySensorDeviceClass.PROBLEM)
        )
    if data.get(CONF_PUMP_POWER_SENSOR):
        entities.append(
            HydroAlarmSensor(controller, ALARM_PUMP_FAULT, BinarySensorDeviceClass.PROBLEM)
        )
    if data.get(CONF_FLOOR_LEAK_SENSOR):
        entities.append(
            HydroAlarmSensor(controller, ALARM_LEAK, BinarySensorDeviceClass.MOISTURE)
        )

    async_add_entities(entities)


class HydroAlarmSensor(HydroEntity, BinarySensorEntity):
    """A single alarm condition exposed as a binary sensor."""

    def __init__(
        self,
        controller: HydroController,
        alarm_key: str,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialise the alarm sensor."""
        super().__init__(controller, alarm_key)
        self._alarm_key = alarm_key
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool:
        """Return whether this alarm is active."""
        return self.coordinator.data.alarms.get(self._alarm_key, False)
