# Handoff: Funk-Raumfühler für Honeywell Home Smile SDC per NTC-Emulation

## Ziel

Ein Honeywell Home (Resideo) Smile SDC Heizungsregler regelt aktuell rein witterungsgeführt (Außentemperatur). Er soll zusätzlich die Wohnzimmertemperatur berücksichtigen (Raumaufschaltung), ohne ein Buskabel zu verlegen.

Lösung: Ein ESP32 am Regler bildet am Raumfühler-Eingang (variabler Eingang VE) den Widerstand eines NTC-20k-Raumfühlers (Typ RF 20) nach. Die echte Raumtemperatur kommt per WLAN von einem vorhandenen Sonoff-Panel im Wohnzimmer.

## Kontext aus dem Vorgespräch

- Anlage: Heizkörper **ohne Raumregelventile**, hydraulisch abgeglichen. Das ist gut für Raumaufschaltung: Das Wohnzimmer dient als Referenzraum, die übrigen Räume folgen über den Abgleich.
- Verworfene Optionen:
  - Wandmodul SDW10/SDW30 am Smile-Bus (Klemmen A/B): kein Kabel vorhanden.
  - Smile-Bus per Funk tunneln: proprietäres, undokumentiertes Protokoll, Busversorgung der Wandmodule, Timing-Probleme. Zu aufwendig.
  - Smile Connect (SCN-10) + Smile Room Connect (SRC-10): für Einzelraumregelung mit Funk-Heizkörperventilen gedacht, passt nicht.
- Gewählt: Analoger Raumfühler RF 20 am variablen Eingang, per ESP32 emuliert. Laut SDC-Installationsanleitung wird der Raumfühler über Parameter 08, 09 oder 10 im Menü „Hydraulik" einem variablen Eingang (z. B. VE1) zugeordnet.
- Sollwert wird am Regler eingestellt (nicht im Raum). Später evtl. erweiterbar.

## Hardware-Skizze

```
  WOHNZIMMER                                HEIZUNGSRAUM
 ┌───────────────────┐                    ┌──────────────────────────────────────────┐
 │ Sonoff Panel      │                    │  Isoliertes 5V-Netzteil                   │
 │ (Temp.-Sensor +   │   WLAN / MQTT /    │  (USB-Steckernetzteil o. HLK-PM01)        │
 │  Display)         │ ─ HA / ESP-NOW ──▶ │        │ 5V                               │
 └───────────────────┘                    │        ▼                                  │
                                          │  ┌───────────┐  I2C   ┌──────────────┐    │
                                          │  │  ESP32    │───────▶│ AD5272 50k   │    │
                                          │  │ (3.3V)    │ SDA/SCL│ Rheostat     │    │
                                          │  └───────────┘        │ 1024 Stufen  │    │
                                          │                       │ ±1 % Toleranz│    │
                                          │                       └──┬────────┬──┘    │
                                          │                          │ W      │ A     │
                                          │                  R_serie │        │       │
                                          │                  ~12–15k ┴        │       │
                                          │                          │        │       │
                                          └──────────────────────────┼────────┼───────┘
                                                                     │        │
                                                          ┌──────────┴────────┴───┐
                                                          │ SDC-Regler            │
                                                          │ Klemmen VEx / Masse   │
                                                          │ (Raumfühler-Eingang)  │
                                                          └───────────────────────┘
```

### Stückliste (Vorschlag)

| Teil | Zweck | Hinweis |
|---|---|---|
| ESP32 DevKit | Empfang der Raumtemp., Ansteuerung Rheostat | beliebiges Board |
| AD5272BRMZ-50 (oder vergleichbar) | digitaler Rheostat, 50 kΩ, 1024 Stufen, I2C | ±1 % Widerstandstoleranz, 50-TP-Speicher für Power-on-Wert |
| Festwiderstand ca. 12–15 kΩ, 0,1 % | Offset, damit der Bereich ~15–45 kΩ abgedeckt wird | exakten Wert nach NTC-Tabelle wählen |
| Isoliertes 5V-Netzteil | Versorgung ESP32 | **galvanisch getrennt**, siehe Sicherheit |
| optional: I2C-Isolator (ISO1540) + isolierter DC/DC | vollständige Trennung ESP32 ↔ Regler | empfohlen, falls die Eingangsspannung nicht zum Rheostat passt |
| Alternative: PhotoMOS-Relais + Widerstandskette | voll isolierte Widerstandsnachbildung ohne Rail-Probleme | mehr Bauteile, dafür robust |

### Größenordnung Widerstand (NTC 20k, grob)

