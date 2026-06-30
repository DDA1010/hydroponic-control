"""Core orchestration logic for HydroSYS.

The controller wraps the user's existing entities (pump, light, sensors) and
drives them: irrigation pulse cycling, light photoperiod, and all safety gates.
It never talks to hardware directly — it calls services on the configured
entities and reads their states, which keeps it hardware-agnostic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ALARM_DRY_RUN,
    ALARM_LEAK,
    ALARM_PUMP_FAULT,
    ALARM_SENSOR_FAULT,
    ALARM_WATER_TEMP,
    ALL_ALARMS,
    BLOCKING_ALARMS,
    CONF_AIR_TEMP_SENSOR,
    CONF_BLOCKED_RECHECK,
    CONF_DRY_RUN_DEBOUNCE,
    CONF_FAN_ON_OVERTEMP,
    CONF_FAN_SWITCH,
    CONF_FLOOR_LEAK_SENSOR,
    CONF_HEATER_ON_UNDERTEMP,
    CONF_HEATER_SWITCH,
    CONF_HUMIDITY_SENSOR,
    CONF_ILLUMINANCE_SENSOR,
    CONF_LIGHT_SWITCH,
    CONF_NOTIFY_SERVICE,
    CONF_PUMP_FAULT_DELAY,
    CONF_PUMP_MAX_RUNTIME,
    CONF_PUMP_POWER_SENSOR,
    CONF_PUMP_POWER_THRESHOLD,
    CONF_PUMP_SWITCH,
    CONF_SENSOR_TIMEOUT,
    CONF_SLOSH_GRACE,
    CONF_WATER_SENSOR,
    CONF_WATER_TEMP_SENSOR,
    CONF_WATER_WET_STATE,
    DEFAULT_BLOCKED_RECHECK,
    DEFAULT_DRY_RUN_DEBOUNCE,
    DEFAULT_LIGHT_OFF,
    DEFAULT_LIGHT_ON,
    DEFAULT_PUMP_FAULT_DELAY,
    DEFAULT_PUMP_MAX_RUNTIME,
    DEFAULT_PUMP_OFF_MINUTES,
    DEFAULT_PUMP_ON_MINUTES,
    DEFAULT_PUMP_POWER_THRESHOLD,
    DEFAULT_SENSOR_TIMEOUT,
    DEFAULT_SLOSH_GRACE,
    DEFAULT_WATER_TEMP_MAX,
    DEFAULT_WATER_TEMP_MIN,
    DEFAULT_WATER_WET_STATE,
    DOMAIN,
    EVENT_ALERT,
    EVENT_ALERT_CLEARED,
    MAINTENANCE_TIMEOUT_MINUTES,
    MODE_AUTO,
    MODE_MAINTENANCE,
    MODE_MANUAL,
    MODE_VACATION,
    PHASE_BLOCKED,
    PHASE_IDLE,
    PHASE_OFF,
    PHASE_ON,
    SETTING_IRRIGATION_ENABLED,
    SETTING_LIGHT_OFF,
    SETTING_LIGHT_ON,
    SETTING_MODE,
    SETTING_PUMP_OFF,
    SETTING_PUMP_ON,
    SETTING_TEMP_MAX,
    SETTING_TEMP_MIN,
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    STATUS_BLOCKED,
    STATUS_IDLE,
    STATUS_IRRIGATING,
    STATUS_MAINTENANCE,
    STATUS_WAITING,
)

_LOGGER = logging.getLogger(__name__)

_INVALID_STATES = (None, STATE_UNAVAILABLE, STATE_UNKNOWN, "")


@dataclass
class HydroSysData:
    """Snapshot of controller state consumed by read-only entities."""

    status: str = STATUS_IDLE
    pump_phase: str = PHASE_IDLE
    next_pump_change: datetime | None = None
    water_present: bool | None = None
    alarms: dict[str, bool] = field(default_factory=lambda: {a: False for a in ALL_ALARMS})

    @property
    def has_problem(self) -> bool:
        """Return True if any alarm is active."""
        return any(self.alarms.values())


class HydroSysController(DataUpdateCoordinator[HydroSysData]):
    """Orchestrates the hydroponics system from existing HA entities."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        """Initialise the controller."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=None,  # pure push, never polled
        )
        self.entry = entry
        self.data = HydroSysData()

        # Live, user-adjustable settings (owned by the control entities, which
        # push their restored/changed values in here).
        self.settings: dict[str, Any] = {
            SETTING_PUMP_ON: DEFAULT_PUMP_ON_MINUTES,
            SETTING_PUMP_OFF: DEFAULT_PUMP_OFF_MINUTES,
            SETTING_TEMP_MAX: DEFAULT_WATER_TEMP_MAX,
            SETTING_TEMP_MIN: DEFAULT_WATER_TEMP_MIN,
            SETTING_LIGHT_ON: _parse_time(DEFAULT_LIGHT_ON),
            SETTING_LIGHT_OFF: _parse_time(DEFAULT_LIGHT_OFF),
            SETTING_MODE: MODE_AUTO,
            SETTING_IRRIGATION_ENABLED: True,
        }

        self._alarms: dict[str, bool] = {a: False for a in ALL_ALARMS}
        self._phase: str = PHASE_IDLE
        self._next_change: datetime | None = None
        self._pump_started: datetime | None = None
        self._last_climate: tuple[bool, bool] | None = None

        # Cancel handles
        self._unsub_state: Any = None
        self._unsub_cycle: Any = None
        self._unsub_light: list[Any] = []
        self._unsub_fault: Any = None
        self._unsub_maxruntime: Any = None
        self._unsub_dryrun: Any = None
        self._unsub_maintenance: Any = None
        self._unsub_sensor_timeout: dict[str, Any] = {}

        self._started = False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def async_start(self) -> None:
        """Begin tracking source entities and run the control loops."""
        tracked = [
            self._conf(c)
            for c in (
                CONF_WATER_SENSOR,
                CONF_FLOOR_LEAK_SENSOR,
                CONF_WATER_TEMP_SENSOR,
                CONF_PUMP_POWER_SENSOR,
                CONF_PUMP_SWITCH,
            )
            if self._conf(c)
        ]
        if tracked:
            self._unsub_state = async_track_state_change_event(
                self.hass, tracked, self._handle_state_event
            )

        self._schedule_light_tracking()
        self._evaluate(initial=True)
        await self._apply_light_state()
        self._restart_cycle()
        self._started = True
        self._publish()

    async def async_stop(self) -> None:
        """Cancel every timer and listener (called on unload/reload)."""
        self._started = False
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None
        self._cancel(self._unsub_cycle)
        self._unsub_cycle = None
        self._cancel(self._unsub_fault)
        self._unsub_fault = None
        self._cancel(self._unsub_maxruntime)
        self._unsub_maxruntime = None
        self._cancel(self._unsub_dryrun)
        self._unsub_dryrun = None
        self._cancel(self._unsub_maintenance)
        self._unsub_maintenance = None
        for unsub in self._unsub_light:
            self._cancel(unsub)
        self._unsub_light = []
        for unsub in self._unsub_sensor_timeout.values():
            self._cancel(unsub)
        self._unsub_sensor_timeout = {}

    # ------------------------------------------------------------------ #
    # Public API used by control entities and services
    # ------------------------------------------------------------------ #
    def set_setting(self, key: str, value: Any) -> None:
        """Update a live setting and react to it."""
        if self.settings.get(key) == value:
            return
        self.settings[key] = value
        if not self._started:
            return
        if key in (SETTING_LIGHT_ON, SETTING_LIGHT_OFF):
            self._schedule_light_tracking()
            self.hass.async_create_task(self._apply_light_state())
        if key in (SETTING_MODE, SETTING_IRRIGATION_ENABLED):
            self._on_mode_or_enable_changed()
        elif key in (SETTING_PUMP_ON, SETTING_PUMP_OFF):
            self._restart_cycle()
        if key in (SETTING_TEMP_MAX, SETTING_TEMP_MIN):
            self._evaluate()
        self._publish()

    async def async_run_pump(self, minutes: float | None = None) -> None:
        """Run a single manual pulse, still honouring the safety gate."""
        if not self._gate_open():
            _LOGGER.warning("run_pump requested but safety gate is closed")
            return
        duration = (minutes if minutes is not None else self.settings[SETTING_PUMP_ON]) * 60
        await self._pump_on()
        self._phase = PHASE_ON
        self._schedule_cycle(duration)
        self._publish()

    @callback
    def async_reset_alarms(self) -> None:
        """Clear latched alarms (notably pump_fault) and try to resume."""
        for key in ALL_ALARMS:
            self._set_alarm(key, False, recompute=False)
        self._evaluate()
        self._restart_cycle()
        self._publish()

    # ------------------------------------------------------------------ #
    # Source state handling
    # ------------------------------------------------------------------ #
    @callback
    def _handle_state_event(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]

        if entity_id == self._conf(CONF_WATER_SENSOR):
            self._handle_water_change()
        elif entity_id == self._conf(CONF_PUMP_SWITCH):
            self._evaluate()
        else:
            # temp / leak / power
            self._evaluate()

        # A source recovering may re-open the gate -> resume promptly.
        self._maybe_resume()
        self._publish()

    @callback
    def _handle_water_change(self) -> None:
        present = self._is_water_present()
        if present is False:
            grace = self._opt(CONF_SLOSH_GRACE, DEFAULT_SLOSH_GRACE)
            if self._pump_started and (
                dt_util.utcnow() - self._pump_started
            ) < timedelta(seconds=grace):
                # Sloshing right after pump start — ignore briefly.
                return
            self._cancel(self._unsub_dryrun)
            debounce = self._opt(CONF_DRY_RUN_DEBOUNCE, DEFAULT_DRY_RUN_DEBOUNCE)
            self._unsub_dryrun = async_call_later(
                self.hass, debounce, self._confirm_dry_run
            )
        else:
            # Water present again — abort any pending dry-run confirmation.
            self._cancel(self._unsub_dryrun)
            self._unsub_dryrun = None
        self._evaluate()

    async def _confirm_dry_run(self, _now: datetime) -> None:
        self._unsub_dryrun = None
        if self._is_water_present() is not False:
            return  # recovered during debounce
        _LOGGER.warning("Dry-run confirmed — stopping pump")
        await self._pump_off()
        self._phase = PHASE_BLOCKED
        self._set_alarm(
            ALARM_DRY_RUN,
            True,
            severity=SEVERITY_CRITICAL,
            message="Reservoir empty — pump stopped (dry-run protection).",
        )
        self._publish()

    # ------------------------------------------------------------------ #
    # Safety evaluation
    # ------------------------------------------------------------------ #
    @callback
    def _evaluate(self, initial: bool = False) -> None:
        """Recompute level-based alarms from current source states."""
        # Dry-run (level based, immediate clear when water returns)
        present = self._is_water_present()
        if present is True and self._alarms[ALARM_DRY_RUN]:
            self._set_alarm(ALARM_DRY_RUN, False)
        elif present is False and initial:
            self._set_alarm(
                ALARM_DRY_RUN, True, SEVERITY_CRITICAL, "Reservoir empty at startup."
            )

        # Floor leak
        leak = self._is_on(self._conf(CONF_FLOOR_LEAK_SENSOR))
        if leak is not None:
            self._set_alarm(
                ALARM_LEAK,
                leak,
                SEVERITY_CRITICAL,
                "Water leak detected on the floor!",
            )

        # Water temperature window
        temp = self._float(self._conf(CONF_WATER_TEMP_SENSOR))
        if temp is not None:
            too_hot = temp > self.settings[SETTING_TEMP_MAX]
            too_cold = temp < self.settings[SETTING_TEMP_MIN]
            self._set_alarm(
                ALARM_WATER_TEMP,
                too_hot or too_cold,
                SEVERITY_WARNING,
                f"Water temperature out of range ({temp}°).",
            )
            # Only actuate fan/heater on a transition, not on every reading.
            if (too_hot, too_cold) != self._last_climate:
                self._last_climate = (too_hot, too_cold)
                self.hass.async_create_task(self._apply_climate(too_hot, too_cold))

        # Sensor-fault watchdogs for the safety-critical sources
        for conf_key in (CONF_WATER_SENSOR, CONF_WATER_TEMP_SENSOR):
            self._check_sensor_availability(self._conf(conf_key))

    @callback
    def _check_sensor_availability(self, entity_id: str | None) -> None:
        if not entity_id:
            return
        unavailable = self._is_unavailable(entity_id)
        if unavailable:
            if entity_id not in self._unsub_sensor_timeout:
                minutes = self._opt(CONF_SENSOR_TIMEOUT, DEFAULT_SENSOR_TIMEOUT)
                self._unsub_sensor_timeout[entity_id] = async_call_later(
                    self.hass, minutes * 60, self._sensor_timeout_factory(entity_id)
                )
            return
        # Recovered: cancel any pending timeout for this entity ...
        if entity_id in self._unsub_sensor_timeout:
            self._cancel(self._unsub_sensor_timeout.pop(entity_id))
        # ... and clear the (possibly latched) fault if nothing else is down.
        if self._alarms[ALARM_SENSOR_FAULT] and not self._any_critical_unavailable():
            self._set_alarm(ALARM_SENSOR_FAULT, False)

    @callback
    def _any_critical_unavailable(self) -> bool:
        return any(
            self._is_unavailable(self._conf(conf_key))
            for conf_key in (CONF_WATER_SENSOR, CONF_WATER_TEMP_SENSOR)
            if self._conf(conf_key)
        )

    @callback
    def _is_unavailable(self, entity_id: str | None) -> bool:
        if not entity_id:
            return False
        state = self.hass.states.get(entity_id)
        return state is None or state.state in _INVALID_STATES

    def _sensor_timeout_factory(self, entity_id: str):
        @callback
        def _fired(_now: datetime) -> None:
            self._unsub_sensor_timeout.pop(entity_id, None)
            self._set_alarm(
                ALARM_SENSOR_FAULT,
                True,
                SEVERITY_WARNING,
                f"Source sensor {entity_id} unavailable — failing safe.",
            )
            self._publish()

        return _fired

    @callback
    def _set_alarm(
        self,
        key: str,
        value: bool,
        severity: str = SEVERITY_WARNING,
        message: str = "",
        recompute: bool = True,
    ) -> None:
        if self._alarms[key] == value:
            return
        self._alarms[key] = value
        if value:
            self._fire_alert(key, severity, message)
        else:
            self.hass.bus.async_fire(
                EVENT_ALERT_CLEARED, {"entry_id": self.entry.entry_id, "alarm": key}
            )
        if recompute and value and key in BLOCKING_ALARMS:
            # A new blocking alarm must stop the pump now.
            self.hass.async_create_task(self._pump_off())
            self._phase = PHASE_BLOCKED

    # ------------------------------------------------------------------ #
    # Irrigation cycle state machine
    # ------------------------------------------------------------------ #
    @callback
    def _restart_cycle(self) -> None:
        self._cancel(self._unsub_cycle)
        self._unsub_cycle = None
        if not self._cycle_should_run():
            self.hass.async_create_task(self._pump_off())
            self._phase = PHASE_IDLE
            self._next_change = None
            return
        # Kick off immediately with an ON attempt.
        self._phase = PHASE_OFF
        self._schedule_cycle(0)

    @callback
    def _schedule_cycle(self, delay_seconds: float) -> None:
        self._cancel(self._unsub_cycle)
        self._next_change = dt_util.utcnow() + timedelta(seconds=delay_seconds)
        self._unsub_cycle = async_call_later(
            self.hass, max(delay_seconds, 0), self._cycle_step
        )

    async def _cycle_step(self, _now: datetime | None = None) -> None:
        self._unsub_cycle = None
        if not self._cycle_should_run():
            await self._pump_off()
            self._phase = PHASE_IDLE
            self._next_change = None
            self._publish()
            return

        if self._phase == PHASE_ON:
            # End of an ON pulse -> go to OFF wait.
            await self._pump_off()
            self._phase = PHASE_OFF
            self._schedule_cycle(self.settings[SETTING_PUMP_OFF] * 60)
        else:
            # Start of a pulse, if the gate allows it.
            if not self._gate_open():
                self._phase = PHASE_BLOCKED
                self._schedule_cycle(
                    self._opt(CONF_BLOCKED_RECHECK, DEFAULT_BLOCKED_RECHECK)
                )
                self._publish()
                return
            await self._pump_on()
            self._phase = PHASE_ON
            self._schedule_cycle(self.settings[SETTING_PUMP_ON] * 60)
        self._publish()

    @callback
    def _maybe_resume(self) -> None:
        """If we were blocked and the gate re-opened, retry promptly."""
        if self._phase == PHASE_BLOCKED and self._gate_open() and self._cycle_should_run():
            self._schedule_cycle(0)

    @callback
    def _on_mode_or_enable_changed(self) -> None:
        mode = self.settings[SETTING_MODE]
        self._cancel(self._unsub_maintenance)
        self._unsub_maintenance = None
        if mode == MODE_MAINTENANCE:
            # Everything off; auto-expire so safety is not left disabled.
            self.hass.async_create_task(self._all_off())
            self._unsub_maintenance = async_call_later(
                self.hass, MAINTENANCE_TIMEOUT_MINUTES * 60, self._maintenance_expired
            )
        else:
            # Re-assert the light photoperiod for the new mode.
            self.hass.async_create_task(self._apply_light_state())
        self._restart_cycle()

    @callback
    def _maintenance_expired(self, _now: datetime) -> None:
        self._unsub_maintenance = None
        if self.settings[SETTING_MODE] == MODE_MAINTENANCE:
            _LOGGER.info("Maintenance window expired — returning to auto")
            self.set_setting(SETTING_MODE, MODE_AUTO)

    # ------------------------------------------------------------------ #
    # Actuation
    # ------------------------------------------------------------------ #
    async def _pump_on(self) -> None:
        await self._turn(self._conf(CONF_PUMP_SWITCH), True)
        self._pump_started = dt_util.utcnow()
        # Pump-fault check: power must rise shortly after switching on.
        if self._conf(CONF_PUMP_POWER_SENSOR):
            self._cancel(self._unsub_fault)
            self._unsub_fault = async_call_later(
                self.hass,
                self._opt(CONF_PUMP_FAULT_DELAY, DEFAULT_PUMP_FAULT_DELAY),
                self._check_pump_fault,
            )
        # Max-runtime backstop against logic bugs.
        self._cancel(self._unsub_maxruntime)
        self._unsub_maxruntime = async_call_later(
            self.hass,
            self._opt(CONF_PUMP_MAX_RUNTIME, DEFAULT_PUMP_MAX_RUNTIME) * 60,
            self._max_runtime_exceeded,
        )

    async def _pump_off(self) -> None:
        self._cancel(self._unsub_fault)
        self._unsub_fault = None
        self._cancel(self._unsub_maxruntime)
        self._unsub_maxruntime = None
        self._pump_started = None
        await self._turn(self._conf(CONF_PUMP_SWITCH), False)

    async def _check_pump_fault(self, _now: datetime) -> None:
        self._unsub_fault = None
        power = self._float(self._conf(CONF_PUMP_POWER_SENSOR))
        threshold = self._opt(CONF_PUMP_POWER_THRESHOLD, DEFAULT_PUMP_POWER_THRESHOLD)
        if power is not None and power < threshold:
            _LOGGER.warning("Pump commanded on but no power draw (%.1f W)", power)
            await self._pump_off()
            self._phase = PHASE_BLOCKED
            self._set_alarm(
                ALARM_PUMP_FAULT,
                True,
                SEVERITY_CRITICAL,
                "Pump is on but drawing no power — possible blockage or failure.",
            )
            self._publish()

    async def _max_runtime_exceeded(self, _now: datetime) -> None:
        self._unsub_maxruntime = None
        _LOGGER.warning("Pump max runtime exceeded — forcing off")
        await self._pump_off()
        self._phase = PHASE_OFF
        self._schedule_cycle(self.settings[SETTING_PUMP_OFF] * 60)
        self._fire_alert(
            "max_runtime",
            SEVERITY_WARNING,
            "Pump ran longer than the configured maximum and was forced off.",
        )
        self._publish()

    async def _apply_climate(self, too_hot: bool, too_cold: bool) -> None:
        if self._opt(CONF_FAN_ON_OVERTEMP, True) and self._conf(CONF_FAN_SWITCH):
            await self._turn(self._conf(CONF_FAN_SWITCH), too_hot)
        if self._opt(CONF_HEATER_ON_UNDERTEMP, True) and self._conf(CONF_HEATER_SWITCH):
            await self._turn(self._conf(CONF_HEATER_SWITCH), too_cold)

    async def _all_off(self) -> None:
        await self._pump_off()
        for conf_key in (CONF_LIGHT_SWITCH, CONF_FAN_SWITCH, CONF_HEATER_SWITCH):
            if self._conf(conf_key):
                await self._turn(self._conf(conf_key), False)

    # ------------------------------------------------------------------ #
    # Light photoperiod
    # ------------------------------------------------------------------ #
    @callback
    def _schedule_light_tracking(self) -> None:
        for unsub in self._unsub_light:
            self._cancel(unsub)
        self._unsub_light = []
        if not self._conf(CONF_LIGHT_SWITCH):
            return
        on_t: time = self.settings[SETTING_LIGHT_ON]
        off_t: time = self.settings[SETTING_LIGHT_OFF]
        self._unsub_light.append(
            async_track_time_change(
                self.hass,
                self._light_on_fired,
                hour=on_t.hour,
                minute=on_t.minute,
                second=0,
            )
        )
        self._unsub_light.append(
            async_track_time_change(
                self.hass,
                self._light_off_fired,
                hour=off_t.hour,
                minute=off_t.minute,
                second=0,
            )
        )

    async def _light_on_fired(self, _now: datetime) -> None:
        if self._light_automation_active():
            await self._turn(self._conf(CONF_LIGHT_SWITCH), True)

    async def _light_off_fired(self, _now: datetime) -> None:
        if self._light_automation_active():
            await self._turn(self._conf(CONF_LIGHT_SWITCH), False)

    async def _apply_light_state(self) -> None:
        """Reconcile the light to the schedule (startup / setting change)."""
        if not self._conf(CONF_LIGHT_SWITCH) or not self._light_automation_active():
            return
        await self._turn(self._conf(CONF_LIGHT_SWITCH), self._is_light_time())

    @callback
    def _is_light_time(self) -> bool:
        on_t: time = self.settings[SETTING_LIGHT_ON]
        off_t: time = self.settings[SETTING_LIGHT_OFF]
        if on_t == off_t:
            return False  # equal times = schedule disabled
        now_t = dt_util.now().time()
        if on_t < off_t:
            return on_t <= now_t < off_t
        return now_t >= on_t or now_t < off_t  # crosses midnight

    @callback
    def _light_automation_active(self) -> bool:
        return self.settings[SETTING_MODE] in (MODE_AUTO, MODE_VACATION)

    # ------------------------------------------------------------------ #
    # Gates & helpers
    # ------------------------------------------------------------------ #
    @callback
    def _cycle_should_run(self) -> bool:
        return (
            self.settings[SETTING_MODE] in (MODE_AUTO, MODE_VACATION)
            and self.settings[SETTING_IRRIGATION_ENABLED]
        )

    @callback
    def _gate_open(self) -> bool:
        if any(self._alarms[a] for a in BLOCKING_ALARMS):
            return False
        present = self._is_water_present()
        if present is None and self._conf(CONF_WATER_SENSOR):
            return False  # fail safe: unknown level == do not pump
        return present is not False

    @callback
    def _is_water_present(self) -> bool | None:
        entity_id = self._conf(CONF_WATER_SENSOR)
        if not entity_id:
            return True  # no sensor configured -> cannot block
        state = self.hass.states.get(entity_id)
        if state is None or state.state in _INVALID_STATES:
            return None
        wet = self._opt(CONF_WATER_WET_STATE, DEFAULT_WATER_WET_STATE)
        return state.state == wet

    @callback
    def _is_on(self, entity_id: str | None) -> bool | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in _INVALID_STATES:
            return None
        return state.state == "on"

    @callback
    def _float(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in _INVALID_STATES:
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    async def _turn(self, entity_id: str | None, on: bool) -> None:
        if not entity_id:
            return
        await self.hass.services.async_call(
            "homeassistant",
            "turn_on" if on else "turn_off",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    @callback
    def _fire_alert(self, alarm: str, severity: str, message: str) -> None:
        _LOGGER.debug("HydroSYS alert [%s/%s]: %s", alarm, severity, message)
        self.hass.bus.async_fire(
            EVENT_ALERT,
            {
                "entry_id": self.entry.entry_id,
                "alarm": alarm,
                "severity": severity,
                "message": message,
            },
        )
        service = self._opt(CONF_NOTIFY_SERVICE, "")
        if service:
            domain, _, name = service.partition(".")
            if not name:
                domain, name = "notify", domain
            self.hass.async_create_task(
                self.hass.services.async_call(
                    domain,
                    name,
                    {"title": f"HydroSYS: {severity}", "message": message},
                    blocking=False,
                )
            )

    @callback
    def _publish(self) -> None:
        self.async_set_updated_data(
            HydroSysData(
                status=self._status(),
                pump_phase=self._phase,
                next_pump_change=self._next_change,
                water_present=self._is_water_present(),
                alarms=dict(self._alarms),
            )
        )

    @callback
    def _status(self) -> str:
        if self.settings[SETTING_MODE] == MODE_MAINTENANCE:
            return STATUS_MAINTENANCE
        if not self._cycle_should_run():
            return STATUS_IDLE
        if self._phase == PHASE_ON:
            return STATUS_IRRIGATING
        if self._phase == PHASE_OFF:
            return STATUS_WAITING
        if self._phase == PHASE_BLOCKED:
            return STATUS_BLOCKED
        return STATUS_IDLE

    # ------------------------------------------------------------------ #
    # Config/option accessors
    # ------------------------------------------------------------------ #
    def _conf(self, key: str) -> str | None:
        return self.entry.data.get(key)

    def _opt(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, default)

    @staticmethod
    def _cancel(unsub: Any) -> None:
        if unsub is not None:
            unsub()


def _parse_time(value: str | time) -> time:
    """Parse a 'HH:MM[:SS]' string (or pass through a time)."""
    if isinstance(value, time):
        return value
    parts = [int(p) for p in value.split(":")]
    while len(parts) < 3:
        parts.append(0)
    return time(parts[0], parts[1], parts[2])
