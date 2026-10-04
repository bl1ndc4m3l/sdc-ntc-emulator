"""Single source of truth for the SDC NTC emulator board.

Each part lists its schematic symbol, value, footprint, schematic position
and pin -> net mapping. make_schematic.py turns this into the .kicad_sch;
make_pcb.py places the footprints and reads the nets back from the netlist
that kicad-cli exports from that schematic.
"""

PROJECT = "sdc-ntc-emulator"

# Nets in the isolated SDC domain (everything else is the ESP domain).
ISO_NETS = {"VDD_ISO", "GND_ISO", "SDA_ISO", "SCL_ISO", "EXT_CAP", "WIPER",
            "NO_PATH", "NC_PATH", "VE1", "LED_ISO",
            "SVC_RX_ISO", "SVC_RX_EXT", "SVC_TX_ISO", "SVC_TX_EXT", "SVC_5V"}

FP_R0805 = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"
FP_R_THT = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
FP_TERM = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
FP_SOCKET = "Connector_PinSocket_2.54mm:PinSocket_1x22_P2.54mm_Vertical"
FP_LED = "LED_SMD:LED_0805_2012Metric_Pad1.15x1.40mm_HandSolder"
FP_SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"


def part(ref, symbol, value, footprint, sch, pins, **fields):
    return dict(ref=ref, symbol=symbol, value=value, footprint=footprint,
                sch=sch, pins=pins, fields=fields)


# DevKit header J1 (official ESP32-S3-DevKitC-1 pinout, verified against the
# Espressif schematic V1.1). Only the pins below are used.
DEVKIT_J1 = {"1": "+3V3", "2": "+3V3", "4": "RELAY_EN", "5": "RELAY_SENSE", "6": "SVC_RX",
             "7": "SVC_TX", "12": "SDA_ESP", "15": "SCL_ESP", "21": "+5V", "22": "GND"}
# J3 pin 1 (GND, antenna end) is left open: it sits at the antenna keep-out edge.
# J3 pins 4/5 = GPIO1/GPIO2 (ADC1-capable, no strapping function) for the expansion header.
DEVKIT_J3 = {"4": "EXT_IO1", "5": "EXT_IO2", "21": "GND", "22": "GND"}