- 30 °C ≈ 16 kΩ, 25 °C = 20 kΩ, 20 °C ≈ 25 kΩ, 15 °C ≈ 31 kΩ, 10 °C ≈ 40 kΩ
- **Diese Werte sind Näherungen.** Die exakte Kennlinie (Tabelle oder B-Wert) aus der Honeywell-Dokumentation zum RF 20 / NTC-20k-Fühler übernehmen.
- Steigung um 20 °C ca. 1 kΩ/K → AD5272 50k (≈ 49 Ω/Stufe) ergibt ca. 0,05 K Auflösung.

## Sicherheit & Robustheit (wichtig)

1. **Erst messen:** Leerlaufspannung und Messstrom an den VE-Klemmen (Regler an, Fühler ab) mit dem Multimeter bestimmen. Die Spannung über dem Rheostat muss innerhalb seiner Versorgung (0–5 V) liegen.
2. **Galvanische Trennung:** ESP32 nur über ein isoliertes Netzteil versorgen. Beim Debuggen per USB am PC entsteht eine Masseverbindung zum Regler: nur bei ausgeschaltetem Regler oder mit USB-Isolator arbeiten.
3. **Keine Arbeiten unter Netzspannung.** Im Regler liegen 230 V an (Brenner, Pumpen, Mischer). Anschluss nur an den Kleinspannungs-Fühlerklemmen.
4. **Fail-safe:** Bleibt der Temperaturwert vom Panel länger als z. B. 10 Minuten aus, einen neutralen Wert ausgeben (Widerstand, der dem Raumsollwert entspricht → Raumaufschaltung korrigiert nicht). Denselben Wert als Power-on-Default in den 50-TP-Speicher des AD5272 schreiben.
5. **Plausibilitätsgrenzen:** Ausgabe auf z. B. 10–30 °C begrenzen, Sprünge glätten.
6. Eingriff kann Gewährleistung/Garantie des Reglers berühren.

## Software-Aufgaben für Claude Code

1. **Datenquelle klären und anbinden** (siehe offene Punkte): Raumtemperatur vom Sonoff-Panel empfangen, z. B. via
   - ESPHome + Home Assistant (bevorzugt, falls HA vorhanden),
   - MQTT (z. B. bei Tasmota auf dem Panel),
   - ESP-NOW direkt (falls Panel ESP32-basiert und frei programmierbar).
2. **Temperatur → Widerstand:** NTC-Kennlinie als Tabelle mit linearer Interpolation oder Steinhart-Hart/B-Parameter implementieren.
3. **Widerstand → Rheostat-Code:** `code = round((R_ziel − R_serie − R_wiper) / (50k / 1024))`, auf 0–1023 begrenzen. AD5272: Write-Protect (RDAC-Schreibschutz) per Control-Register aufheben.
4. **Kalibrierung:** Offset-Parameter vorsehen, abgleichen gegen die am SDC angezeigte Raumtemperatur.
5. **Watchdog/Fail-safe** wie oben, inkl. Statusmeldung (z. B. „Quelle verloren") an HA/MQTT.
6. **Diagnose:** aktuellen Sollwiderstand, Code, letzte Aktualisierung als Sensoren veröffentlichen.
7. Firmware-Framework: ESPHome (AD5272 braucht vermutlich eine kleine External Component) oder Arduino/PlatformIO. Entscheidung nach Klärung der Datenquelle.

## Einrichtung am SDC-Regler

1. Raumfühler im Menü „Hydraulik" per Parameter 08/09/10 dem genutzten variablen Eingang zuordnen (Installationsanleitung, Kapitel „Anschluss von Raumgeräten").
2. Raumeinfluss/Raumaufschaltung für den betreffenden Heizkreis aktivieren, **moderat** einstellen (Außentemperatur bleibt Basis).
3. Vorher Heizkurve sauber einstellen; die Raumaufschaltung ist nur Feinkorrektur.
4. Im Wohnzimmer: Fühler-/Panel-Position fern von Sonne, Heizkörper, Kamin.

## Offene Punkte (vor Start klären)

- [ ] Exaktes SDC-Modell und Softwareversion (SDC3-10 / 3-40 / 9-21 / 12-31, WM/PM)?
- [ ] Welcher VE-Eingang ist frei?
- [ ] Gemessene Leerlaufspannung / Messstrom am VE-Eingang?
- [ ] Welches Sonoff-Panel (NSPanel, NSPanel Pro, …) und welche Firmware (eWeLink, Tasmota, ESPHome)?
- [ ] Gibt es Home Assistant oder einen MQTT-Broker?
- [ ] Exakte NTC-20k-Kennlinie aus Honeywell-Unterlagen.
