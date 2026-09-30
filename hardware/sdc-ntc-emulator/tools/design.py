"""Single source of truth for the SDC NTC emulator board.

Each part lists its schematic symbol, value, footprint, schematic position
and pin -> net mapping. make_schematic.py turns this into the .kicad_sch;
make_pcb.py places the footprints and reads the nets back from the netlist
that kicad-cli exports from that schematic.
"""

PROJECT = "sdc-ntc-emulator"

# Nets in the isolated SDC domain (everything else is the ESP domain).
ISO_NETS = {"VDD_ISO", "GND_ISO", "SDA_ISO", "SCL_ISO", "EXT_CAP", "WIPER",
            "NO_PATH", "NC_PATH", "VE1", "LED_ISO"}

FP_R0805 = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"
FP_R_THT = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
FP_TERM = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
FP_SOCKET = "Connector_PinSocket_2.54mm:PinSocket_1x22_P2.54mm_Vertical"


def part(ref, symbol, value, footprint, sch, pins, **fields):
    return dict(ref=ref, symbol=symbol, value=value, footprint=footprint,
                sch=sch, pins=pins, fields=fields)


# DevKit header J1 (official ESP32-S3-DevKitC-1 pinout, verified against the
# Espressif schematic V1.1). Only the pins below are used.
DEVKIT_J1 = {"1": "+3V3", "2": "+3V3", "4": "RELAY_EN", "5": "RELAY_SENSE", "12": "SDA_ESP",
             "15": "SCL_ESP", "21": "+5V", "22": "GND"}
# J3 pin 1 (GND, antenna end) is left open: it sits at the antenna keep-out edge.
DEVKIT_J3 = {"21": "GND", "22": "GND"}

