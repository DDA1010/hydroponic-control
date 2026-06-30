# HydroSYS — Architecture & Design Plan

Technical reference for contributors. User-facing docs are in [README.md](README.md).

---

## Ziel / Goal

Eine HACS-veröffentlichbare Home Assistant Custom Component, die **bestehende Entitäten** (Pumpe, Licht, Sensoren) zu einem hydroponischen Steuerungssystem zusammenführt — ohne eigene Hardware anzusprechen.

---

## Kernentscheidung: Orchestrator-Pattern

```
┌─────────────────────────────────────────────────────────┐
│                  Home Assistant                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │           HydroSYS Integration                   │   │
│  │  ┌─────────────┐   state_changed  ┌───────────┐ │   │
│  │  │  controller  │◄────────────────│  Source   │ │   │
│  │  │  (Coordinator)│                │  Entities │ │   │
│  │  │              │─turn_on/off────►│  (Pump,   │ │   │
│  │  └──────┬───────┘                 │  Light,   │ │   │
│  │         │ async_set_updated_data  │  Sensors) │ │   │
│  │  ┌──────▼───────────────────────┐ └───────────┘ │   │
│  │  │  HydroSYS Entitäten          │               │   │
│  │  │  (Status, Alarme, Steuerung) │               │   │
│  │  └──────────────────────────────┘               │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

Die Integration spricht **nie direkt Hardware an**. Sie liest Zustände vorhandener Entitäten und ruft `homeassistant.turn_on/off` auf ihnen auf. Dadurch funktioniert sie mit Zigbee, ESPHome, MQTT, Wi-Fi — egal.

---

## Datei-Übersicht

```
custom_components/hydrosys/
├── __init__.py          Setup/Unload, Plattform-Forwarding, Reload bei Options-Änderung
├── controller.py        Herzstück: Zustandsmaschine, Timer, Sicherheits-Gates (~550 LOC)
├── config_flow.py       UI-Einrichtung (Entitäten verknüpfen) + Options-Flow (Tuning)
├── const.py             Alle Konstanten, CONF_*, DEFAULT_*, Alarm-Keys
├── entity.py            Basisklassen: HydroSysEntity (read-only) + HydroSysControlEntity
├── number.py            Pump-Timings & Temperatur-Grenzen (RestoreNumber)
├── time.py              Licht-Ein/Aus-Zeiten (RestoreEntity + TimeEntity)
├── select.py            Betriebsmodus-Auswahl (RestoreEntity + SelectEntity)
├── switch.py            Master-Enable + Entity-Services (run_pump, reset_alarms)
├── binary_sensor.py     Problem-Sensor + einzelne Alarm-Sensoren
├── sensor.py            Status-Sensor (ENUM) + Next-Change-Sensor (TIMESTAMP)
├── diagnostics.py       async_get_config_entry_diagnostics für HA-Diagnose-Panel
├── manifest.json        Domain, Version, iot_class, HACS-Metadaten
├── strings.json         Übersetzungs-Keys (Quelle)
├── services.yaml        Service-Schema-Deklaration
└── translations/
    ├── en.json          Englische Texte (identisch mit strings.json)
    └── de.json          Deutsche Texte
```

---

## Controller — Lebenszyklus

```
async_setup_entry()
  │
  ├─ 1. HydroSysController() erstellen
  ├─ 2. async_forward_entry_setups()  ← Entitäten restoren & Controller seeden
  └─ 3. controller.async_start()      ← Loops starten (Sensoren tracken, Licht, Zyklus)

async_unload_entry()
  ├─ 1. controller.async_stop()       ← alle Timer canceln
  └─ 2. async_unload_platforms()
```

**Wichtig:** Schritt 2 muss vor Schritt 3 kommen. `RestoreNumber`/`RestoreEntity` setzen die gespeicherten Werte in `async_added_to_hass` — die Steuerung muss diese Werte kennen, bevor Loops starten.

---

## Bewässerungs-Zustandsmaschine

```
          ┌─────────────────────────────────────┐
          │             PHASE_IDLE              │ (Start / nach async_start)
          └──────────────┬──────────────────────┘
                         │ _restart_cycle()
                         ▼
          ┌──────────────────────────────────────┐
     ┌───►│  PHASE_OFF  (Pumpe aus, warte T_off) │
     │    └──────────────┬───────────────────────┘
     │                   │ Timer abgelaufen + _gate_open()
     │                   ▼
     │    ┌──────────────────────────────────────┐
     │    │  PHASE_ON   (Pumpe an, warte T_on)   │
     │    └──┬───────────────────────────────────┘
     │       │ Timer abgelaufen
     └───────┘

