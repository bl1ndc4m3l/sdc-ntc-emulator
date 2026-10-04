# Firmware (ESP32-S3, ESPHome)

> **Status: not written yet.** The board is designed (see [../pcb/](../pcb/README.md)); the firmware is specified but not implemented. Until it exists, the board stays in its hardware fail-safe state: relay off, the SDC sees the fixed 24.9 kΩ.

The full requirements are in the [firmware specification](../docs/design-notes.md#firmware-specification) and the [failure-mode table](../docs/design-notes.md#failure-modes-and-fail-safe-behaviour) of the design notes. In short:

- Read the living-room temperature from Home Assistant (`homeassistant` sensor platform).
- Convert it to the NTC 20 resistance (table with linear interpolation) and then to an AD5272 code (R_series 18.2 kΩ in series).
- Write the AD5272, read it back, and only then switch the relay to the rheostat.
- Fall back to the relay-off state on any fault: source lost, implausible value, I2C error, or relay sense disagreeing with the drive.

## Target

| | |
|---|---|
| Board | ESP32-S3-DevKitC-1 (or pin-compatible clone), module ESP32-S3-WROOM-1 **N16R8** (16 MB flash, 8 MB octal PSRAM) |
| Framework | ESPHome, with a small external component for the AD5272 (I2C, 16-bit command frames) |
| OTA | enabled from the start |

## Pin map (PCB rev 4)

| GPIO | Function | Notes |
|---|---|---|
| 8 | I2C SDA | through the ISO1540 isolator; 2.7 kΩ pull-up on the board |
| 9 | I2C SCL | as SDA |
| 4 | relay ENABLE | output, `restore_mode: ALWAYS_OFF`; drives the relay MOSFET, which has a 100 kΩ gate pull-down |
| 5 | relay SENSE | input, **LOW = coil energised**, HIGH = off |
| 6 | SDC service port RX | 9600 baud, through the ISO7721; listen-only until the port is understood |
| 7 | SDC service port TX | leave unset in the UART config for now |
| 1, 2 | expansion header J6 | free (ADC1-capable, no strapping function) |

AD5272 at I2C address **0x2F**. At every boot, write the control register with C1 = 1 (frame `0x1C02`) before any RDAC write. **Never set C0** (50-TP programming): the part allows only 50 permanent writes.

Pins to avoid on the N16R8: strapping pins 0, 3, 45, 46; octal PSRAM pins 35–37; USB pins 19/20; UART0 pins 43/44.

## Planned layout

```
firmware/
  sdc-ntc-emulator.yaml        main ESPHome config
  components/ad5272/           external component (AD5272 driver)
  secrets.yaml.example         template, copy to secrets.yaml
```

Build and flash:

```
esphome run sdc-ntc-emulator.yaml
```

## Secrets

Wi-Fi credentials, the API encryption key and the OTA password go into `secrets.yaml` and are referenced with `!secret`. `secrets.yaml` and the `.esphome/` build folder are git-ignored. Never put credentials in the YAML itself.
