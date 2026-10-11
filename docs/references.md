# References and related projects

[← README](../README.md) · [protocol](protocol.md) · [connection box](connection-box.md) · [esphome](esphome.md) · [reverse engineering](reverse-engineering.md)

Projects, documents and forums related to this one: pellet-stove controllers on the same Micronova bus,
Palazzetti Connection Box clients, manuals, and the project used as scaffolding. Each entry says what we can
reuse from it. Links were checked in 2026; entries marked *unverified* were found through citations but not
opened.

## 1. Two board families, two protocols

Palazzetti stoves have shipped with two kinds of control board, and the projects below split along that line:

| Family | Bus | Frames | Addresses | Used by |
|---|---|---|---|---|
| **Micronova** | 1-wire half duplex, 1200 baud 8N2 | 2-byte read / 4-byte write, see [protocol.md](protocol.md) | 8-bit RAM and EEPROM | Ecofire Lara (**implemented here**), Extraflame, MCZ, Laminox, Ungaro, Artel, L'Asolana… |
| **Fumis** (Alpha) | serial, 38400 baud | 11-byte frames | 16-bit (`0x20xx`, `0x2100` serial number…) | newer Palazzetti (not implemented), Jotul, TurboFonte, Godin, Fonte Flamme, Invicta, Casatelli, Alpis, HETA |

The Ecofire Lara has a Micronova-protocol board, and only that protocol is implemented here; the evidence and
the full comparison are in [boards.md](boards.md). The Connection Box speaks to both (see
[connection-box.md](connection-box.md)). Fumis projects are listed in
§4 because their command lists and status codes overlap with ours, but their frames are not compatible with
the Micronova bus.

## 2. ESPHome implementations (Micronova)