PHASE_BLOCKED: Gate geschlossen (Alarm aktiv / kein Wasser)
  → Pumpe sofort aus, recheck sobald Gate sich öffnet
```

`_gate_open()` gibt `False` zurück wenn:
- Ein BLOCKING_ALARM aktiv ist (`dry_run`, `pump_fault`, `leak`)
- Wassersensor konfiguriert, aber Zustand = None/unavailable

---

## Sicherheits-Modell

| Alarm | Blockiert Pumpe | Auslöser | Löschen |
|---|---|---|---|
| `dry_run` | ja | Wassersensor → leer (nach Debounce) | Sensor → voll |
| `leak` | ja | Lecksensor → nass | Sensor → trocken |
| `pump_fault` | ja | Kein Power-Draw nach Einschalten | `reset_alarms` Service |
| `water_temp` | nein | Temperatur außerhalb Fenster | Temp wieder OK |
| `sensor_fault` | nein | Sensor unavailable > Timeout | Sensor wieder verfügbar |

**Fail-safe Prinzip:** Unbekannter Zustand = Pumpe gesperrt (besser ausschalten als Trockenlauf).

### Trockenlauf-Schutz (Detail)
```
Wassersensor "leer"
  → Slosh-Grace (5s) abwarten  ← Wasserbeweegung nach Pumpenstart
    → Debounce-Timer (10s)
      → _confirm_dry_run(): noch leer?
        ja → ALARM_DRY_RUN setzen, Pumpe stoppen
        nein → ignorieren
```

---

## Licht-Steuerung

```python
# Mitternachts-Crossing korrekt behandelt:
def _is_light_time(on_t, off_t, now_t) -> bool:
    if on_t < off_t:
        return on_t <= now_t < off_t   # normaler Bereich (06:00–22:00)
    else:
        return now_t >= on_t or now_t < off_t  # über Mitternacht (22:00–06:00)
```

- `async_track_time_change` auf exakte Ein/Aus-Sekunde registriert
- Beim Start: sofortiger Reconcile (Licht in korrekten Zustand bringen)
- Nur aktiv in Modus `auto`

---

## Betriebsmodi

| Modus | Bewässerung | Licht | Besonderheit |
|---|---|---|---|
| `auto` | Automatik-Zyklus | Photoperiod | Normalbetrieb |
| `manual` | Gesperrt | Gesperrt | Nutzer steuert direkt |
| `vacation` | Gesperrt | Gesperrt | Komplett-Pause |
| `maintenance` | Gesperrt | Gesperrt | Auto-Ablauf nach 120 min → auto |

---

## Entitäten-Typen

### Steuer-Entitäten (persistiert via Restore*)
Besitzen ihre eigenen Werte, seeden den Controller beim Start:

| Entität | Klasse | Zweck |
|---|---|---|
| `number.pump_on_minutes` | RestoreNumber | Pumpe-An-Zeit (0.1–1440 min) |
| `number.pump_off_minutes` | RestoreNumber | Pumpe-Aus-Zeit |
| `number.water_temp_max` | RestoreNumber | Obere Temp-Grenze (°C) |
| `number.water_temp_min` | RestoreNumber | Untere Temp-Grenze |
| `time.light_on` | RestoreEntity | Licht-Einschalt-Zeit |
| `time.light_off` | RestoreEntity | Licht-Ausschalt-Zeit |
| `select.mode` | RestoreEntity | Betriebsmodus |
| `switch.irrigation` | RestoreEntity | Master-Enable |

### Status-Entitäten (read-only, vom Coordinator)
| Entität | Klasse | Zweck |
|---|---|---|
| `sensor.status` | SensorDeviceClass.ENUM | idle/running/blocked/alarm/vacation |
| `sensor.next_change` | SensorDeviceClass.TIMESTAMP | Nächste Pumpen-Zustandsänderung |
| `binary_sensor.problem` | — | Fasst alle aktiven Alarme zusammen |
| `binary_sensor.alarm_*` | je nach Typ | Ein Sensor pro konfiguriertem Alarm |

---

## Config Flow

**Schritt 1 — user:** Pflichtfeld (Pumpen-Entity) + optionale Felder (Licht, Sensoren, Notify-Service).

```python
# Keine default=None bei optionalen EntitySelectoren:
vol.Optional(CONF_WATER_SENSOR): _entity("binary_sensor")  # RICHTIG
# vol.Optional(CONF_WATER_SENSOR, default=None): ...        # FALSCH — HA lehnt None ab
```

**Schritt 2 — options (Options Flow):** Sicherheits-Tuning (Debounce-Zeiten, Fault-Check-Delay, Max-Laufzeit, etc.)

Änderungen in Options lösen `_async_update_listener` aus → Entry reload (frische Instanz).

---

## Entity Services

Registriert via `entity_platform.async_register_entity_service` im `switch.py`:

| Service | Target | Parameter | Effekt |
|---|---|---|---|
| `hydrosys.run_pump` | Switch-Entität | `minutes: float` (optional) | Pumpe manuell X Minuten |
| `hydrosys.reset_alarms` | Switch-Entität | — | Verriegelte Alarme zurücksetzen |

---

## Events

```yaml
# hydrosys_alert
event_type: hydrosys_alert
data:
  config_entry_id: "abc123"
  alarm: "dry_run"          # Key aus ALARM_* Konstanten
  message: "..."

