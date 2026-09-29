# Handoff: Wireless Room Sensor for Honeywell Home Smile SDC via NTC Emulation

> **⏰ Pending checks (user):**
> 1. **DevKit diode check:** Are there Schottky diodes (1N5819 or similar) between each USB-C VBUS and the 5 V rail on the clone board? This decides whether USB and RAC03 may be connected at the same time.
>
> Details under [Open points](#open-points-clarify-before-starting).

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
| `en2h0221-ge51.pdf` | Service manual EN2H-0221GE51 (261 pages; NTC 20 table in ch. 8.2.1, room influence in ch. 7.3.4, fault codes in ch. 7.4) |
| `en2h0220-ge51.pdf` | Operating instructions EN2H-0220GE51 |
| `en0b0565-ge51.pdf` | Parameter list EN0B-0565GE51 |
| `SDC_Informationsschrift_ge0h-0405ge51r0603.pdf` | Product info (German, 2006); **terminal plan on PDF page 37** |

The other German `SDC_*.pdf` files (2006–2008) are older revisions and only kept for reference.

## Context from the preliminary discussion

- System: radiators **without room control valves**, hydraulically balanced. This suits room compensation well: the living room serves as the reference room, and the other rooms follow via the hydraulic balancing.
- Rejected options:
  - Wall module SDW10/SDW30 on the Smile bus (terminals A/B): no cable available.
  - Tunnelling the Smile bus wirelessly: proprietary, undocumented protocol, bus-powered wall modules, timing issues. Too much effort.
  - Smile Connect (SCN-10) + Smile Room Connect (SRC-10): intended for single-room control with wireless radiator valves, does not fit.
- Chosen: analog room sensor RF 20 on the variable input, emulated by an ESP32. Confirmed by the service manual (R1020): parameters 08/09/10 in the "Hydraulics" menu assign variable inputs VE1/VE2/VE3; setting value 30/31/32 = "Room sensor NTC 20" of the direct heating circuit / mixed heating circuit 1 / mixed heating circuit 2.
- The setpoint is set at the controller (not in the room). Possibly extendable later.

## Circuit (revision 3)

- **Revision 1 (first sketch)** connected the AD5272 directly to the SDC input. Its weak spot: if the ESP32 loses power, the SDC's measuring voltage reaches the unpowered AD5272 through its internal clamp diodes (datasheet: "power VDD first before applying any voltage to terminal A/W"). The SDC then reads an undefined, probably low resistance, i.e. a "very warm" room. With room influence active that throttles the heating, silently.
- **Revision 2** added a **fail-safe relay**: without power it connects a fixed resistor instead.
- **Revision 3** adds **galvanic isolation** between the ESP32 and the SDC side: an I2C isolator plus an isolated DC/DC for the AD5272. The relay's coil/contact gap forms the second crossing of the barrier. This makes USB flashing/debugging on a PC possible while installed, because PC earth no longer touches the SDC sensor ground. As a bonus, the isolator also level-shifts, so the AD5272 supply voltage is independent of the ESP32's 3V3.

```
  LIVING ROOM                       HOME ASSISTANT                 BOILER ROOM
 ┌────────────────┐   Wi-Fi     ┌─────────────────┐  ESPHome API  ┌──────────────────────┐
 │ NSPanel-EU     │ ──────────▶ │ entity "Anzeige"│ ────────────▶ │ ESP32-S3 DevKitC-1   │
 │ (ESPHome)      │             └─────────────────┘               └──────────────────────┘

            ESP DOMAIN (RAC03 secondary / USB / PC)  ┆  SDC DOMAIN (floating, referenced to X5 only)
                                                     ┆
 230 V ─ fuse ─▶ RAC03 ─ 5 V ─┬─▶ DevKit 5V pin      ┆
                              ├─▶ iso DC/DC in ══════╪═▶ TEM 2-0511  5V = VDD_ISO ─┬─▶ AD5272 VDD
                              │                      ┆                             └─▶ ISO1540 side 2
      DevKit 3V3 ─▶ ISO1540 side 1                   ┆
      GPIO8/9 SDA/SCL ─▶ ISO1540 ════════════════════╪═▶ SDA2/SCL2 ─▶ AD5272 (addr 0x2F)
                              └─▶ relay coil ◀─ MOSFET ◀─ GPIO4 "ENABLE" (pull-down)
                                   ║ (coil/contact isolation)
              ┌─ relay (SPDT, gold contacts) ────────────────────────────────────┐
 X6-6 (VE1) ──┤ COM                                                              │
              │   NO (energised) ── R_series 15.0 kΩ 0.1 % ── W ┤AD5272 50k├ A ──┼──┐
              │   NC (no power)  ── R_failsafe 24.3 kΩ 0.1 % ────────────────────┼──┤
              └──────────────────────────────────────────────────────────────────┘  │
 X5-x (GND) ──────────────────────────────────────────── GND_ISO (AD5272, ISO1540-2) ┘
```

**Isolation boundary:** Everything right of ┆ belongs to the SDC domain: iso DC/DC output, LDO, ISO1540 side 2, AD5272, both resistors, relay contacts. Its only reference is X5. Everything left of it may be earthed (PC via USB). Keep a few mm of gap between the domains on the board. This is functional isolation; safety isolation from mains is still the RAC03's job.

**Rejected: powering the AD5272 side from the SDC.** The SDC's only low-voltage supply is the T2B data bus: X6-1 (A) / X5-1 (B), "power supply via bus 12 V/150 mA" (service manual ch. 8.1), described as "data bus line 12 V AC" (ch. 2.2). It was not used because:
1. **Data rides on the supply.** The bus powers and talks to SDW wall devices over the same two wires. A rectifier with a buffer capacitor loads and distorts that signal, which risks fault 70-1 "No T2B signal" or disturbing the bus.
2. **Wrong reference.** The AD5272 rail must be referenced to the sensor ground X5-2…12, because terminal A sits at GND and A/W must stay between GND and VDD. T2B B (X5-1) is a separate terminal, and a rectified 12 V AC is not referenced to sensor ground. Fixing that needs an isolated converter again, so nothing is saved.
3. **Undocumented.** AC or DC, polarity, modulation and what is left for third parties are not specified.
4. **Little gain.** Its only advantage, an AD5272 that is always powered while the SDC measures, is already covered by the relay.

**Power-loss behaviour is unchanged:** the iso DC/DC and the relay coil both hang on the same 5 V. If it fails, the relay drops within ms and physically disconnects the AD5272, whatever its rail does.

### Why each part is there

- **AD5272 50k in rheostat mode (W–A):** 1024 steps of ≈ 49 Ω. The internal ±1 % tolerance calibration is on by default (control bit C2 = 0).
- **R_series 15.0 kΩ, 0.1 %:** The 50 kΩ rheostat alone could cover 15.9–41.6 kΩ, so the series resistor is **not strictly required**. It is kept for three reasons:
  1. **Hardware floor:** even at code 0 or a shorted rheostat, the SDC sees ≥ 15.0 kΩ ≈ 31 °C, never an absurd 60–100 °C.
  2. **Smaller absolute error:** at 20 °C the rheostat only provides 10.3 kΩ instead of 25.3 kΩ, so its ±1 % tolerance means ±0.1 K instead of ±0.2 K. The precise fixed resistor carries the rest.
  3. **Usable range:** 15.0–65.0 kΩ ≈ 31 °C … 2 °C, which covers the 10–30 °C plausibility window with margin.

  The first sketch said "12–15 kΩ". 15.0 kΩ (E24) is the better choice, because the floor then sits right at the upper plausibility limit.
- **Relay + R_failsafe 24.3 kΩ, 0.1 %:** Without coil power (ESP32 off, crashed, rebooting, or deliberately in fail-safe), the SDC sees a fixed **24.3 kΩ ≈ 20.9 °C**. Pick this to match the SDC day room setpoint, see the NTC table. The controller then sees "room = setpoint", so room influence makes no correction and it effectively runs weather-compensated as before. The rheostat is **physically disconnected**, so no back-powering. Use a signal relay with gold(-clad) contacts, since the contacts switch only µA ("dry circuit"). Examples: Panasonic TQ2-5V, Omron G6K-2F-Y 5VDC. Must be **non-latching**.
- **Why a fixed resistor rather than an open input:** An open or shorted room sensor gives SDC fault **20-0 / 20-1**, shown alternating with the basic display, and the manual does not document how the control behaves in that case. A fixed resistor at the setpoint is silent, defined and neutral.
- **MOSFET driver:** logic-level N-MOSFET (e.g. AO3400 / 2N7002), 100 kΩ gate pull-down, flyback diode (1N4148) across the coil. The pull-down keeps the relay off while the GPIO floats during boot.

### Bill of materials

| Part | Purpose | Note |
|---|---|---|
| ESP32-S3-DevKitC-1 (WROOM-1 N16R8) | Receives room temp., drives rheostat and relay | powered via its 5V pin from the RAC03 |
| AD5272BRMZ-50 (MSOP-10) + breakout board | digital rheostat, 50 kΩ, 1024 steps, I2C | needs 1 µF on EXT_CAP, 100 nF on VDD, RESET tied to VDD, ADDR → GND = I2C address 0x2F |
| Resistor 15.0 kΩ, 0.1 %, ≤ 25 ppm/K | R_series | |
| Resistor 24.3 kΩ, 0.1 % (E96) | R_failsafe | value = NTC resistance at the SDC day setpoint |
| **Omron G5V-2-H1 5VDC** (DPDT, both poles in parallel) | fail-safe switch-over | gold-alloy contacts, coil 30 mA / 167 Ω; Reichelt |
| N-MOSFET, 100 kΩ, 1N4148 | relay driver | |
| ISO1540 (TI) or ADuM1250 (ADI) | bidirectional I2C isolator | each side 3.0–5.5 V; 100 nF decoupling per side |
| Isolated DC/DC: **Traco TEM 2-0511** (user already owns it) | powers the SDC domain: VDD_ISO = 5 V for AD5272 + ISO1540 side 2 | 5 V ±10 % in, **regulated** 5 V ±3 % out, 400 mA, 1000 VDC isolation, DIP-24, PFM 80 kHz, ripple ≤ 50 mVpp, max. 470 µF load. End-of-life part. Load regulation is only specified from 10 % load (40 mA); ours is a few mA, so **measure the no-load output once**: must be ≤ 5.4 V for the AD5272 (5.5 V max). Add 10 µF + 100 nF at the AD5272. No LDO needed. |
| LED + 1.5 kΩ on VDD_ISO | "SDC domain powered" indicator | ~2 mA; always fitted |
| **Preload resistor 250 Ω / 0.5 W** (e.g. 2 × 1206 in parallel or 1 × THT) on VDD_ISO | preload the TEM 2-0511 (~20 mA = 100 mW) | **Footprint always present, fit only if needed:** if the no-load output is > 5.4 V or ripple is > 50 mVpp at assembly. Costs about +40 mA on the RAC03's 5 V (50 % efficiency), which matters for the tight budget. |
| 4 × 4.7 kΩ | I2C pull-ups on **both** sides of the isolator | ESP side to 3V3, SDC side to VDD_ISO |
| Electrolytic capacitor 470 µF / 10 V | 5 V bulk buffer for Wi-Fi current peaks | RAC03 allows up to 7500 µF |
| Ceramic capacitor 10 µF / 25 V X7R, 1206 (C9) | parallel to the elco: low ESR against RAC03 switching ripple and fast current edges | 25 V/1206 because of DC-bias derating; a film cap of 10 µF would be far too large |
| Recom RAC03-05SER/277 | isolated 5 V supply | see assessment below |
| Slow-blow fuse + in-line holder | mains-side protection | Recom recommends a slow-blow type |
| Wago lever terminals (mains), 2 × 2-pin PCB screw terminals (5 V in, SDC) | wiring | mains only on the Wago side, never on the PCB |
| Enclosure | | mains section and PCB section separated; strain relief |

### Digital rheostat: AD5272 vs. alternatives (reviewed 2026-09-29)

Requirements:
- ≥ 25 kΩ span, or ≥ 20 kΩ if the window is narrowed to 14–30 °C.
- Step ≤ ~120 Ω (≈ 0.1 K).
- Low tempco (the boiler room swings ±10 K).
- **Readback** of the set value (fail-safe check).
- Terminals usable from 0 V to the supply.
- I2C preferred, because it fits the ISO1540 isolator.

Absolute tolerance is less critical, since a one-time calibration can remove it.

| Part | Steps / span | Tolerance, tempco | Interface, readback | Package | Availability | Verdict |
|---|---|---|---|---|---|---|
| **AD5272BRMZ-50** | 1024 / 50 kΩ (49 Ω) | ±1 %, 5 ppm/K | I2C, yes | MSOP-10 (0.5 mm) | Mouser, DigiKey (both sell to private customers), possibly LCSC; **not Reichelt** | **Best fit, keep** |
| MCP4651-103 (dual 10 kΩ, both channels in series) | 2 × 256 / 20 kΩ (39 Ω) | ±20 % → calibrate each channel once; 50 ppm/K; wiper 75–160 Ω per channel | I2C, yes | TSSOP-14 (0.65 mm) | **Reichelt, ~€2** | **Fallback**. With R_series 15 kΩ the range is 15–35 kΩ ≈ 31 … 13.4 °C, OK for a living room. Needs a calibration routine. |
| AD5291BRUZ-20 | 256 / 20 kΩ (78 Ω) | ±1 % | SPI (the ISO1540 cannot isolate SPI; needs e.g. ADuM1401) | TSSOP-14 | Reichelt, ~€10 | Rejected: needs a 9–33 V supply plus a different isolator |
| MCP41050 | 256 / 50 kΩ (195 Ω ≈ 0.16 K) | ±20 %, **800 ppm/K** | SPI, no readback | DIP-8 | common | Rejected: coarse, drifts, no readback |
| X9C103/104 | 100 steps | ±20 %, 300 ppm/K | up/down, **no readback** | SO-8 / modules | everywhere (Amazon, Reichelt) | Rejected: no readback, coarse |
| MCP4018 boards (Soldered "DEBO DIGI", Reichelt) | 128 steps | ±20 % | I2C | module | Reichelt | Rejected: too coarse for the needed span |

**Decision:** Keep the AD5272. The ISO1540 is not a typical consumer-shop part either, so one Mouser/DigiKey (or LCSC) order covers AD5272 + ISO1540 + precision resistors. The MSOP-10 is the only fine-pitch part; it can be hand-soldered with flux and a fine tip, or put on an MSOP-10 adapter.

### PCB

**Designed (rev 1, 2026-09-29): [hardware/sdc-ntc-emulator/](hardware/sdc-ntc-emulator/README.md).**
- KiCad 9, 2 layers, 104 × 76 mm; ERC and DRC clean, schematic parity OK.
- JLC Gerber zip and BOM in `production/`, generated from `tools/design.py` by `tools/build.py`.
- Choices made during layout:
  - Relay **Omron G5V-2-H1 5VDC** with both poles **in parallel**: COM 4+13, NC 6+11, NO 8+9, coil 1/16, gold-alloy contacts, 30 mA coil.
  - That drops the optional relay-state readback (failure mode 8).
  - GPIO4 = relay, GPIO8/9 = I2C.
  - R_failsafe and R_series are THT 0.1 % parts, so they are easy to swap.
- Before ordering, check the points in the README: DevKit row spacing 25.4 mm and pinout, TEM footprint 1:1, terminal orientation, R10 value.

- **No mains on the PCB.** The RAC03-05SER/277 is a potted module (50.3 × 50.3 × 11 mm) with **flying leads** on input and output. It sits next to the PCB in the enclosure, fixed with a clip, strap or adhesive pad.
  - Its input leads go to a fused mains terminal (e.g. an in-line fuse holder with a slow-blow fuse + Wago lever terminals), in their own section of the enclosure.
  - Its output leads go to a 2-pin 5 V screw terminal on the PCB.
  - So the PCB is SELV only, and no 6 mm mains clearances are needed on it.
- **Own PCB from JLC (bare board, hand-soldered)** rather than perfboard, for clean isolation gaps:
  - Two zones: **ESP domain** and **SDC domain**.
  - A few mm gap across the ISO1540 / TEM 2-0511 / relay barrier, with no copper crossing it except through those parts.
- **Hand-soldering friendly:**
  - Passives 0805/1206; ISO1540 in SOIC-8; MOSFET in SOT-23.
  - Relay and TEM 2-0511 (DIP-24) through-hole.
  - AD5272 MSOP-10 is the only fine-pitch part (optionally with its footprint pads extended for easier soldering).
- DevKit on female headers (removable). Screw terminals: 5 V in (from RAC03), 2-pin to the SDC (X6-6 / X5).
- **Enclosure:**
  - Mains section (RAC03 input, fuse, terminals) separated from the PCB section, e.g. by a partition or at least clearly apart with fixed wiring.
  - Strain relief for the mains cable and the SDC cable.

### GPIO notes for the ESP32-S3 N16R8

- Avoid the strapping pins GPIO0, 3, 45 and 46.
- Avoid GPIO35–37, which are used by the octal PSRAM on R8 modules.
- Avoid GPIO19/20 (USB) and GPIO43/44 (UART0).
- **Used on the PCB:** I2C on GPIO8 (SDA) / GPIO9 (SCL), relay ENABLE on GPIO4. All are on DevKit header J1. Check against the clone's silkscreen.

### AD5272 supply voltage (settled by the VE1 measurement: U_max ≈ 1.7 V)

The voltage on terminals A/W must stay between GND and VDD. Worst case is the highest resistance: U_max = U0 × 65 kΩ / (65 kΩ + R_pull), with R_pull = 20 kΩ × (U0 / U20 − 1).
- **Decided: VDD_ISO = 5 V** from the Traco TEM 2-0511. That gives the most headroom. Measured: U_max ≈ 1.7 V, so it is confirmed with a wide margin.
- The ISO1540 handles the level shift to the ESP32's 3V3, so no extra level shifter is needed.

The measuring current is far below the AD5272's ±3 mA limit in any case: ≤ 5 V / 15 kΩ ≈ 0.3 mA.

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
- With R_series = 15.0 kΩ the rheostat covers 0.9 kΩ (30 °C, code ≈ 18) … 26.6 kΩ (10 °C, code ≈ 544). At 20 °C: 10.3 kΩ, code ≈ 212.
- Slope around 20 °C is approx. 1.2 kΩ/K → ≈ 49 Ω/step gives approx. 0.04 K resolution.
- The ±1 % per-code tolerance is only guaranteed above roughly code 0x078 (≈ 5.9 kΩ, i.e. below ≈ 24 °C). Above ≈ 24 °C the relative error grows, but the absolute error stays in the range of tens of Ω plus 35–70 Ω wiper resistance, i.e. < 0.1 K. Calibrate at the usual 20–22 °C.

### Power supply assessment: Recom RAC03-05SER/277

**Suitable, with caveats.**
- **Good:** 3 kVAC isolation, EN 60335-1 (household appliances) certified, leakage ≤ 10 µA, OVP and short-circuit protection, −40 … +75 °C at full load, 85–305 VAC input.
- **Current budget:** 600 mA at 5 V. ESP32-S3 Wi-Fi TX peaks ≈ 350–500 mA at 5 V incl. LDO losses, plus relay ~30 mA. That is enough, but not generous, so add the 470 µF bulk capacitor. Average draw ≈ 100 mA. Keep the DevKit's RGB LED off.
- **Obsolescence:** the datasheet says "not recommended for new designs, last time buy 31 Mar 2026". Fine for this one unit, but a replacement would be a different part: Mean Well IRM-05-5 (5 W, 1 A, more headroom) or a certified USB-C wall adapter if a socket is available in the boiler room.
- **Mains wiring (by a qualified person):** It is a potted module with flying leads, so it stays off the PCB (see PCB). It still needs a slow-blow input fuse, a closed enclosure and strain relief. Feed it from its own fused supply or socket. Do not tap the SDC's L/N terminals.
- **Isolation concept:** The RAC03 isolates from mains. The I2C isolator + iso DC/DC (revision 3) additionally separate the ESP32 from the SDC sensor ground.
- **Current budget with revision 3 (tight!):** The TEM 2-0511 draws **80 mA even without load**. Peak: ESP32-S3 Wi-Fi ≈ 350–500 mA + relay ≈ 30 mA + TEM 80 mA ≈ **460–610 mA vs. the RAC03's 600 mA**. Average ≈ 200 mA. The TX peaks are short and the RAC03's current limit only starts at 105–150 %, so this works, but only with the **470 µF bulk capacitor** (RAC03 allows up to 7500 µF; 1000 µF is also fine). Further headroom: disable Bluetooth, reduce ESPHome `wifi: output_power` (e.g. 15 dB), keep the RGB LED off. If the ESP32 shows brown-out resets: move to a Mean Well IRM-05-5 (1 A).

## Failure modes and fail-safe behaviour

| # | Scenario | Detection | Reaction | What the SDC sees |
|---|---|---|---|---|
| 1 | 5 V / ESP32 loses power | – (hardware) | relay drops within ms | 24.3 kΩ ≈ setpoint → no correction, no fault |
| 2 | ESP32 crash / hang | task watchdog → reset | GPIO resets low, relay drops during reboot | as 1 |
| 3 | Boot / power return | – | Relay stays off until: I2C OK, control reg. C1 set, RDAC written **and read back**, fresh valid temperature received. Then relay on. | as 1, then emulated value |
| 4 | Home Assistant or Wi-Fi down | ESPHome `api.connected` false > 10 min | relay off (fail-safe), log | as 1 |
| 5 | Panel offline / entity `unavailable` | HA sensor delivers NaN > 10 min | relay off | as 1 |
| 6 | Implausible value (< 10 °C, > 30 °C, jump > 2 K/min) | range/rate check | ignore sample; persistent → relay off | last good value, then as 1 |
| 7 | AD5272 fault (I2C NACK, readback ≠ written code) | check on every write, plus periodic readback e.g. every 5 min | relay off, report in HA | as 1 |
| 8 | Relay coil / driver open | not detected (the 2nd pole is used in parallel for contact reliability, no readback) | none needed | as 1 (safe direction) |
| 9 | Local heat in the living room (fireplace, sun) | – | optional: limit the emulated temperature to setpoint ± 3 K (setpoint as an HA `number`) | limited deviation, other rooms not undersupplied |
| 10 | USB flashing/debugging while installed | – | Allowed thanks to the isolator: PC earth only reaches the ESP domain. The official DevKitC-1 has a Schottky diode (1N5819) from each USB VBUS to the 5 V rail, so USB and RAC03 can be connected at the same time. **Verify these diodes on the clone** (near both USB-C ports) before doing so. | unaffected |
| 11 | Isolated rail fails (DC/DC or LDO) while relay is on | AD5272 I2C NACK / readback error | relay off (as 7) | as 1 |
| 12 | SDC reduced/night mode | – | none | R_failsafe matches only the day setpoint. At night the fail-safe reads "too warm", so the night setback gets a bit deeper. Acceptable. |

Notes:
- **Stale-value detection:** Do not use "no update for 10 min". HA only pushes a value when it changes, so a steady room temperature would trigger false alarms. Watch the connection state and NaN/`unavailable` instead.
- **Relay switching:** it happens only at boot and in fault cases. The brief open circuit during changeover lasts only milliseconds. If the SDC ever logs a fault 20-0 at that moment, a make-before-break contact or a parallel 10 nF capacitor is the remedy.
- **50-TP memory:** no longer needed for the fail-safe, since the relay handles it. **Do not program it.** Only 50 writes are possible, and the chip must not be written permanently by accident.
- The SDC's own frost protection stays active in every case.

## Safety

1. **No work on live mains.** The SDC carries 230 V (burner, pumps, mixer) on X7–X10. Connect only to the SELV sensor terminals X5/X6.
2. RAC03 mains wiring only by a qualified person (fuse, enclosure, clearances).
3. The modification may affect the controller's warranty/guarantee.

## Software tasks for Claude Code

1. **Connect the data source (decided: ESPHome + Home Assistant):** The panel publishes its room temperature to HA via ESPHome. The emulator runs ESPHome too and imports the value with the `homeassistant` sensor platform. The panel's own ESPHome API link is not used. The NSPanel's built-in sensor is known to read high from self-heating, but the reading on this panel has been checked and is correct.
2. **Temperature → resistance:** NTC table from above with linear interpolation. It is more exact than a B-parameter approximation.
3. **Resistance → rheostat code:** `code = round((R_target − R_series − R_wiper) / (50 kΩ / 1024))`, clamped to 0–1023. At every boot, write the control register with C1 = 1 (allow RDAC updates; command 7, data 0x002 → frame 0x1C02). Leave C2 = 0 (±1 % calibration on). Never set C0 (50-TP programming).
4. **Readback:** after every write and periodically, read back the RDAC and compare.
5. **Fail-safe state machine** as in the table above: relay ENABLE only when all conditions are met. Report a status to HA (`OK`, `FAILSAFE: source lost`, `FAILSAFE: AD5272 error`, …).
6. **Calibration:** provide an offset parameter (HA `number`), trimmed against the room temperature shown on the SDC.
7. **Diagnostics:** publish target resistance, code, relay state, last valid value and its age as sensors.
8. Firmware framework (decided): **ESPHome** on the ESP32-S3. The AD5272 needs a small external component (I2C, 16-bit command frames). Enable OTA from the start.

## Setup on the SDC controller

### Operating the SDC: technician level and parameters (service manual ch. 5.1.2.9 / 5.2)

Buttons (front panel, operating instructions ch. 4.1):
- Right column: ☀🌡 = "Daytime room temperature" (top), "Night-time room temperature" (middle), 🚰🌡 = "Daytime hot-water temperature" (bottom).
- Left column: "Manual mode", "Operating modes", "Switching time programs", **i** = "System information".
- Centre: rotary **input button** (turn / press).

Enter the technician code (**1234**):
1. Press **"Daytime room temperature" + "Daytime hot-water temperature"** simultaneously. The first code digit flashes.
2. Turn the input button to 1, press it. Then 2, press; 3, press; 4, press.
3. **Press and hold the input button > 3 s** to reach the menu-selection level (starts at TIME–DATE).

Change a parameter:
4. Turn to the menu (e.g. **HYDRAULIC**), press.
5. Turn to the parameter number (e.g. **09**), press. The value flashes.
6. Turn to the new value (e.g. **31**), **press to confirm**.
7. Back: **i** = one level up. The "Switching time programs" button, holding the input button > 3 s, or a timeout returns to the basic display.

**Never change HYDRAULIC parameter 01** ("Hydraulic schematic"). It redefines the whole application. Write down every value before you change it.

1. Assign the room sensor to VE1: "Hydraulics" menu, **parameter 08 = 31** (room sensor NTC 20 of mixed heating circuit 1, since the controller runs only one mixer and a pump). **Verified on the device 2026-09-29.** VE1 is the only working input on this SDC3-40PM.
2. In the "MIX.VALVE-1" menu:
   - Parameter 03 "Room connection" = 1 (room sensor active, operation active). Factory setting: OFF. Setting 3 only displays the room temperature without influence, useful for a first test.
   - Parameter 04 "Room factor" = influence in % (OFF, 10 … 500 %). Start **moderately**, e.g. 20–50 %, because the outdoor temperature remains the basis. Formula: corrected room setpoint = set room setpoint − deviation × room factor / 100.
3. Set up the heating curve properly beforehand; room compensation is only a fine correction.
4. In the living room: sensor/panel position away from sunlight, radiators, fireplace.

## Open points (clarify before starting)

- [x] Exact SDC model: SDC3-40PM
- [x] SDC software version: V3.3. The docs are written for V3.2; check parameter numbers on the device if anything differs.
- [x] Heating circuit: mixed heating circuit 1 (one mixer + pump), so VE setting 31.
- [x] **Input: VE1 (X6-6 → X5), parameter 08 = 31.** VE2/VE3 do not work on this SDC3-40PM (0 V, no bias); presumably not populated. VE1's extra flue-gas capability (AGF, PT1000) is not needed here.
- [x] **VE1 measured (2026-09-29).** Terminal plan (`SDC_Informationsschrift_ge0h-0405ge51r0603.pdf`, PDF page 37): **X5-1…12 are all sensor GND**; X6-6 = VE1, **X6-7 = VE2**, X6-8 = VE3. First readings (controller on, nothing connected, all VE parameters OFF):
  - VE1 (X6-6 → X5) ≈ 2 V
  - VE2 (X6-7 → X5) ≈ −0.1 V
  - VE3 (X6-8 → X5) ≈ −0.1 V

  **VE1 result with P08 = 31 and 20 kΩ connected:** **U20 = 1.3 V**; the SDC shows **25.5 °C** as room temperature (nominal 25.0 °C).
  - U0 ≈ 2.0 V is taken from the open-circuit reading above (P08 was still OFF then).
  - Measuring current I = 1.3 V / 20 kΩ ≈ **65 µA** (AD5272 limit ±3 mA).
  - Internal pull-up R_pull = 20 kΩ × (2.0 / 1.3 − 1) ≈ **10.8 kΩ** to ≈ 2 V.
  - Worst case U_max at 65 kΩ = 2.0 × 65 / 75.8 ≈ **1.7 V**; at 15 kΩ ≈ 1.2 V. Well below VDD_ISO = 5 V, so the supply question is settled.
  - The +0.5 K display offset: 25.5 °C corresponds to ≈ 19.5 kΩ, i.e. −2.5 %. The test resistor (2 × 10 kΩ) measured **20.0 kΩ** with a VC820 (meter tolerance ≈ ±0.8 %). So the offset is **on the SDC side**: either its input reads slightly high, or it displays the room temperature in coarse (e.g. 0.5 K) steps. It would apply to a real RF 20 sensor as well. The firmware calibration offset (software task 6) is set so that the SDC display matches the panel temperature. Expect roughly −0.5 K. It is tuned during commissioning, so no separate second-point test is planned.
  - VE2 (X6-7) stayed at 0 V with 20 kΩ; VE3 was not usable either.

  At commissioning: tune the offset against the panel, and check that the fail-safe state (relay off → 24.3 kΩ) shows ≈ 21 °C on the SDC.
- [ ] **⏰ PENDING (user): DevKit clone diode check.** The official ESP32-S3-DevKitC-1 (schematic in `datasheets/`) has a Schottky diode 1N5819 (D1, D7) from each USB-C VBUS to the 5 V rail. It blocks back-feed from the RAC03 into the PC. Check on the clone: look for a small diode (SOD-123, marking e.g. "S4"/"SL" or similar) next to each USB-C port. Alternatively measure with the multimeter in diode mode from the VBUS pin of each port to the 5V header pin: ~0.2–0.4 V in one direction and open in the other = diode present. **If missing:** unplug the RAC03 (or disconnect the 5 V pin) whenever USB is connected.
- [x] Isolated DC/DC: **Traco TEM 2-0511** (5 V → 5 V regulated, 2 W; datasheet `datasheets/TEM2_datasheet.pdf`). VDD_ISO = 5 V, no LDO. To do at assembly: measure its output with only the indicator LED as load: ≤ 5.4 V and ripple ≤ 50 mVpp. If not, fit the 250 Ω preload resistor and measure again.
- [ ] SDC day room setpoint? It determines the R_failsafe value (24.3 kΩ assumes 21 °C).
- [x] Sonoff panel: NSPanel-EU (original NSPanel, Wi-Fi, black) with custom ESPHome firmware.
- [x] Home Assistant is available and is the data path.
- [x] HA entity: the panel appears in Home Assistant as **"Anzeige"**. Its temperature reading is available and checked as correct. For the ESPHome `homeassistant` sensor, look up the exact `entity_id` (e.g. `sensor.anzeige_…`) in HA.
- [x] Exact NTC 20k characteristic: see table above (10–30 °C). The full range is in the service manual, ch. 8.2.1.

---

*A German version of this document ([HANDOFF_SDC_NTC_Emulator.de.md](HANDOFF_SDC_NTC_Emulator.de.md)) is kept for reference but is outdated.*