| Project | Platform | Notes | Reusable for us |
|---|---|---|---|
| **[ESPHome `micronova`](https://esphome.io/components/micronova/)** ([source](https://github.com/esphome/esphome/tree/dev/esphome/components/micronova)) | ESPHome core | Official component: UART 1200 8N2, `enable_rx_pin`, `memory_location`/`memory_address` per entity. Tested on Extraflame boards. | Frame handling, configuration vocabulary, adapter schematic (credited to philibertc). Our component keeps the same frame layer and adds profiles, scanning and polling ([esphome.md](esphome.md)). |
| **[Jorre05/micronova](https://github.com/Jorre05/micronova)** | ESPHome external | Origin of the core component, still where fixes land first. | Watch for fixes not yet upstream. |
| **[r-hmn/micronova_stove_esphome](https://github.com/r-hmn/micronova_stove_esphome)** | ESPHome + Arduino | Artel Idro 15; includes a PCB. | Second adapter PCB to compare with [adapter.md](adapter.md). |
| **[morettigiorgio/micronova-C6](https://github.com/morettigiorgio/micronova-C6)** | ESPHome, ESP32-C6 | Powered from the stove bus; relay outputs; ultrasonic pellet level. | Self-powered design; pellet-level sensor idea. |
| **[Isno-Open/OpenXtraflame](https://github.com/Isno-Open/OpenXtraflame)** | ESP32 firmware, MQTT | Not ESPHome; Extraflame boards. | Independent address set for cross-checks. |

## 3. Other Micronova projects, protocol notes and adapters

| Project | Platform | Notes | Reusable for us |
|---|---|---|---|
| **[philibertc/micronova_controller](https://github.com/philibertc/micronova_controller)** | ESP8266, MQTT | Most-used community controller (MCZ, Extraflame, Laminox…), with a companion PCB. | Optocoupler adapter, command set; cited in [protocol.md](protocol.md). |
| **[eni23/micronova-controller](https://github.com/eni23/micronova-controller)** | ESP32, TCP bridge | L'Asolana Marina; documents that RAM/EEPROM maps differ per model. | Another address table; the TCP bridge is close to our `plz` lab server. |
| **[k3a/MicronovaPelletStoveController](https://github.com/k3a/MicronovaPelletStoveController)** + [blog post](https://k3a.me/ir-controller-for-pellet-stove-with-micronova-controller-stufe-e-pellet-aria-ir-telecomando/) | Arduino | Early write-up: connector pinout, **20 V on one pin** (killed a naive UART), logic-analyser captures, IR remote. | Connector and voltage warnings, used in [hardware.md](hardware.md). |
| **[cotestatnt/PelletStoveMicronova](https://github.com/cotestatnt/PelletStoveMicronova)** | ESP8266 | Half-duplex serial on ESP8266. | Same MCU as ours: echo handling, timing. |
| **[dili900/MicronovaBerry](https://github.com/dili900/MicronovaBerry)** | Tasmota (Berry) | Board I023_5; TX and RX joined through a **single diode**; `StoveReadRAM`/`StoveWriteEEPROM` commands. | Simplest possible adapter, an alternative to [adapter.md](adapter.md); command naming. |
| **[fabrizioromanelli/Pellet-Stove-Control](https://github.com/fabrizioromanelli/Pellet-Stove-Control)** | ESP, MQTT | Micronova MQTT bridge. | Cross-check the command set. |
| **[JoseHerrero99/micronova-pellets-stove](https://github.com/JoseHerrero99/micronova-pellets-stove)** | ESP, Blynk | PC817 optocoupler circuit with component values. | Component values for the adapter. |
| **[procaktomasz/ARTEL-MicronovaPelletStoveController](https://github.com/procaktomasz/ARTEL-MicronovaPelletStoveController)** | C | RAM/EEPROM files for an Artel boiler. | Which addresses stay stable across boards. |
| **[DanieleSgroi/Pelog](https://github.com/DanieleSgroi/Pelog)** | Arduino | Read-only data logger (Idro stove). | Read-only logging, like our first lab sessions. |
| **[Cyb3rn0id/Pellet-Stove-Web-Control](https://github.com/Cyb3rn0id/Pellet-Stove-Web-Control)** | ESP, infrared | Controls an Ungaro Maia Blend through the IR remote, no serial. | Fallback when the bus cannot be reached. |
| **[daniele-salvagni/pellet-aws-iot](https://github.com/daniele-salvagni/pellet-aws-iot)** | ESP8266, AWS IoT | Cited by the legacy Arduino code. | Historical; same frames. |

Protocol notes and forums:

- **ridiculouslab**, *Micronova protocol analysis*: <https://www.ridiculouslab.com/arguments/iot/stufa/micronova_en.php>.
  The protocol source credited by philibertc.
  Directly reviewed 2026-10-11: RAM-only table and representation hints are recorded
  in [its reference extraction](reference-mappings/micronova-ridiculouslab.yaml). It does not
  establish Lara EEPROM locations. Its translated Modbus register numbers are not
  stove serial addresses.
- **StufaPellet forum** (IT), the thread where the protocol was first documented, with a PlatformIO project
  (copy in the private repo `thirdparty/`): <https://stufapellet.forumcommunity.net/?t=53061907>.
  The site is intermittently unavailable.

Direct mapping review also covers [eni23's Marina extraction](reference-mappings/micronova-marina.yaml):
different clock layouts, BCD-like EEPROM examples and ten-minute schedule units.
Water scales and P+/P− labels conflict across these sources; the
[reference notes](reference-mappings/README.md) preserve those conflicts outside the Lara-only atlas.
ESPHome's current sensor
code supports configurable addresses and raw scaling, not Lara-specific applicability.
Remaining linked projects/manuals are a reference backlog, **not** a claim that all
their addresses, revisions and parameters have been extracted or verified.

Not reviewed yet: [raziel83257/micronovaEsphome](https://github.com/raziel83257/micronovaEsphome),
[ArthurG94/Stove](https://github.com/ArthurG94/Stove),
[giovannidesisto/micronovaSupervisor](https://github.com/giovannidesisto/micronovaSupervisor).

## 4. Palazzetti, Connection Box and Fumis

All of these go through the Connection Box HTTP API (`/cgi-bin/sendmsg.lua?cmd=…`) or replace the box on a Fumis
board. They are the best sources for command names, status codes and the parameters the box exposes.

| Project | Platform | Notes | Reusable for us |
|---|---|---|---|
| **[Home Assistant `palazzetti`](https://www.home-assistant.io/integrations/palazzetti)** ([source](https://github.com/home-assistant/core/tree/dev/homeassistant/components/palazzetti)) | HA core | Local polling through `pypalazzetti`; DHCP discovery of `connbox*` hosts. | Which box fields are considered stable; entity naming to match. |
| **[dotvav/py-palazzetti-api](https://github.com/dotvav/py-palazzetti-api)** (`pypalazzetti`) | Python | Async client; Connection Box or WPalaControl backend. | Command and attribute list; a client to test a box-compatible endpoint. |
| **[sdaclin/cBox](https://github.com/sdaclin/cBox)** | Python | Async client, `doc/cboxProtcol.md` protocol notes, `connbox_simulator.py`. | The simulator, to test a box-compatible API without a box. |
| **[condo4/KnxInes](https://github.com/condo4/KnxInes)** | C++, KNX | README (FR) lists `GET LABL/STDT/FWST/TMPS/FAND/SETP/STAT/TIME/MDVE/CHRD`, `EXT ADRD`, `CMD ON/OFF`, and the full `STAT` table (0 off … 253 no pellets). | Status-code table for the `palazzetti-connbox` profile. |
| **[condo4/KaZa-Server-Palazzetti](https://github.com/condo4/KaZa-Server-Palazzetti)** | C++ | Second client by the same author. | Cross-check the command list. |
| **[Vost3/hass-palazzetti](https://github.com/Vost3/hass-palazzetti)** | HA custom | Older integration; `set_parms` service, `GET ALLS`. | History of the command set. |
| **[marcopal74/home-assistant-palazzetti](https://github.com/marcopal74/home-assistant-palazzetti)** | HA custom (HACS) | Covers boilers, Air Pro3, Monoblocco; door/cover entities. | Feature ideas across product types. |
| **[marcopal74/palazzetti_local_api](https://github.com/marcopal74/palazzetti_local_api)** | Python | UDP discovery plus HTTP. | Box discovery protocol. |
| **[palazzetti/palazzetti-sdk-asset-parser-python](https://github.com/palazzetti/palazzetti-sdk-asset-parser-python)** | Python, **official** | Palazzetti's own parser for product capabilities. | Authoritative capability and field names per product; worth reading first. |
| **[kinou74/Domoticz-Palazzetti](https://github.com/kinou74/Domoticz-Palazzetti)** | Domoticz | Early plugin; documents the `sendmsg.php` → `sendmsg.lua` change. | History of the command set. |
| **[dotvav/vihio](https://github.com/dotvav/vihio)** | Python, MQTT | Box ⇄ MQTT bridge. | MQTT layout. |
| **[jeedom/plugin-Palazzetti](https://github.com/jeedom/plugin-Palazzetti)** / **[inapsis/ioBroker.palazzetti](https://github.com/inapsis/ioBroker.palazzetti)** | Jeedom / ioBroker | Two more ecosystems on the same API. | Cross-checks. |
| **[Domochip/WPalaControl](https://github.com/Domochip/WPalaControl)** | ESP8266 (D1 mini) | **Replaces the Connection Box** on Fumis boards: RJ11/RJ12 wiring, adapter PCB, box-compatible HTTP API, MQTT. | Closest prior art for a box-compatible API served by our ESP. |
| **[Domochip/Palazzetti](https://github.com/Domochip/Palazzetti)** | C++ library | The Fumis serial layer of the box (`fumisComReadByte/Word/Buff`, 38400 baud, 11-byte frames, addresses `0x2000`–`0x2100`). | Fumis address list; shows how the box maps its commands to board memory. |
| **[Domochip/WPalaSensor](https://github.com/Domochip/WPalaSensor)** | ESP8266 + DAC | Emulates the room NTC sensor. | Injecting a synthetic room temperature. |
| **[pm2036/palazzetti-firmware](https://github.com/pm2036/palazzetti-firmware)** | Shell | A Connection Box root filesystem (`www/`, `etc/`, `sbin/`…). | Compare with our own box binary in the private repo; the web UI JS lists commands. Proprietary content: study it, do not copy it here. |

## 5. Other brands (for contrast)

These use different controllers or cloud APIs; they are listed so they are not mistaken for compatible projects.

| Project | Target | Protocol | Notes |
|---|---|---|---|
| [AndreMiras/edilkamin.py](https://github.com/AndreMiras/edilkamin.py), [nghaye/ha-edilkamin](https://github.com/nghaye/ha-edilkamin), [algra4/ha-edilkamin](https://github.com/algra4/ha-edilkamin) | Edilkamin "The Mind" | cloud (AWS IoT) | No local bus. |
| [jer-nz/hottoh_api](https://github.com/jer-nz/hottoh_api) | Hottoh controllers (CMG, Edilkamin, MCZ) | HTTP/TCP | Neither Micronova nor Fumis. |

No open-source local protocol for MCZ Maestro boards was found.

## 6. Manuals and official documentation

- **Palazzetti technical documentation portal**: <https://palazzetti.it/assistenza-clienti/modulo-documentazione-tecnica/>
  (search by product code).
- **Palazzetti Ecofire manuals** on ManualsLib: <https://www.manualslib.com/products/Palazzetti-Ecofire-4217258.html>.
  The exact Ecofire Lara installer manual is not identified yet; our copies (user manual, SAV file, service menu)
  are in the reference repository's `resources/manuals/` and summarised in the
  [palazzetti-ecofire-lara](https://github.com/jordanauge/palazzetti-ecofire-lara) repo.
- **Micronova** (board maker): <https://www.micronovasrl.com/>. Board manuals (LO23, I023 LCD Idro, O047/T047)
  circulate on ManualsLib and Manualzz (*unverified*); they describe the service-menu parameters (PG/PF/P1…) that
  live in EEPROM.
- **Jotul Pellet Connection Box manual** (same box hardware as Palazzetti, multilingual):
  <https://www.jotul.fr/sites/french/files/products/MANUAL_PELLET_CONNEXION_BOX_FR_DE_NL_ES_EN_IT_PL_P02.pdf>.

## 7. Scaffolding: the WHR930 project

The repository layout, the ESPHome component structure, the example and override YAML files, the Makefile and the
PlatformIO tests follow **[jordanauge/esphome_whr930](https://github.com/jordanauge/esphome_whr930)**, an ESPHome
component for the Zehnder ComfoAir 350 / StorkAir WHR930 **ventilation unit (VMC)**. It is not a stove project;
its value here is the structure: a serial protocol kept apart from the entities, packets described in data,
`external_components` packaging, and docs plus figures per topic. Its own
[references](https://github.com/jordanauge/esphome_whr930/blob/master/doc/references.md) list the WHR930 projects
it builds on ([wichers/esphome-comfoair](https://github.com/wichers/esphome-comfoair) and others).

## 8. Our repositories

| Repository | Role | Content |
|---|---|---|
| [palazzetti](https://github.com/jordanauge/palazzetti) (this one) | public results | ESPHome component, memory maps, `plz` lab tool, docs |
| [palazzetti-ecofire-lara](https://github.com/jordanauge/palazzetti-ecofire-lara) | stove notes | Stove-level notes: manuals summary, service menu, maintenance |
| [palazzetti-connection-box-reverse](https://github.com/jordanauge/palazzetti-connection-box-reverse) | private investigation | Dumps, sessions, experiments, extracted working binaries and disassembly |
| [palazzetti-binaries](https://github.com/jordanauge/palazzetti-binaries) | private original packages | Versioned LabTools distributions, firmware packages, bootloaders and third-party archives |

[← README](../README.md) · [protocol](protocol.md) · [connection box](connection-box.md)
