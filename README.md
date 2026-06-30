# Hydroponic Control — Hydroponics controller for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Hydroponic Control turns the entities you **already have** (a pump plug, a grow-light plug,
a water/leak sensor, temperature sensors, …) into a complete, safety-first
hydroponics controller — configured entirely from the UI.

It is an **orchestrator**: it does not talk to hardware directly. It reads your
existing sensors and calls services on your existing switches, so it works with
any pump/light/sensor regardless of whether they are Zigbee, ESPHome, MQTT or
Wi-Fi.

## Features

- **Irrigation cycle** — pump *x* minutes on / *y* minutes off, adjustable live.
- **Light photoperiod** — on/off times that handle the midnight crossing and DST.
- **Dry-run protection** — the pump never runs when the reservoir is empty.
- **Pump fault detection** — verifies real power draw after switching on (needs a power sensor).
- **Water-temperature window** — alerts when too hot/cold, optionally drives a fan/heater.
- **Flood / leak detection**, **max-runtime backstop**, **sensor-unavailable watchdog** (fail-safe).
- **Operating modes** — Auto, Manual, Maintenance (auto-expiring), Vacation.
- **Notifications** — fires `hydroponic_control_alert` events and exposes a `Problem` binary sensor; can also call a notify service directly.

## Requirements

- Home Assistant **2024.12** or newer.
- Existing entities for at least a **pump** (a `switch`, `input_boolean` or `light`).
  A **water/leak sensor** is strongly recommended (it powers the dry-run protection).

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/DDA1010/hydroponic-control`, category **Integration**.
3. Install **Hydroponic Control**, then restart Home Assistant.

### Manual

Copy `custom_components/hydroponic_control` into your `config/custom_components/` folder and
restart Home Assistant.

## Setup

**Settings → Devices & Services → Add Integration → Hydroponic Control.**

Pick your entities. Only the pump is required.

> ⚠️ **Water-sensor polarity matters.** Choose correctly whether `on` or `off`
> means *water present*. If it is inverted, dry-run protection is inverted too —
> and the pump could run dry. Verify it on the device page before relying on it.

Safety/advanced values (notify service, debounce/grace times, power threshold,
watchdog timeouts, fan/heater behaviour) live under the integration's
**Configure** (options) dialog.

## Entities created

| Entity | Purpose |
|---|---|
| `select.*_mode` | Auto / Manual / Maintenance / Vacation |
| `switch.*_irrigation` | Master enable for the pump cycle |
| `number.*_pump_on_time` / `*_pump_off_time` | Pulse timing (minutes) |
| `number.*_water_temperature_max` / `*_min` | Temperature window |
| `time.*_light_on` / `*_light_off` | Photoperiod (only if a light is configured) |
| `sensor.*_status` | idle / irrigating / waiting / blocked / maintenance |
| `sensor.*_next_pump_change` | Timestamp of the next on/off transition |
| `binary_sensor.*_problem` | Any alarm active (great notification hook) |
| `binary_sensor.*_dry_run`, `*_pump_fault`, `*_water_temperature_alarm`, `*_sensor_fault`, `*_leak` | Individual alarms (created for the sources you configured) |

## Operating modes

- **Auto** — full automation (cycle + light + safety).
- **Manual** — automation paused; you control devices yourself. **Safety still applies.**
- **Maintenance** — everything off, alarms suppressed; auto-returns to Auto after 2 h.
- **Vacation** — like Auto, conservative.

## Services

- `hydroponic_control.run_pump` (optional `minutes`) — one manual pulse, still gated by safety.
- `hydroponic_control.reset_alarms` — clear latched alarms (e.g. a pump fault) and resume.

Both target the `switch.*_irrigation` entity.

## Notifications

Hydroponic Control fires bus events you can build any automation on:

- `hydroponic_control_alert` — `{ entry_id, alarm, severity, message }`
- `hydroponic_control_alert_cleared` — `{ entry_id, alarm }`

Example — push every critical alert to your phone:

```yaml
automation:
  - alias: Hydroponic Control critical alerts
    triggers:
      - trigger: event
        event_type: hydroponic_control_alert
        event_data:
          severity: critical
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "Hydroponic Control"
          message: "{{ trigger.event.data.message }}"
```

Or simply notify on the `Problem` binary sensor. (You can also set a notify
service in the options to have Hydroponic Control call it directly.)

## Example dashboard card

```yaml
type: entities
title: Hydroponic Control
entities:
  - entity: sensor.hydroponic_control_status
  - entity: select.hydroponic_control_mode
  - entity: switch.hydroponic_control_irrigation
  - entity: number.hydroponic_control_pump_on_time
  - entity: number.hydroponic_control_pump_off_time
  - entity: time.hydroponic_control_light_on
  - entity: time.hydroponic_control_light_off
  - entity: binary_sensor.hydroponic_control_problem
  - entity: sensor.hydroponic_control_next_pump_change
```

## Safety model

- Dry-run, leak and pump-fault are **blocking** alarms: the pump is stopped and
  will not start while they are active.
- An **unavailable** water sensor is treated as *not safe* — the pump is blocked
  and a sensor-fault alarm is raised after the configured timeout.
- The max-runtime timer is a backstop against logic bugs, independent of the
  normal pulse length.

## Roadmap

- pH / EC monitoring and dosing helpers
- Auto top-up valve control
- Runtime/energy statistics entities
- Night-time irrigation reduction

## Disclaimer

Provided as-is (MIT). Hydroponics involves water and electricity near living
plants — test thoroughly, and keep an independent hardware safety where a failure
could cause damage.
