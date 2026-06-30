"""Shared entity helpers for HydroSYS."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DEFAULT_NAME, DOMAIN, MANUFACTURER, MODEL
from .controller import HydroSysController


def hydrosys_device_info(entry) -> DeviceInfo:
    """Return the device that groups all HydroSYS entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or entry.data.get(CONF_NAME, DEFAULT_NAME),
        manufacturer=MANUFACTURER,
        model=MODEL,
    )


class HydroSysEntity(CoordinatorEntity[HydroSysController]):
    """Base for read-only entities driven by the controller's data."""

    _attr_has_entity_name = True

    def __init__(self, controller: HydroSysController, key: str) -> None:
        """Initialise a coordinator-backed entity."""
        super().__init__(controller)
        self.controller = controller
        self._attr_unique_id = f"{controller.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = hydrosys_device_info(controller.entry)


class HydroSysControlEntity(Entity):
    """Base for user-adjustable control entities (own their own value)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: HydroSysController, key: str) -> None:
        """Initialise a control entity."""
        self.controller = controller
        self._attr_unique_id = f"{controller.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = hydrosys_device_info(controller.entry)
