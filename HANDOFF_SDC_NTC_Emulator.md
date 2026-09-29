# Handoff: Wireless Room Sensor for Honeywell Home Smile SDC via NTC Emulation

## Goal

A Honeywell Home (Resideo) Smile SDC heating controller currently operates purely weather-compensated (outdoor temperature). It should additionally take the living room temperature into account (room influence / room compensation) without running a bus cable.

Solution: An ESP32 at the controller emulates the resistance of an NTC 20k room sensor (type RF 20) on the room sensor input (variable input VE). The actual room temperature arrives via Wi-Fi from an existing Sonoff panel in the living room.

## Installed hardware

- Controller: **Honeywell Home Smile SDC3-40PM**, software **V3.3**. It controls only one mixer and a pump, i.e. **mixed heating circuit 1**.
- Power supply for the emulator: **Recom RAC03-05SER/277** (isolated AC/DC module, 5 V)
- Microcontroller: **ESP32-S3-DevKitC-1 clone with ESP32-S3-WROOM-1 N16R8** (16 MB flash, 8 MB PSRAM), two USB-C ports (USB-UART and native USB)
- Room temperature source: **SONOFF NSPanel-EU** (original NSPanel "Smart Scene Wall Switch", Wi-Fi, black, EAN 6920075776393; not the NSPanel Pro), in the living room, running custom ESPHome firmware and integrated in **Home Assistant**. It is ESP32-based with a Nextion display, two relays and a built-in temperature sensor.

Datasheets and manuals are kept locally in `datasheets/` (not in git, `*.pdf` is ignored). The authoritative SDC documents are the English Resideo set for the SDC3-40PM, revision R1020, valid for software V3.2:

| File | Document |
|---|---|
| `en2h0221-ge51.pdf` | Service manual EN2H-0221GE51 (261 pages; NTC 20 table in ch. 8.2.1, room influence in ch. 7.3.4) |
| `en2h0220-ge51.pdf` | Operating instructions EN2H-0220GE51 |
| `en0b0565-ge51.pdf` | Parameter list EN0B-0565GE51 |

The German `SDC_*.pdf` files (2006–2008) are older revisions and only kept for reference.

## Context from the preliminary discussion

- System: radiators **without room control valves**, hydraulically balanced. This suits room compensation well: the living room serves as the reference room, and the other rooms follow via the hydraulic balancing.
- Rejected options:
  - Wall module SDW10/SDW30 on the Smile bus (terminals A/B): no cable available.
  - Tunnelling the Smile bus wirelessly: proprietary, undocumented protocol, bus-powered wall modules, timing issues. Too much effort.
  - Smile Connect (SCN-10) + Smile Room Connect (SRC-10): intended for single-room control with wireless radiator valves, does not fit.
- Chosen: analog room sensor RF 20 on the variable input, emulated by an ESP32. Confirmed by the service manual (R1020): parameters 08/09/10 in the "Hydraulics" menu assign variable inputs VE1/VE2/VE3; setting value 30/31/32 = "Room sensor NTC 20" of the direct heating circuit / mixed heating circuit 1 / mixed heating circuit 2.
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
| ESP32-S3-DevKitC-1 (WROOM-1 N16R8) | Receives room temp., drives the rheostat | chosen board; powered via its 5V pin from the RAC03 |
| AD5272BRMZ-50 (or comparable) | digital rheostat, 50 kΩ, 1024 steps, I2C | ±1 % resistance tolerance, 50-TP memory for power-on value |
| Fixed resistor approx. 12–15 kΩ, 0.1 % | Offset so the range ~15–45 kΩ is covered | choose exact value from the NTC table |
| Recom RAC03-05SER/277 | Isolated AC/DC 5V supply for the ESP32 (chosen) | **galvanically isolated**, see Safety; 3 W / 600 mA, enough for ESP32 Wi-Fi peaks; mains side needs fusing and a proper enclosure |
| optional: I2C isolator (ISO1540) + isolated DC/DC | full isolation ESP32 ↔ controller | recommended if the input voltage doesn't suit the rheostat |
| Alternative: PhotoMOS relays + resistor ladder | fully isolated resistance emulation without rail issues | more parts, but robust |

### NTC 20 resistance (from service manual EN2H-0221GE51 R1020, ch. 8.2.1)

| °C | Ω | °C | Ω | °C | Ω |
|---|---|---|---|---|---|
| 10 | 41560 | 17 | 29303 | 24 | 20958 |
| 11 | 39500 | 18 | 27909 | 25 | 20000 |
| 12 | 37553 | 19 | 26590 | 26 | 19089 |
| 13 | 35714 | 20 | 25340 | 27 | 18224 |
| 14 | 33975 | 21 | 24155 | 28 | 17404 |
| 15 | 32331 | 22 | 23032 | 29 | 16624 |
| 16 | 30775 | 23 | 21967 | 30 | 15884 |

