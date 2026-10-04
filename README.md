# SDC NTC emulator

A wireless room sensor for the **Honeywell Home (Resideo) Smile SDC** heating controller, without running a bus cable.

The Smile SDC normally regulates from the outdoor temperature only. Fed with a room temperature, it can also correct for the reference room ("room influence"). This board sits next to the controller and **emulates an NTC 20 kΩ room sensor (type RF 20)** on one of the SDC's variable inputs. The real room temperature comes over Wi-Fi from Home Assistant.

![PCB rev 4, top side](pcb/production/sdc-ntc-emulator-top.png)

```
 room sensor ──Wi-Fi──▶ Home Assistant ──ESPHome API──▶ ESP32-S3 ──I2C (isolated)──▶ AD5272 rheostat ──▶ SDC input VE1
                                                           │                         + 18.2 kΩ series
                                                           └── fail-safe relay: without power the SDC sees a fixed 24.9 kΩ
```

Main design points:
- **Galvanically isolated** from the SDC: an I2C isolator and an isolated DC/DC supply. So USB debugging is possible while the board is installed.
- **Fail-safe by hardware:** when the ESP32 is unpowered, crashed or rebooting, a non-latching relay connects a fixed resistor at the room setpoint. The controller then runs weather-compensated, as it did before, without a fault code.
- **Mains-free PCB:** 5 V from a USB-C charger or an external 5 V supply.

## Status

| Part | State |
|---|---|
| PCB | **rev 4 designed**: ERC/DRC clean, isolation gap ≥ 1.14 mm checked. **Not yet manufactured or tested.** |
| Firmware | **not written yet**, specified in the design notes |
| Field measurements | done on an SDC3-40PM, software V3.3: input VE1, bias voltage, measuring current, display offset |
| Open | DevKit clone USB diode check, SDC service-port pinout, firmware |

This is a work in progress. Treat the board as untested until a built and commissioned unit is reported here.

## ⚠ Safety

- The SDC carries **230 V** (burner, pumps, mixer) on terminals X7–X10. Connect **only** to the low-voltage sensor terminals: VE1 = X6-6, sensor GND = X5-2…12. **Never use X5-1**: that is the T2B data bus.
- Switch the controller off before opening it. Any mains wiring (only needed with a built-in supply such as the RAC03) must be done by a qualified person.
- Modifying the heating installation may affect its warranty. You do this at your own risk.

## Repository layout

| Path | Contents |
|---|---|
| [`docs/design-notes.md`](docs/design-notes.md) | The design record: measurements, circuit decisions, failure modes, firmware specification, SDC parameter setup |
| [`pcb/`](pcb/README.md) | KiCad 9 project, generator scripts, and production files (Gerbers, BOM, DigiKey/Mouser order files, schematic PDF) |
| [`firmware/`](firmware/README.md) | ESPHome firmware for the ESP32-S3 (pin map and plan; not written yet) |
| [`LICENSES/`](LICENSES) | Licence texts, see [Licence](#licence) |

## Building one

1. **Board:** upload `pcb/production/sdc-ntc-emulator-jlcpcb-gerbers.zip` to JLCPCB, or any other fab: 2 layers, 1.6 mm, standard rules. Check the points under ["Verify before ordering"](pcb/README.md#verify-before-ordering) first.
2. **Parts:** import `pcb/production/sdc-ntc-emulator-digikey-order-3x.csv` (DigiKey BOM Manager) or `…-mouser-order-3x.csv` (Mouser BOM Tool). Both are for 3 boards. Also needed: an **ESP32-S3-DevKitC-1 (N16R8)** on sockets, and a 5 V ≥ 2 A USB-C charger.
3. **Assembly and bench checks:** see [pcb/README.md](pcb/README.md#assembly). Everything is hand-solderable; the AD5272 (MSOP-10) is the only fine-pitch part.
4. **Firmware:** see [firmware/](firmware/README.md). Until it exists, the board keeps the relay off and the SDC sees the fixed fail-safe resistance.
5. **Controller setup:** assign the input (HYDRAULIC parameter 08 = 31 for mixed heating circuit 1), then enable room influence moderately. See ["Setup on the SDC controller"](docs/design-notes.md#setup-on-the-sdc-controller).

### Regenerating the KiCad files

The schematic, PCB and all production files are generated from `pcb/tools/design.py` by `pcb/tools/build.py`. This needs **KiCad 9.0** and Python 3. See ["How the files are made"](pcb/README.md#how-the-files-are-made) for the environment variables on non-Windows systems.

### Datasheets

The manuals and datasheets are copyrighted and **not included**. Get them from the manufacturers:
- Resideo SDC3-40PM: service manual EN2H-0221GE51, operating instructions EN2H-0220GE51, parameter list EN0B-0565GE51 (all R1020). The terminal plan is in the German product information GE0H-0405GE51.
- Analog Devices AD5272. Texas Instruments ISO1540 and ISO7721. Omron G5V-2. Gaptec 1S4E_1U. ST L78L05.
- Espressif ESP32-S3, ESP32-S3-WROOM-1, ESP32-S3-DevKitC-1 V1.1 schematic.
- Recom RAC03-SER/277, only if you use the built-in mains supply.

## Licence

- **Hardware** (`pcb/` except `pcb/tools/`, and `docs/`): [CERN-OHL-S-2.0](LICENSES/CERN-OHL-S-2.0.txt).
- **Software** (`pcb/tools/`, `firmware/`): [GPL-3.0-or-later](LICENSES/GPL-3.0-or-later.txt).

See [LICENSE](LICENSE) for details. Honeywell Home, Smile and Resideo are trademarks of their respective owners. This project is not affiliated with or endorsed by them.