# hydrosys_alert_cleared
event_type: hydrosys_alert_cleared
data:
  config_entry_id: "abc123"
  alarm: "dry_run"
```

---

## DataUpdateCoordinator (Push-only)

```python
super().__init__(
    hass, _LOGGER,
    name=DOMAIN,
    config_entry=entry,
    update_interval=None,   # kein Polling — nur push via async_set_updated_data()
)
```

Alle Entitäten abonnieren via `CoordinatorEntity`. Bei jeder Zustandsänderung ruft `_publish()` → `async_set_updated_data()` auf.

---

## Bekannte Bugs (behoben)

1. **Sensor-Fault-Alarm nicht löschend (latched):** Recovery-Pfad in `_check_sensor_availability` rief nie `_set_alarm(ALARM_SENSOR_FAULT, False)` auf. Fix: `_is_unavailable()` + `_any_critical_unavailable()` prüfen.

2. **Climate-Aktoren bei jeder Temperatur-Messung feuern:** `_apply_climate()` wurde bei jedem `state_changed`-Event aufgerufen. Fix: `_last_climate: tuple[bool, bool] | None = None` Cache — nur bei Zustandswechsel schalten.

3. **Licht-Reconcile nach Moduswechsel fehlte:** Wechsel von `maintenance` → `auto` stellte Licht nicht korrekt ein. Fix: `_apply_light_state()` im `else`-Branch von `_on_mode_or_enable_changed()`.

4. **Pump-Timing-Änderungen über falschen Pfad:** `SETTING_PUMP_ON/OFF` liefen durch `_on_mode_or_enable_changed()` mit unerwünschten Nebeneffekten. Fix: direkt `_restart_cycle()` aufrufen.

---

## Nächste Schritte

- [ ] Auf echter HA-Instanz testen (kopiere `custom_components/hydrosys/` nach `config/custom_components/`)
- [ ] `@dariobaio` und GitHub-URLs in `manifest.json` ersetzen
- [ ] GitHub-Repo erstellen + pushen → CI läuft automatisch (hassfest + HACS)
- [ ] Optionale Features: pH/EC-Monitoring, Auto-Nachfüll-Ventil, Energie-Statistiken

---

## CI/CD

`.github/workflows/validate.yaml` läuft bei jedem Push/PR:

```
hassfest   → prüft manifest.json, strings, services gegen HA-Standard
hacs       → prüft HACS-Kompatibilität (hacs.json, Ordnerstruktur)
```