- The same NTC 20 curve applies to all VE inputs (and the outside/flow/tank sensors). The full table covers −50 … 130 °C.
- 10–30 °C therefore needs 15.9–41.6 kΩ. A series resistor of ~12–15 kΩ plus the 50 kΩ rheostat covers this.
- Slope around 20 °C is approx. 1.2 kΩ/K → AD5272 50k (≈ 49 Ω/step) gives approx. 0.04 K resolution.

## Safety & robustness (important)

1. **Measure first:** Determine the open-circuit voltage and measuring current at the VE terminals (controller on, sensor disconnected) with a multimeter. The voltage across the rheostat must stay within its supply range (0–5 V).
2. **Galvanic isolation:** Power the ESP32 only from an isolated power supply. When debugging via USB on a PC, a ground connection to the controller is created: only work with the controller switched off or with a USB isolator.
3. **No work on live mains.** The controller carries 230 V (burner, pumps, mixer). Connect only to the extra-low-voltage sensor terminals.
4. **Fail-safe:** If the temperature value from the panel is missing for longer than e.g. 10 minutes, output a neutral value (resistance corresponding to the room setpoint → room compensation makes no correction). Write the same value as the power-on default into the AD5272's 50-TP memory.
5. **Plausibility limits:** Clamp the output to e.g. 10–30 °C, smooth out jumps.
6. The modification may affect the controller's warranty/guarantee.

## Software tasks for Claude Code

1. **Connect the data source (decided: ESPHome + Home Assistant):** The panel publishes its room temperature to HA via ESPHome. The emulator runs ESPHome too and imports the value with the `homeassistant` sensor platform. The panel's own ESPHome API link is not used. The NSPanel's built-in sensor is known to read high from self-heating, but the reading on this panel has been checked and is correct.
2. **Temperature → resistance:** implement the NTC characteristic as a table with linear interpolation, or Steinhart-Hart/B parameter.
3. **Resistance → rheostat code:** `code = round((R_target − R_series − R_wiper) / (50k / 1024))`, clamped to 0–1023. AD5272: disable write protection (RDAC write protect) via the control register.
4. **Calibration:** provide an offset parameter, trimmed against the room temperature shown on the SDC.
5. **Watchdog/fail-safe** as above, incl. status message (e.g. "source lost") to HA/MQTT.
6. **Diagnostics:** publish current target resistance, code and last update as sensors.
7. Firmware framework (decided): **ESPHome** on the ESP32-S3. The AD5272 probably needs a small external component.

## Setup on the SDC controller

1. Assign the room sensor to the variable input in use: "Hydraulics" menu, parameter 08 (VE1), 09 (VE2) or 10 (VE3). Set it to **31 = room sensor NTC 20 of mixed heating circuit 1**, because the controller runs only one mixer and a pump.
2. In the "MIX.VALVE-1" menu:
   - Parameter 03 "Room connection" = 1 (room sensor active, operation active). Factory setting: OFF. Setting 3 only displays the room temperature without influence, useful for a first test.
   - Parameter 04 "Room factor" = influence in % (OFF, 10 … 500 %). Start **moderately**, e.g. 20–50 %, because the outdoor temperature remains the basis. Formula: corrected room setpoint = set room setpoint − deviation × room factor / 100.
3. Set up the heating curve properly beforehand; room compensation is only a fine correction.
4. In the living room: sensor/panel position away from sunlight, radiators, fireplace.

## Open points (clarify before starting)

- [x] Exact SDC model: SDC3-40PM
- [x] SDC software version: V3.3. The docs are written for V3.2; check parameter numbers on the device if anything differs.
- [x] Heating circuit: mixed heating circuit 1 (one mixer + pump), so VE setting 31.
- [x] Free VE inputs: all three (VE1–VE3) are free. **Use VE2 → parameter 09 = 31.** VE1 is kept free because it is the only input that can take a flue-gas sensor (AGF, PT1000).
- [ ] Measured open-circuit voltage / measuring current at the VE input? First readings (controller on, nothing connected): X5-6 → X6-6 ≈ 2 V, X5-7 → X6-7 ≈ −0.1 V, X5-8 → X6-8 ≈ −0.1 V. Still unknown: which of these pins is VE2 and which is sensor ground. The terminal plan is not in the three R1020 documents; check the label on the device or the installation instructions. Measuring current still to be determined, e.g. with a known resistor (20 kΩ) across the input: I = U / R.
- [x] Sonoff panel: NSPanel-EU (original NSPanel, Wi-Fi, black) with custom ESPHome firmware.
- [x] Home Assistant is available and is the data path.
- [x] HA entity: the panel appears in Home Assistant as **"Anzeige"**. Its temperature reading is available and checked as correct. For the ESPHome `homeassistant` sensor, look up the exact `entity_id` (e.g. `sensor.anzeige_…`) in HA.
- [x] Exact NTC 20k characteristic: see table above (10–30 °C). The full range is in the service manual, ch. 8.2.1.

---

*A German version of this document ([HANDOFF_SDC_NTC_Emulator.de.md](HANDOFF_SDC_NTC_Emulator.de.md)) is kept for reference but is outdated.*