PARTS = [
    # ---------------------------------------------------------------- ESP domain
    part("J1", "Connector:Conn_01x22_Socket", "DevKit J1", FP_SOCKET, (30.48, 76.2, 0),
         DEVKIT_J1, Description="ESP32-S3-DevKitC-1 header J1 (3V3/GPIO4-9/5V/GND)"),
    part("J2", "Connector:Conn_01x22_Socket", "DevKit J3", FP_SOCKET, (30.48, 160.02, 0),
         DEVKIT_J3, Description="ESP32-S3-DevKitC-1 header J3 (GPIO1/GPIO2, GND)"),
    part("J3", "Connector:Screw_Terminal_01x02", "5V IN (RAC03)", FP_TERM, (71.12, 35.56, 180),
         {"1": "+5V_IN", "2": "GND"}, Description="5 V from Recom RAC03-05SER/277 flying leads"),
    part("J7", "Connector:USB_C_Receptacle_PowerOnly_6P", "USB-C 5V IN",
         "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x-0190_6P_TopMnt_Horizontal", (294.64, 205.74, 0),
         {"A9": "+5V_IN", "B9": "+5V_IN", "A12": "GND", "B12": "GND", "S1": "GND",
          "A5": "USB_CC1", "B5": "USB_CC2"},
         Description="5 V input alternative to J3 (any USB-C charger); power sink only, never above 5 V"),
    part("R22", "Device:R", "5k1", FP_R0805, (322.58, 213.36, 0), {"1": "USB_CC1", "2": "GND"},
         Description="USB-C CC1 Rd: identifies the board as a sink, the charger then supplies 5 V"),
    part("R23", "Device:R", "5k1", FP_R0805, (332.74, 213.36, 0), {"1": "USB_CC2", "2": "GND"},
         Description="USB-C CC2 Rd (cable can be plugged either way round)"),
    part("Q2", "Transistor_FET:AO3401A", "AO3401A", "Package_TO_SOT_SMD:SOT-23", (78.74, 60.96, 0),
         {"1": "GND", "2": "+5V", "3": "+5V_IN"},
         Description="Reverse-polarity protection: P-FET, gate to GND (Vgs max 12 V), ~25 mV drop"),
    part("C1", "Device:C_Polarized", "470uF 10V", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
         (88.9, 38.1, 0), {"1": "+5V", "2": "GND"}, Description="5 V bulk for Wi-Fi TX peaks"),
    part("C9", "Device:C", "10uF 25V X7R", "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder",
         (95.25, 38.1, 0), {"1": "+5V", "2": "GND"},
         Description="Low-ESR ceramic parallel to C1: RAC03 ripple, fast Wi-Fi current edges"),
    part("C2", "Device:C", "10uF 16V X5R", FP_C0805, (101.6, 38.1, 0), {"1": "+5V", "2": "GND"},
         Description="TMR 1-0511 input decoupling (80 mA p-p reflected ripple)"),
    part("PS1", "sdc_emulator:TMR1-0511", "TMR 1-0511",
         "Converter_DCDC:Converter_DCDC_TRACO_TMR-1-xxxx_Single_THT", (142.24, 45.72, 0),
         {"2": "+5V", "1": "GND", "4": "VDD_ISO", "6": "GND_ISO"},
         Description="Traco TMR 1-0511 isolated DC/DC 5 V -> 5 V regulated, 200 mA, 1500 VDC, SIP-6"),
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
    # indicators
    part("R13", "Device:R", "2k2", FP_R0805, (294.64, 33.02, 0), {"1": "+5V", "2": "LED_PWR"},
         Description="5 V power LED resistor (~1.3 mA)"),
    part("D3", "Device:LED", "green", FP_LED, (294.64, 45.72, 90), {"1": "GND", "2": "LED_PWR"},
         Description="5 V present (after the reverse-polarity FET)"),
    part("R14", "Device:R", "2k2", FP_R0805, (314.96, 33.02, 0), {"1": "+5V", "2": "LED_REL"},
         Description="Relay LED resistor (~1.3 mA)"),
    part("D4", "Device:LED", "yellow", FP_LED, (314.96, 45.72, 90), {"1": "COIL_N", "2": "LED_REL"},
         Description="Relay coil energised (parallel to the coil: shows the real coil state)"),
    # expansion header: GPIO1/GPIO2 (I2C, 1-Wire, UART, ADC ...)
    part("J6", "Connector:Conn_01x04_Pin", "EXT I/O", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
         (294.64, 76.2, 0), {"1": "+3V3", "2": "EXT_IO2_H", "3": "EXT_IO1_H", "4": "GND"},
         Description="Expansion header: 3V3, GPIO2, GPIO1, GND"),
    part("R18", "Device:R", "100R", FP_R0805, (309.88, 73.66, 0), {"1": "EXT_IO2_H", "2": "EXT_IO2"},
         Description="Series resistor GPIO2 (ESD / short-circuit protection)"),
    part("R19", "Device:R", "100R", FP_R0805, (309.88, 91.44, 0), {"1": "EXT_IO1_H", "2": "EXT_IO1"},
         Description="Series resistor GPIO1 (ESD / short-circuit protection)"),
    part("R20", "Device:R", "4k7", FP_R0805, (325.12, 68.58, 90), {"1": "+3V3", "2": "EXT_IO2"}, dnp=True,
         Description="Optional pull-up GPIO2 (I2C / 1-Wire)"),
    part("R21", "Device:R", "4k7", FP_R0805, (340.36, 68.58, 90), {"1": "+3V3", "2": "EXT_IO1"}, dnp=True,
         Description="Optional pull-up GPIO1 (I2C / 1-Wire)"),
    # SDC service port: isolated UART (ISO7721 straddles the isolation gap like U1)
    part("U3", "Isolator:ISO7721D", "ISO7721D", FP_SOIC8, (309.88, 116.84, 0),
         {"1": "+3V3", "2": "SVC_RX", "3": "SVC_TX", "4": "GND",
          "5": "GND_ISO", "6": "SVC_TX_ISO", "7": "SVC_RX_ISO", "8": "VDD_ISO"},
         Description="Service-port UART isolator, 1/1 channels, default output high (UART idle)"),
    part("C10", "Device:C", "100nF", FP_C0805, (289.56, 114.3, 0), {"1": "+3V3", "2": "GND"},
         Description="U3 VCC1 decoupling"),
    # ---------------------------------------------------------- isolated domain
    part("C4", "Device:C", "10uF 16V X5R", FP_C0805, (208.28, 38.1, 0), {"1": "VDD_ISO", "2": "GND_ISO"},
         Description="TMR output buffer"),
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
    part("C11", "Device:C", "100nF", FP_C0805, (335.28, 114.3, 0), {"1": "VDD_ISO", "2": "GND_ISO"},
         Description="U3 VCC2 decoupling"),
    part("R15", "Device:R", "1k", FP_R0805, (345.44, 104.14, 0), {"1": "SVC_RX_EXT", "2": "SVC_RX_ISO"},
         Description="Service RX series resistor (cable protection, limits current on a wrong pinout)"),
    part("R16", "Device:R", "1k", FP_R0805, (345.44, 124.46, 0), {"1": "SVC_TX_EXT", "2": "SVC_TX_ISO"},
         Description="Service TX series resistor (limits current if the SDC line also drives)"),
    part("R17", "Device:R", "0R", FP_R0805, (345.44, 139.7, 0), {"1": "SVC_5V", "2": "VDD_ISO"},
         Description="VDD_ISO to the service connector; remove if the SDC port has its own 5 V"),
    part("J5", "Connector:Conn_01x04_Pin", "SDC SERVICE", "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical",
         (365.76, 116.84, 180), {"1": "GND_ISO", "2": "SVC_RX_EXT", "3": "SVC_TX_EXT", "4": "SVC_5V"},
         Description="SDC service port: GND_ISO, RX (from SDC TX), TX (to SDC RX), 5 V (VDD_ISO)"),
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

# Manufacturer part numbers (DigiKey BOM Manager matches uploads on these).
# (manufacturer, MPN, order quantity for one board incl. spares, note)
# Spares only for cheap SMD parts that get lost or for the fine-pitch AD5272; the costly
# THT parts and SOIC isolators are hand-solderable and bought without spares.
MPN = {
    "C1": ("Panasonic", "EEU-FR1A471", 1, "470 uF 10 V, 8 x 11.5 mm, 3.5 mm pitch, low ESR"),
    "C3 C5 C6 C10 C11": ("Samsung Electro-Mechanics", "CL21B104KBCNNNC", 10, "100 nF 50 V X7R 0805"),
    "C2 C4 C7": ("Yageo", "CC0805KRX5R7BB106", 4, "10 uF 16 V X5R 0805"),
    "C8": ("Murata", "GRM219R71E105KA88D", 5, "1 uF 25 V X7R 0805"),
    "C9": ("Murata", "GRM31CR71E106MA12L", 3, "10 uF 25 V X7R 1206"),
    "D1": ("Diodes Incorporated", "1N4148W-7-F", 3, "SOD-123"),
    "D2 D3": ("Lite-On", "LTST-C171GKT", 4, "green LED 0805"),
    "D4": ("Lite-On", "LTST-C171YKT", 3, "yellow LED 0805"),
    "J1 J2": ("Sullins Connector Solutions", "PPTC221LFBN-RC", 2, "female header 1 x 22, 2.54 mm"),
    "J3 J4": ("Phoenix Contact", "1715721", 2, "MKDS 1,5/ 2-5,08 terminal block"),
    "J5": ("JST", "B4B-XH-A(LF)(SN)", 1, "XH 4-pin header, 2.5 mm, vertical"),
    "J6": ("Wurth Elektronik", "61300411121", 1, "pin header 1 x 4, 2.54 mm"),
    "J7": ("GCT", "USB4125-GF-A-0190", 1, "USB-C receptacle, power only, 6P, 1.9 mm shell stakes"),
    "K1": ("Omron", "G5V-2-H1 DC5", 1, "DPDT signal relay, 5 V high-sensitivity coil"),
    "Q1": ("Alpha & Omega Semiconductor", "AO3400A", 3, "N-MOSFET SOT-23"),
    "Q2": ("Alpha & Omega Semiconductor", "AO3401A", 3, "P-MOSFET SOT-23"),
    "R1 R2": ("Yageo", "RC0805FR-072K7L", 10, "2.7 k 1 % 0805"),
    "R3": ("Yageo", "RC0805FR-07100KL", 10, "100 k 1 % 0805"),
    "R4 R18 R19": ("Yageo", "RC0805FR-07100RL", 10, "100 R 1 % 0805"),
    "R5 R6 R20 R21": ("Yageo", "RC0805FR-074K7L", 10, "4.7 k 1 % 0805 (R20/R21 optional)"),
    "R7": ("Yageo", "RC0805FR-071K5L", 10, "1.5 k 1 % 0805"),
    "R13 R14": ("Yageo", "RC0805FR-072K2L", 10, "2.2 k 1 % 0805"),
    "R15 R16": ("Yageo", "RC0805FR-071KL", 10, "1 k 1 % 0805"),
    "R17": ("Yageo", "RC0805JR-070RL", 10, "0 R jumper 0805"),
    "R22 R23": ("Bourns", "CR0805-FX-5101ELF", 10, "5.1 k 1 % 0805 (USB-C Rd)"),
    "R11": ("Yageo", "RC0805FR-0710KL", 10, "10 k 1 % 0805"),
    "R12": ("Stackpole Electronics", "RMCF0805FT20K0", 10, "20 k 1 % 0805"),
    "R9": ("TE Connectivity", "YR1B18K2CC", 1, "18.2 k 0.1 % 15 ppm 1/4 W axial 2.3 x 6.3 mm"),
    "R10": ("TE Connectivity", "YR1B24K9CC", 1, "24.9 k 0.1 % 15 ppm 1/4 W axial 2.3 x 6.3 mm"),
    "U1": ("Texas Instruments", "ISO1540DR", 1, "I2C isolator SOIC-8"),
    "U3": ("Texas Instruments", "ISO7721DR", 1, "dual digital isolator 1/1, default high, SOIC-8"),
    "U2": ("Analog Devices", "AD5272BRMZ-50", 2, "50 k digital rheostat MSOP-10 (spare for hand soldering)"),
    "PS1": ("Traco Power", "TMR 1-0511", 1, "isolated DC/DC 1 W regulated, SIP-6"),
}

# DigiKey part numbers (cut tape where offered), checked on digikey.com 2026-10-01.
# BOM Manager matches these exactly; matching on the MPN alone is fuzzy (JST suffixes,
# "TMR 1-0511" with a space) and offers obsolete or backordered parts.
DIGIKEY = {
    "EEU-FR1A471": "P124219-ND",
    "CL21B104KBCNNNC": "1276-1003-1-ND",
    "CC0805KRX5R7BB106": "311-3502-1-ND",
    "GRM219R71E105KA88D": "490-5899-1-ND",
    "GRM31CR71E106MA12L": "490-6519-1-ND",
    "1N4148W-7-F": "1N4148W-FDICT-ND",
    "LTST-C171GKT": "160-1423-1-ND",
    "LTST-C171YKT": "160-1431-1-ND",
    "PPTC221LFBN-RC": "S7020-ND",
    "1715721": "277-1263-ND",
    "B4B-XH-A(LF)(SN)": "455-B4B-XH-A-ND",
    "61300411121": "732-5317-ND",
    "USB4125-GF-A-0190": "2073-USB4125-GF-A-0190CT-ND",
    "G5V-2-H1 DC5": "Z108-ND",
    "AO3400A": "785-1000-1-ND",
    "AO3401A": "785-1001-1-ND",
    "RC0805FR-072K7L": "311-2.70KCRCT-ND",
    "RC0805FR-07100KL": "311-100KCRCT-ND",
    "RC0805FR-07100RL": "311-100CRCT-ND",
    "RC0805FR-074K7L": "311-4.70KCRCT-ND",
    "RC0805FR-071K5L": "311-1.50KCRCT-ND",
    "RC0805FR-072K2L": "311-2.20KCRCT-ND",
    "RC0805FR-071KL": "311-1.00KCRCT-ND",
    "RC0805JR-070RL": "311-0.0ARCT-ND",
    "CR0805-FX-5101ELF": "CR0805-FX-5101ELFCT-ND",
    "RC0805FR-0710KL": "311-10.0KCRCT-ND",
    "RMCF0805FT20K0": "RMCF0805FT20K0CT-ND",
    "YR1B18K2CC": "1712-YR1B18K2CCCT-ND",
    "YR1B24K9CC": "1712-YR1B24K9CCCT-ND",
    "ISO1540DR": "296-34871-1-ND",
    "ISO7721DR": "296-48296-1-ND",
    "AD5272BRMZ-50": "505-AD5272BRMZ-50-ND",
    "TMR 1-0511": "1951-2333-ND",
}

# Boards to buy parts for (JLC ships 5 bare PCBs; 3 get assembled).
BOARDS = 3


def order_qty(refs, mpn, order):
    """Quantity for BOARDS boards: per-board count x BOARDS, plus the spares that the
    one-board quantity above contains (once, not per board). Rounded up to where DigiKey's
    cut-tape price breaks make the larger quantity cheaper in total (checked 2026-10-01):
    0805 resistors break at 10/25/50 (25 pcs cost less than 20), MLCCs at 10/50, and
    7-9 pcs of anything cost more than 10 at the 10-pcs break."""
    per_board = len(refs.split())
    qty = per_board * BOARDS + max(0, order - per_board)
    if mpn.startswith(("RC0805", "CR0805", "RMCF0805")):
        qty = -(-qty // 25) * 25
    elif mpn.startswith(("GRM", "CL21", "CC0805")):
        qty = -(-qty // 10) * 10
    elif 7 <= qty < 10:
        qty = 10
    return qty


# Off-board parts (not on the PCB, listed for completeness)
OFF_BOARD = [
    ("Recom", "RAC03-05SER/277", 0, "AC/DC 5 V 3 W - already on hand (end of life)"),
    ("", "USB-C charger, 5 V >= 2 A (any certified phone charger)", 1,
     "kit alternative to the RAC03: plugs into J7, no mains wiring; see README for more options"),
    ("", "ESP32-S3-DevKitC-1 N16R8 clone", 0, "already on hand"),
    ("", "fuse 5 x 20 mm slow-blow + in-line holder", 1,
     "value not given by Recom; T 500 mA - T 1 A is typical for a 3 W module - buy locally"),
    ("", "Wago 221 lever terminals, M3 spacers, enclosure", 1, "buy locally"),
    ("JST", "XHP-4 + SXH-001T-P0.6 (or a pre-crimped XH cable)", 1,
     "mating plug for J5; the SDC end needs a 1.0 mm adapter (pinout still to be measured)"),
]


def mpn_for(ref):
    for refs, data in MPN.items():
        if ref in refs.split():
            return data
    return None


# Power flags for nets that are only driven by passive pins (connectors).
PWR_FLAGS = [("+5V", (60.96, 25.4)), ("GND", (60.96, 45.72)), ("+3V3", (106.68, 96.52))]

TEXTS = [
    ("ESP DOMAIN (earthed via USB/PC allowed)", (20.32, 15.24), 2.5),
    ("ISOLATED SDC DOMAIN (referenced to SDC X5 only)", (195.58, 15.24), 2.5),
    ("DevKit: ESP32-S3-DevKitC-1 (N16R8 clone), header rows 25.1 mm apart (measured).\n"
     "GPIO4 = RELAY_EN (ESPHome restore_mode ALWAYS_OFF), GPIO5 = RELAY_SENSE (LOW = coil on),\n"
     "GPIO8 = SDA, GPIO9 = SCL, GPIO6 = service RX, GPIO7 = service TX (UART),\n"
     "GPIO1/GPIO2 = expansion header J6.", (20.32, 228.6), 1.5),
    ("SDC service port (J5): UART at 5 V logic, isolated by U3. Pinout of the SDC socket\n"
     "is not yet known: J5-2 RX must go to the SDC's TX, J5-3 TX to the SDC's RX.\n"
     "J5-1 is GND_ISO (= SDC X5 ground): only connect if the port GND is the same potential.\n"
     "R17 (0R): remove if the SDC port has its own 5 V supply pin.", (284.48, 157.48), 1.5),
    ("Relay K1: coil 1/16, COM 4/13, NC 6/11, NO 8/9 (Omron datasheet).\n"
     "Both poles in parallel for dry-circuit reliability.\n"
     "De-energised: VE1 -> R10 (fail-safe). Energised: VE1 -> R9 -> AD5272 W-A.", (152.4, 213.36), 1.5),
    ("AD5272: ADDR = GND -> I2C 0x2F. RESET tied to VDD.\n"
     "Firmware: write control reg C1=1 at boot, never set C0 (50-TP).", (223.52, 147.32), 1.5),
    ("PS1 TMR 1-0511: regulated, no minimum load. Pin 3/5 absent:\n"
     "5.08 mm between +Vin (2) and +Vout (4).", (208.28, 55.88), 1.5),
]
