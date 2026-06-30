"""Constants for the Hydroponic Control integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "hydroponic_control"
MANUFACTURER: Final = "Hydroponic Control"
MODEL: Final = "Hydroponics Controller"

# ---------------------------------------------------------------------------
# Config entry keys (data) -> the existing entities the integration wraps
# ---------------------------------------------------------------------------
CONF_NAME: Final = "name"
CONF_PUMP_SWITCH: Final = "pump_switch"
CONF_LIGHT_SWITCH: Final = "light_switch"
CONF_FAN_SWITCH: Final = "fan_switch"
CONF_HEATER_SWITCH: Final = "heater_switch"

CONF_WATER_SENSOR: Final = "water_sensor"
CONF_WATER_WET_STATE: Final = "water_wet_state"  # which state means "water present"
CONF_FLOOR_LEAK_SENSOR: Final = "floor_leak_sensor"
CONF_WATER_TEMP_SENSOR: Final = "water_temp_sensor"
CONF_AIR_TEMP_SENSOR: Final = "air_temp_sensor"
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"
CONF_ILLUMINANCE_SENSOR: Final = "illuminance_sensor"
CONF_PUMP_POWER_SENSOR: Final = "pump_power_sensor"

# ---------------------------------------------------------------------------
# Config entry keys (options) -> advanced / safety tuning
# ---------------------------------------------------------------------------
CONF_NOTIFY_SERVICE: Final = "notify_service"
CONF_PUMP_POWER_THRESHOLD: Final = "pump_power_threshold"
CONF_DRY_RUN_DEBOUNCE: Final = "dry_run_debounce_seconds"
CONF_SLOSH_GRACE: Final = "slosh_grace_seconds"
CONF_PUMP_FAULT_DELAY: Final = "pump_fault_check_seconds"
CONF_SENSOR_TIMEOUT: Final = "sensor_unavailable_minutes"
CONF_PUMP_MAX_RUNTIME: Final = "pump_max_runtime_minutes"
CONF_BLOCKED_RECHECK: Final = "blocked_recheck_seconds"
CONF_FAN_ON_OVERTEMP: Final = "fan_on_overtemp"
CONF_HEATER_ON_UNDERTEMP: Final = "heater_on_undertemp"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_NAME: Final = "Hydroponic Control"
DEFAULT_WATER_WET_STATE: Final = "on"  # leak/level sensor: "on" == water present

DEFAULT_PUMP_ON_MINUTES: Final = 1.0
DEFAULT_PUMP_OFF_MINUTES: Final = 30.0
DEFAULT_WATER_TEMP_MAX: Final = 28.0
DEFAULT_WATER_TEMP_MIN: Final = 16.0
DEFAULT_LIGHT_ON: Final = "06:00:00"
DEFAULT_LIGHT_OFF: Final = "00:00:00"

DEFAULT_PUMP_POWER_THRESHOLD: Final = 5.0  # watts
DEFAULT_DRY_RUN_DEBOUNCE: Final = 10  # seconds
DEFAULT_SLOSH_GRACE: Final = 5  # seconds after pump start to ignore "dry"
DEFAULT_PUMP_FAULT_DELAY: Final = 10  # seconds after pump on to verify power draw
DEFAULT_SENSOR_TIMEOUT: Final = 15  # minutes a source may be unavailable
DEFAULT_PUMP_MAX_RUNTIME: Final = 30  # minutes hard ceiling for a single pulse
DEFAULT_BLOCKED_RECHECK: Final = 30  # seconds between retries while gate is blocked

# ---------------------------------------------------------------------------
# Bounds for number entities
# ---------------------------------------------------------------------------
MIN_PUMP_MINUTES: Final = 0.1
MAX_PUMP_MINUTES: Final = 1440.0
MIN_TEMP: Final = 0.0
MAX_TEMP: Final = 50.0

# ---------------------------------------------------------------------------
# Operating modes (select entity options / translation keys)
# ---------------------------------------------------------------------------
MODE_AUTO: Final = "auto"
MODE_MANUAL: Final = "manual"
MODE_MAINTENANCE: Final = "maintenance"
MODE_VACATION: Final = "vacation"
MODES: Final = [MODE_AUTO, MODE_MANUAL, MODE_MAINTENANCE, MODE_VACATION]

# Maintenance auto-expires so safety is never silently left off forever.
MAINTENANCE_TIMEOUT_MINUTES: Final = 120

# ---------------------------------------------------------------------------
# System status (sensor entity)
# ---------------------------------------------------------------------------
STATUS_OFF: Final = "off"
STATUS_IDLE: Final = "idle"
STATUS_IRRIGATING: Final = "irrigating"
STATUS_WAITING: Final = "waiting"
STATUS_BLOCKED: Final = "blocked"
STATUS_ALARM: Final = "alarm"
STATUS_MAINTENANCE: Final = "maintenance"

# Pump phase
PHASE_IDLE: Final = "idle"
PHASE_ON: Final = "on"
PHASE_OFF: Final = "off"
PHASE_BLOCKED: Final = "blocked"

# ---------------------------------------------------------------------------
# Alarm keys
# ---------------------------------------------------------------------------
ALARM_DRY_RUN: Final = "dry_run"
ALARM_WATER_TEMP: Final = "water_temp"
ALARM_PUMP_FAULT: Final = "pump_fault"
ALARM_SENSOR_FAULT: Final = "sensor_fault"
ALARM_LEAK: Final = "leak"
ALL_ALARMS: Final = [
    ALARM_DRY_RUN,
    ALARM_WATER_TEMP,
    ALARM_PUMP_FAULT,
    ALARM_SENSOR_FAULT,
    ALARM_LEAK,
]
# Alarms that block the pump from running.
BLOCKING_ALARMS: Final = [ALARM_DRY_RUN, ALARM_PUMP_FAULT, ALARM_LEAK]

# Severity for the alert event / notifications
SEVERITY_CRITICAL: Final = "critical"
SEVERITY_WARNING: Final = "warning"
SEVERITY_INFO: Final = "info"

# ---------------------------------------------------------------------------
# Events fired on the HA bus (users can build their own automations on these)
# ---------------------------------------------------------------------------
EVENT_ALERT: Final = "hydroponic_control_alert"
EVENT_ALERT_CLEARED: Final = "hydroponic_control_alert_cleared"

# ---------------------------------------------------------------------------
# Custom services
# ---------------------------------------------------------------------------
SERVICE_RUN_PUMP: Final = "run_pump"
SERVICE_RESET_ALARMS: Final = "reset_alarms"
ATTR_MINUTES: Final = "minutes"

# Internal setting keys (controller.settings)
SETTING_PUMP_ON: Final = "pump_on_minutes"
SETTING_PUMP_OFF: Final = "pump_off_minutes"
SETTING_TEMP_MAX: Final = "water_temp_max"
SETTING_TEMP_MIN: Final = "water_temp_min"
SETTING_LIGHT_ON: Final = "light_on"
SETTING_LIGHT_OFF: Final = "light_off"
SETTING_MODE: Final = "mode"
SETTING_IRRIGATION_ENABLED: Final = "irrigation_enabled"
