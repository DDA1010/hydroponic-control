# Hydroponic Control — Hydroponics automation for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Issues](https://img.shields.io/github/issues/DDA1010/hydroponic-control.svg)](https://github.com/DDA1010/hydroponic-control/issues)

**Hydroponic Control** is a Home Assistant integration that turns your existing smart plugs and sensors into a fully automated hydroponic grow system — no YAML, no coding, configured entirely through the UI in minutes.

Whether you're running a **tower garden**, an **NFT channel**, a **DWC bucket**, or any other hydroponic setup, this integration handles the irrigation cycle, grow light photoperiod, water temperature management, and safety monitoring for you. It works with any hardware — Tuya, Zigbee, ESPHome, MQTT, or Wi-Fi — because it controls your existing Home Assistant entities rather than talking to hardware directly.

## Features

- **Irrigation cycle** — pump *x* minutes on / *y* minutes off, adjustable live.
- **Maintenance run** — a one-tap button runs the pump once for the configured on-time, still gated by safety (handy for maintenance/priming). The `run_pump` service does the same programmatically.
- **Light photoperiod** — on/off times that handle the midnight crossing and DST.
- **Dry-run protection** — the pump never runs when the reservoir is empty.
- **Pump fault detection** — verifies real power draw after switching on (needs a power sensor).
- **Water-temperature window** — alerts when too hot/cold, optionally drives a fan/heater.
- **Flood / leak detection**, **max-runtime backstop**, **sensor-unavailable watchdog** (fail-safe).
- **Operating modes** — Auto, Manual, Maintenance (auto-expiring), Vacation.
- **Notifications** — fires `hydroponic_control_alert` events and exposes a `Problem` binary sensor; can also call a notify service directly.

## Who is this for?

If you use Home Assistant to automate your home and want to extend that to your **hydroponic garden, grow room, or indoor growing setup**, this integration is the easiest way to do it. Instead of writing complex YAML automations for irrigation timing, grow light schedules, and safety shutoffs, Hydroponic Control handles all of that as a single, configurable integration with a proper UI.

It is especially useful for:
- **Tower gardens** (Lettuce Grow, Tower Garden, DIY PVC towers)
- **NFT (Nutrient Film Technique)** and **DWC (Deep Water Culture)** systems
- **Kratky** and other passive setups where you want light photoperiod control
- **Grow rooms** and **grow tents** where temperature monitoring and fan/heater control matters

## Requirements

- Home Assistant **2024.12** or newer.
- Existing entities for at least a **pump** (a `switch`, `input_boolean` or `light`).
  A **water/leak sensor** is strongly recommended (it powers the dry-run protection).

## Installation

### HACS (custom repository)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=DDA1010&repository=hydroponic-control&category=integration)

Oder manuell:

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
| `button.*_maintenance_run` | Manually run the pump once for the configured on-time (safety-gated) |
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
  - entity: button.hydroponic_control_maintenance_run
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

## Feedback & Support

Gefunden einen Bug oder eine Idee für eine neue Funktion?

- **[Bug melden](https://github.com/DDA1010/hydroponic-control/issues/new?template=bug_report.yml)**
- **[Feature vorschlagen](https://github.com/DDA1010/hydroponic-control/issues/new?template=feature_request.yml)**
- **[Fragen & Diskussion](https://github.com/DDA1010/hydroponic-control/discussions)**

## Disclaimer

Provided as-is (MIT). Hydroponics involves water and electricity near living
plants — test thoroughly, and keep an independent hardware safety where a failure
could cause damage.