PARTS = [
    # ---------------------------------------------------------------- ESP domain
    part("J1", "Connector:Conn_01x22_Socket", "DevKit J1", FP_SOCKET, (30.48, 76.2, 0),
         DEVKIT_J1, Description="ESP32-S3-DevKitC-1 header J1 (3V3/GPIO4/GPIO8/GPIO9/5V/GND)"),
    part("J2", "Connector:Conn_01x22_Socket", "DevKit J3", FP_SOCKET, (30.48, 160.02, 0),
         DEVKIT_J3, Description="ESP32-S3-DevKitC-1 header J3 (GND only, mechanical)"),
    part("J3", "Connector:Screw_Terminal_01x02", "5V IN (RAC03)", FP_TERM, (71.12, 35.56, 180),
         {"1": "+5V_IN", "2": "GND"}, Description="5 V from Recom RAC03-05SER/277 flying leads"),
    part("Q2", "Transistor_FET:AO3401A", "AO3401A", "Package_TO_SOT_SMD:SOT-23", (78.74, 60.96, 0),
         {"1": "GND", "2": "+5V", "3": "+5V_IN"},
         Description="Reverse-polarity protection: P-FET, gate to GND (Vgs max 12 V), ~25 mV drop"),
    part("C1", "Device:C_Polarized", "470uF 10V", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
         (88.9, 38.1, 0), {"1": "+5V", "2": "GND"}, Description="5 V bulk for Wi-Fi TX peaks"),
    part("C9", "Device:C", "10uF 25V X7R", "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder",
         (95.25, 38.1, 0), {"1": "+5V", "2": "GND"},
         Description="Low-ESR ceramic parallel to C1: RAC03 ripple, fast Wi-Fi current edges"),
    part("C2", "Device:C", "100nF", FP_C0805, (101.6, 38.1, 0), {"1": "+5V", "2": "GND"},
         Description="TEM 2-0511 input decoupling"),
    part("PS1", "sdc_emulator:TEM2-0511", "TEM 2-0511", "sdc_emulator:Traco_TEM2_Single_DIP24",
         (142.24, 45.72, 0),
         {"1": "+5V", "24": "+5V", "12": "GND", "13": "GND",
          "11": "VDD_ISO", "14": "VDD_ISO", "10": "GND_ISO", "15": "GND_ISO"},
         Description="Traco TEM 2-0511 isolated DC/DC 5 V -> 5 V, 1000 VDC"),
    part("U1", "Isolator:ISO1540", "ISO1540", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
         (142.24, 114.3, 0),
         {"1": "+3V3", "2": "SDA_ESP", "3": "SCL_ESP", "4": "GND",
          "5": "GND_ISO", "6": "SCL_ISO", "7": "SDA_ISO", "8": "VDD_ISO"},
         Description="Bidirectional I2C isolator"),
    part("C3", "Device:C", "100nF", FP_C0805, (106.68, 111.76, 0), {"1": "+3V3", "2": "GND"},
         Description="U1 VCC1 decoupling"),
    part("R1", "Device:R", "2k7", FP_R0805, (116.84, 101.6, 0), {"1": "+3V3", "2": "SDA_ESP"},
         Description="I2C pull-up ESP side (>= 0.5 mA sink current for ISO1540 side 1)"),
    part("R2", "Device:R", "2k7", FP_R0805, (124.46, 101.6, 0), {"1": "+3V3", "2": "SCL_ESP"},
         Description="I2C pull-up ESP side (>= 0.5 mA sink current for ISO1540 side 1)"),
    part("R11", "Device:R", "10k", FP_R0805, (116.84, 198.12, 0), {"1": "COIL_N", "2": "RELAY_SENSE"},
         Description="Relay sense divider: GPIO5 LOW = coil energised"),
    part("R12", "Device:R", "20k", FP_R0805, (124.46, 198.12, 0), {"1": "RELAY_SENSE", "2": "GND"},
         Description="Relay sense divider (5 V -> 3.3 V)"),
    part("R4", "Device:R", "100R", FP_R0805, (76.2, 185.42, 90), {"1": "RELAY_EN", "2": "GATE"},
         Description="Gate series resistor"),
    part("R3", "Device:R", "100k", FP_R0805, (88.9, 193.04, 0), {"1": "GATE", "2": "GND"},
         Description="Gate pull-down: relay off while GPIO4 floats"),
    part("Q1", "Transistor_FET:AO3400A", "AO3400A", "Package_TO_SOT_SMD:SOT-23",
         (101.6, 185.42, 0), {"1": "GATE", "2": "GND", "3": "COIL_N"},
         Description="Relay coil driver"),
    part("D1", "Diode:1N4148W", "1N4148W", "Diode_SMD:D_SOD-123", (114.3, 165.1, 90),
         {"1": "+5V", "2": "COIL_N"}, Description="Flyback diode"),
    part("K1", "Relay:G5V-2", "G5V-2-H1 5VDC", "Relay_THT:Relay_DPDT_Omron_G5V-2",
         (152.4, 175.26, 0),
         {"16": "+5V", "1": "COIL_N", "4": "VE1", "13": "VE1",
          "6": "NC_PATH", "11": "NC_PATH", "8": "NO_PATH", "9": "NO_PATH"},
         Description="Fail-safe relay, both poles in parallel; de-energised = R_failsafe"),
    # ---------------------------------------------------------- isolated domain
    part("C4", "Device:C", "10uF 16V X5R", FP_C0805, (208.28, 38.1, 0), {"1": "VDD_ISO", "2": "GND_ISO"},
         Description="TEM output buffer"),
    part("R8", "Device:R", "270R 0.6W", FP_R_THT, (220.98, 38.1, 0),
         {"1": "VDD_ISO", "2": "GND_ISO"}, dnp=True,
         Description="Optional TEM preload (~18 mA), fit only if no-load output > 5.4 V"),
    part("R7", "Device:R", "1k5", FP_R0805, (233.68, 33.02, 0), {"1": "VDD_ISO", "2": "LED_ISO"},
         Description="Indicator LED resistor"),
    part("D2", "Device:LED", "green", "LED_SMD:LED_0805_2012Metric_Pad1.15x1.40mm_HandSolder",
         (233.68, 45.72, 90), {"1": "GND_ISO", "2": "LED_ISO"},
         Description="VDD_ISO present"),
    part("C5", "Device:C", "100nF", FP_C0805, (177.8, 111.76, 0), {"1": "VDD_ISO", "2": "GND_ISO"},
         Description="U1 VCC2 decoupling"),
    part("R5", "Device:R", "4k7", FP_R0805, (190.5, 101.6, 0), {"1": "VDD_ISO", "2": "SDA_ISO"},
         Description="I2C pull-up SDC side"),
    part("R6", "Device:R", "4k7", FP_R0805, (198.12, 101.6, 0), {"1": "VDD_ISO", "2": "SCL_ISO"},
         Description="I2C pull-up SDC side"),
    part("U2", "Potentiometer_Digital:AD5272BRM", "AD5272BRMZ-50", "Package_SO:MSOP-10_3x3mm_P0.5mm",
         (241.3, 121.92, 0),
         {"1": "VDD_ISO", "2": "GND_ISO", "3": "WIPER", "4": "GND_ISO", "5": "EXT_CAP",
          "6": "GND_ISO", "7": "VDD_ISO", "8": "SDA_ISO", "9": "SCL_ISO", "10": "GND_ISO"},
         Description="1024-step 50k digital rheostat, I2C address 0x2F (ADDR=GND)"),
    part("C6", "Device:C", "100nF", FP_C0805, (223.52, 101.6, 0), {"1": "VDD_ISO", "2": "GND_ISO"},
         Description="U2 VDD decoupling"),
    part("C7", "Device:C", "10uF 16V X5R", FP_C0805, (231.14, 101.6, 0), {"1": "VDD_ISO", "2": "GND_ISO"},
         Description="U2 VDD decoupling"),
    part("C8", "Device:C", "1uF 16V", FP_C0805, (269.24, 129.54, 0), {"1": "EXT_CAP", "2": "GND_ISO"},
         Description="AD5272 EXT_CAP (>= 7 V rating)"),
    part("R9", "Device:R", "18k2 0.1% 25ppm", FP_R_THT, (208.28, 175.26, 90), {"1": "NO_PATH", "2": "WIPER"},
         Description="R_series: hardware floor ~27 C even if the AD5272 is unpowered or shorted"),
    part("R10", "Device:R", "24k9 0.1% 25ppm", FP_R_THT, (208.28, 195.58, 90), {"1": "NC_PATH", "2": "GND_ISO"},
         Description="R_failsafe ~20.4 C true = ~20.9 C on the SDC display (+0.5 K offset)"),
    part("J4", "Connector:Screw_Terminal_01x02", "SDC VE1 / GND", FP_TERM, (254.0, 177.8, 0),
         {"1": "VE1", "2": "GND_ISO"}, Description="To SDC X6-6 (VE1) and X5 (GND)"),
    # ---------------------------------------------------------------- mechanical
    part("H1", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", (40.64, 254.0, 0), {},
         in_bom=False),
    part("H2", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", (53.34, 254.0, 0), {},
         in_bom=False),
    part("H3", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", (66.04, 254.0, 0), {},
         in_bom=False),
    part("H4", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", (78.74, 254.0, 0), {},
         in_bom=False),
]

