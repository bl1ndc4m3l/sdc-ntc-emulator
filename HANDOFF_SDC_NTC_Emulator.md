# Handoff: Wireless Room Sensor for Honeywell Home Smile SDC via NTC Emulation

## Goal

A Honeywell Home (Resideo) Smile SDC heating controller currently operates purely weather-compensated (outdoor temperature). It should additionally take the living room temperature into account (room influence / room compensation) without running a bus cable.

Solution: An ESP32 at the controller emulates the resistance of an NTC 20k room sensor (type RF 20) on the room sensor input (variable input VE). The actual room temperature arrives via Wi-Fi from an existing Sonoff panel in the living room.

## Installed hardware

- Controller: **Honeywell Home Smile SDC3-40PM**
- Power supply for the emulator: **Recom RAC03-05SER/277** (isolated AC/DC module, 5 V)

## Context from the preliminary discussion

- System: radiators **without room control valves**, hydraulically balanced. This suits room compensation well: the living room serves as the reference room, and the other rooms follow via the hydraulic balancing.
- Rejected options:
  - Wall module SDW10/SDW30 on the Smile bus (terminals A/B): no cable available.
  - Tunnelling the Smile bus wirelessly: proprietary, undocumented protocol, bus-powered wall modules, timing issues. Too much effort.
  - Smile Connect (SCN-10) + Smile Room Connect (SRC-10): intended for single-room control with wireless radiator valves, does not fit.
- Chosen: analog room sensor RF 20 on the variable input, emulated by an ESP32. According to the SDC installation manual, the room sensor is assigned to a variable input (e.g. VE1) via parameter 08, 09 or 10 in the "Hydraulics" menu.
- The setpoint is set at the controller (not in the room). Possibly extendable later.

## Hardware sketch

```
  LIVING ROOM                               BOILER ROOM
 ┌───────────────────┐                    ┌──────────────────────────────────────────┐
 │ Sonoff Panel      │                    │  Isolated 5V power supply                 │
 │ (temp. sensor +   │   Wi-Fi / MQTT /   │  (Recom RAC03-05SER/277)                  │
 │  display)         │ ─ HA / ESP-NOW ──▶ │        │ 5V                               │
 └───────────────────┘                    │        ▼                                  │
                                          │  ┌───────────┐  I2C   ┌──────────────┐    │
                                          │  │  ESP32    │───────▶│ AD5272 50k   │    │
                                          │  │ (3.3V)    │ SDA/SCL│ rheostat     │    │
                                          │  └───────────┘        │ 1024 steps   │    │
                                          │                       │ ±1 % toler.  │    │
                                          │                       └──┬────────┬──┘    │
                                          │                          │ W      │ A     │
                                          │                 R_series │        │       │
                                          │                  ~12–15k ┴        │       │
                                          │                          │        │       │
                                          └──────────────────────────┼────────┼───────┘
                                                                     │        │
                                                          ┌──────────┴────────┴───┐
                                                          │ SDC controller        │
                                                          │ terminals VEx / GND   │
                                                          │ (room sensor input)   │
                                                          └───────────────────────┘
```

### Bill of materials (proposal)

| Part | Purpose | Note |
|---|---|---|
| ESP32 DevKit | Receives room temp., drives the rheostat | any board |
| AD5272BRMZ-50 (or comparable) | digital rheostat, 50 kΩ, 1024 steps, I2C | ±1 % resistance tolerance, 50-TP memory for power-on value |
| Fixed resistor approx. 12–15 kΩ, 0.1 % | Offset so the range ~15–45 kΩ is covered | choose exact value from the NTC table |
| Recom RAC03-05SER/277 | Isolated AC/DC 5V supply for the ESP32 (chosen) | **galvanically isolated**, see Safety; 3 W / 600 mA, enough for ESP32 Wi-Fi peaks; mains side needs fusing and a proper enclosure |
| optional: I2C isolator (ISO1540) + isolated DC/DC | full isolation ESP32 ↔ controller | recommended if the input voltage doesn't suit the rheostat |
| Alternative: PhotoMOS relays + resistor ladder | fully isolated resistance emulation without rail issues | more parts, but robust |

