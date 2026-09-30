# SDC NTC emulator PCB (rev 2)

KiCad 9 project for the wireless room sensor of the Smile SDC3-40PM, as described in
[HANDOFF_SDC_NTC_Emulator.md](../../HANDOFF_SDC_NTC_Emulator.md): ESP32-S3 DevKit on sockets,
ISO1540 I2C isolator, Traco TEM 2-0511 isolated supply, AD5272 digital rheostat, the
Omron G5V-2 fail-safe relay with state sense, and reverse-polarity protection on the 5 V input.
2 layers, 104 × 76 mm, 4 × M3 holes.

![top](production/sdc-ntc-emulator-top.png)

## Status

| Check | Result |
|---|---|
| ERC | 0 errors, 0 warnings |
| DRC (incl. schematic parity) | 0 violations, 0 unconnected pads |
| Isolation gap ESP ↔ SDC side (`tools/check_isolation.py`) | **≥ 1.15 mm** copper to copper, both layers (required ≥ 1.0 mm) |
| Gerbers + drill for JLCPCB | `production/sdc-ntc-emulator-jlcpcb-gerbers.zip` |
| BOM | `production/sdc-ntc-emulator-bom.csv` |

### Changes from rev 1 (independent review, 2026-09-30)

- **Isolation gap** 0.40 mm → 1.15 mm. Rev 1's documentation wrongly claimed ≥ 1 mm. Fixes:
  - oval TEM pads, 1.24 mm between +Vout and −Vin
  - ≥ 1.2 mm between the domain outlines
  - the router keeps whole tracks inside their domain
  - a new build check measures the real gap
- **Relay state sense** R11/R12 → GPIO5 (LOW = coil energised).
- **Reverse-polarity P-FET** Q2 in the 5 V input.
- **Resistors:**
  - R9 (R_series) 15.0 → 18.2 kΩ: floor ≈ 27 °C even with the AD5272 unpowered or shorted.
  - R10 (R_failsafe) 24.3 → 24.9 kΩ, which accounts for the SDC's +0.5 K offset.
  - R1/R2 4.7 → 2.7 kΩ: ISO1540 side-1 sink current.
- **Layout and footprints:**
  - C3/C5 moved next to the ISO1540 supply pins.
  - Relay holes 1.0 mm, as Omron recommends.
  - The AD5272 fan-out now has no wide tracks, no vias and no signal tracks under the body. A and VSS are tied to GND by a short trace under the body, under solder mask.
  - Silkscreen text ≥ 1.0 mm.
  - "GND X5-2..12" marking, because X5-1 is the SDC data bus.

## Verify before ordering

1. **DevKit row spacing: 25.1 mm** (`DEVKIT_ROWS` in `tools/make_pcb.py`, measured: outer 25.6 / inner 24.6 mm).
   - The pinout is confirmed from a photo: it is identical to the official DevKitC-1.
   - Solder the sockets with the DevKit plugged in.
   - The clone is ~56.6 × 27.7 mm. Its module antenna overhangs the DevKit edge by ~7 mm at the pin-1 end; the no-copper area covers that.
   - DevKit J3 pin 1 (GND) is intentionally not connected.
   - On the silkscreen the DevKit headers are "DK-J1"/"DK-J3", to tell them apart from the 5 V terminal J3.
2. **TEM 2-0511 footprint** (`lib/sdc_emulator.pretty`, self-made). It follows the datasheet: DIP-24 grid, 15.24 mm rows, only pins 1-3, 10-15 and 22-24, oval pads. Print 1:1 and hold the module against it.
3. **Terminal blocks.** The wire entries should face the board edge: J3 (5 V in) the top edge, J4 (to SDC) the right edge. This follows from KiCad's footprint graphics; confirm in the 3D view.
4. **R10 (R_failsafe) = 24.9 kΩ** assumes an SDC day setpoint of 21 °C (displayed). For another setpoint, pick the value from the NTC table in the handoff, taking the +0.5 K display offset into account. It is a through-hole part, so it is easy to swap.