# Power flags for nets that are only driven by passive pins (connectors).
PWR_FLAGS = [("+5V", (60.96, 25.4)), ("GND", (60.96, 45.72)), ("+3V3", (106.68, 96.52))]

TEXTS = [
    ("ESP DOMAIN (earthed via USB/PC allowed)", (20.32, 15.24), 2.5),
    ("ISOLATED SDC DOMAIN (referenced to SDC X5 only)", (195.58, 15.24), 2.5),
    ("DevKit: ESP32-S3-DevKitC-1 (N16R8 clone), header rows 25.1 mm apart (measured).\n"
     "GPIO4 = RELAY_EN (ESPHome restore_mode ALWAYS_OFF), GPIO5 = RELAY_SENSE (LOW = coil on),\n"
     "GPIO8 = SDA, GPIO9 = SCL.", (20.32, 228.6), 1.5),
    ("Relay K1: coil 1/16, COM 4/13, NC 6/11, NO 8/9 (Omron datasheet).\n"
     "Both poles in parallel for dry-circuit reliability.\n"
     "De-energised: VE1 -> R10 (fail-safe). Energised: VE1 -> R9 -> AD5272 W-A.", (152.4, 213.36), 1.5),
    ("AD5272: ADDR = GND -> I2C 0x2F. RESET tied to VDD.\n"
     "Firmware: write control reg C1=1 at boot, never set C0 (50-TP).", (223.52, 147.32), 1.5),
    ("R8 is DNP: fit only if TEM no-load output > 5.4 V.", (208.28, 55.88), 1.5),
]