### Resistance ballpark (NTC 20k, rough)

- 30 °C ≈ 16 kΩ, 25 °C = 20 kΩ, 20 °C ≈ 25 kΩ, 15 °C ≈ 31 kΩ, 10 °C ≈ 40 kΩ
- **These values are approximations.** Take the exact characteristic (table or B value) from the Honeywell documentation for the RF 20 / NTC 20k sensor.
- Slope around 20 °C approx. 1 kΩ/K → AD5272 50k (≈ 49 Ω/step) gives approx. 0.05 K resolution.

## Safety & robustness (important)

1. **Measure first:** Determine the open-circuit voltage and measuring current at the VE terminals (controller on, sensor disconnected) with a multimeter. The voltage across the rheostat must stay within its supply range (0–5 V).
2. **Galvanic isolation:** Power the ESP32 only from an isolated power supply. When debugging via USB on a PC, a ground connection to the controller is created: only work with the controller switched off or with a USB isolator.
3. **No work on live mains.** The controller carries 230 V (burner, pumps, mixer). Connect only to the extra-low-voltage sensor terminals.
4. **Fail-safe:** If the temperature value from the panel is missing for longer than e.g. 10 minutes, output a neutral value (resistance corresponding to the room setpoint → room compensation makes no correction). Write the same value as the power-on default into the AD5272's 50-TP memory.
5. **Plausibility limits:** Clamp the output to e.g. 10–30 °C, smooth out jumps.
6. The modification may affect the controller's warranty/guarantee.

## Software tasks for Claude Code

1. **Clarify and connect the data source** (see open points): receive the room temperature from the Sonoff panel, e.g. via
   - ESPHome + Home Assistant (preferred, if HA is available),
   - MQTT (e.g. with Tasmota on the panel),
   - ESP-NOW directly (if the panel is ESP32-based and freely programmable).
2. **Temperature → resistance:** implement the NTC characteristic as a table with linear interpolation, or Steinhart-Hart/B parameter.
3. **Resistance → rheostat code:** `code = round((R_target − R_series − R_wiper) / (50k / 1024))`, clamped to 0–1023. AD5272: disable write protection (RDAC write protect) via the control register.
4. **Calibration:** provide an offset parameter, trimmed against the room temperature shown on the SDC.
5. **Watchdog/fail-safe** as above, incl. status message (e.g. "source lost") to HA/MQTT.
6. **Diagnostics:** publish current target resistance, code and last update as sensors.
7. Firmware framework: ESPHome (AD5272 probably needs a small external component) or Arduino/PlatformIO. Decide once the data source is clarified.

## Setup on the SDC controller

1. Assign the room sensor to the variable input in use via parameter 08/09/10 in the "Hydraulics" menu (installation manual, chapter "Connecting room units").
2. Enable room influence/room compensation for the relevant heating circuit, set it **moderately** (outdoor temperature remains the basis).
3. Set up the heating curve properly beforehand; room compensation is only a fine correction.
4. In the living room: sensor/panel position away from sunlight, radiators, fireplace.

## Open points (clarify before starting)

- [x] Exact SDC model: SDC3-40PM
- [ ] SDC software version?
- [ ] Which VE input is free?
- [ ] Measured open-circuit voltage / measuring current at the VE input?
- [ ] Which Sonoff panel (NSPanel, NSPanel Pro, …) and which firmware (eWeLink, Tasmota, ESPHome)?
- [ ] Is there Home Assistant or an MQTT broker?
- [ ] Exact NTC 20k characteristic from Honeywell documentation.

---

*A German version of this document ([HANDOFF_SDC_NTC_Emulator.de.md](HANDOFF_SDC_NTC_Emulator.de.md)) is kept for reference but is outdated.*