## Ordering at JLCPCB (bare board, hand soldering)

Upload the zip. Defaults are fine: 2 layers, 1.6 mm FR-4, 1 oz copper, HASL or ENIG, any colour. No assembly service needed.

Smallest features, all within JLC's standard capabilities:
- **Clearance:** 0.13 mm, only inside the AD5272 MSOP-10 fan-out (pad gap 0.15 mm). Elsewhere ≥ 0.20 mm.
- **Tracks:** 0.25 mm.
- **Vias:** 0.8/0.4 mm, tented.

## Assembly

Order:
1. SMD first: U2 (MSOP-10) first, with flux and a fine tip; then U1, Q1, Q2, D1 and the 0805/1206 parts. C9 sits under the DevKit.
2. The low THT parts (R9, R10).
3. The sockets, relay, TEM, C1 and the terminals.

Notes:
- **R8 is DNP.** Fit it (≈ 270 Ω, 0.6 W) only if the TEM output measures > 5.4 V without load.
- **D2** lights when the isolated side has power.
- Relay K1: both poles are wired in parallel on purpose. Two gold contacts are more reliable at µA currents.
- **TEM pins 12/13** have a solid pour connection on both layers. Use a large tip and enough heat.
- **Before the first power-up, check with an ohmmeter:**
  - J4 VE1 to J4 GND = R10 (24.9 kΩ) with the relay off.
  - There must be no connection at all between the ESP side GND (J3 −) and the SDC side GND (J4 GND).
- **Wiring to the SDC:** J4 GND to **X5-2…12, never X5-1** (T2B data bus).

Not on the PCB: the ESP32-S3 DevKit, the RAC03 with its fuse and mains terminals (separate section of the enclosure), 4 × M3 spacers.

## Bench checks after assembly

- **TEM no-load output:** ≤ 5.4 V (only D2 as load). If higher, fit R8.
- **I2C on the ESP side:** look at SDA/SCL with a scope. The ISO1540's low level (≤ 0.8 V) is close to the ESP32-S3's VIL (0.825 V).
- **Relay sense:** GPIO5 must read HIGH with the relay off and LOW with it on.

## How the files are made

Everything is generated from `tools/design.py` (parts, values, footprints, nets) by:

```
python tools/build.py   # footprints -> schematic -> ERC -> netlist -> PCB -> DRC -> isolation check -> Gerbers/BOM/renders
```

- `tools/make_schematic.py`: writes `sdc-ntc-emulator.kicad_sch` from `design.py` (net labels at every pin).
- `tools/make_pcb.py` (runs in KiCad's Python): placement, routing, pours, keep-outs and silkscreen.
  - The router is a small grid A* router.
  - Each net is kept inside its own domain outline (ESP side or isolated SDC side), including half its track width.
  - The AD5272 fan-out is routed in a fixed order, with protected exit corridors for each 0.5 mm-pitch pin.
  - Placement lives in `PLACEMENT`, domain outlines in `ESP_POLY`/`ISO_POLY`.
- `tools/check_isolation.py` (KiCad Python): merges all copper of each domain per layer and measures the true minimum gap. The build fails below 1.0 mm.
- `tools/make_footprints.py`: the TEM 2 footprint.

**Rebuilding overwrites the `.kicad_sch` and `.kicad_pcb`.** Make changes in `design.py`/`make_pcb.py` and rebuild. If you prefer to continue by hand in KiCad, stop using the scripts from that point on, and run `check_isolation.py` after your edits.

**Known limitation:** `kicad-cli` ignores `sdc-ntc-emulator.kicad_dru`; even a deliberately broken rule gives no error. That is why:
- the global minimum clearance is 0.13 mm, needed for the MSOP-10 pad gaps;
- the isolation gap is checked by `check_isolation.py` instead of a DRC rule.
