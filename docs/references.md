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
| **Micronova** | 1-wire half duplex, 1200 baud 8N2 | 2-byte read / 4-byte write, see [protocol.md](protocol.md) | Common examples use 8-bit addresses; our bridge-derived framing supports 13-bit addresses in separate RAM/EEPROM spaces | Ecofire Lara (**implemented here**), Extraflame, MCZ, Laminox, Ungaro, Artel, L'Asolana… |
| **Fumis** (Alpha) | serial, 38400 baud | 11-byte frames | 16-bit (`0x20xx`, `0x2100` serial number…) | newer Palazzetti (not implemented), Jotul, TurboFonte, Godin, Fonte Flamme, Invicta, Casatelli, Alpis, HETA |

The Ecofire Lara has a Micronova-protocol board, and only that protocol is implemented here; the evidence and
the full comparison are in [boards.md](boards.md). The Connection Box speaks to both (see
[connection-box.md](connection-box.md)). Fumis projects are listed in
§4 because their command lists and status codes overlap with ours, but their frames are not compatible with
the Micronova bus.

## 2. ESPHome implementations (Micronova)

| Project | Platform | Notes | Reusable for us |
|---|---|---|---|
| **[ESPHome `micronova`](https://esphome.io/components/micronova/)** ([source](https://github.com/esphome/esphome/tree/dev/esphome/components/micronova)) | ESPHome core | Official component: UART 1200 8N2, required `enable_rx_pin`, configurable entity addresses. Docs report testing on ExtraFlame Ketty Evo 2.0 and Ilary Top (2024), not Lara. | Independent transport/queue comparison, configuration vocabulary and philibertc optocoupler reference. Our transport handles echo rather than requiring RX gating; see detailed review below. |
| **[Jorre05/micronova](https://github.com/Jorre05/micronova)** | ESPHome external | Historical external implementation associated with the core component. | Compare specific revisions with upstream; do not assume fixes always land here first. |
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
| **[fabrizioromanelli/Pellet-Stove-Control](https://github.com/fabrizioromanelli/Pellet-Stove-Control)** ([README](https://github.com/fabrizioromanelli/Pellet-Stove-Control/blob/master/README.md)) | ESP8266/ESP32, MQTT | N100/D1 Mini implementation, optocoupler PCB, settings in LittleFS. README reports Ecofire Violetta 7 tested, not Lara. | Alternative command-request versus state-write paths; PCB and mapping workbook are references, not Lara compatibility evidence. |
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

Owner-supplied voltage references reviewed on 2026-10-12:

- [AllAboutCircuits: Logic Signal Voltage Levels](https://www.allaboutcircuits.com/textbook/digital/chpt-3/logic-signal-voltage-levels/):
  explains input/output thresholds and noise margin, including different TTL
  and CMOS ranges. Those textbook examples are not Lara receiver specifications.
  Content was retrieved during review; a subsequent request returned HTTP 403.
- [ba0sh1: Is ESP8266 I/O really 5V tolerant?](https://ba0sh1.com/2016/08/03/is-esp8266-io-really-5v-tolerant/):
  measured powered-input/released-open-drain tolerance up to 5.5 V on one setup.
  Explicitly excludes 5 V on push-pull outputs or the supply; not a lifetime,
  reset/unpowered or UART-HAT qualification. See [adapter analysis](adapter.md).
- The retained KIT SUPERVISORE, Italian I023 GEN_02, French I023 air and LabTools
  manuals were compared with the Lara owner manual. Their distinct board
  generations, storage descriptions and timing/state-code conflicts are
  summarized in [reference mapping notes](reference-mappings/README.md#controller-manuals-storage-and-version-dependent-meanings).
  Proprietary originals remain private; no new reference profile enters the atlas.

Not reviewed yet: [raziel83257/micronovaEsphome](https://github.com/raziel83257/micronovaEsphome),
[ArthurG94/Stove](https://github.com/ArthurG94/Stove),
[giovannidesisto/micronovaSupervisor](https://github.com/giovannidesisto/micronovaSupervisor).

### 3.1 Direct source review, 2026-10-12

The requested repositories, sketches and official documentation were reviewed
directly, not just collected as links. These are independent implementations or
related community work, **not independent confirmations of every shared address**.
Moving branch links above aid navigation; the source anchors below pin the
reviewed revisions. No controller script was executed or copied into our firmware.

| Source / reviewed revision | Material inspected | Derived findings and limitations |
|---|---|---|
| eni23, `f5ecf44f2327185c4b41bfb92825389cedaccf53` | [README](https://github.com/eni23/micronova-controller/blob/f5ecf44f2327185c4b41bfb92825389cedaccf53/README.md), [transport](https://github.com/eni23/micronova-controller/blob/f5ecf44f2327185c4b41bfb92825389cedaccf53/src/micronova_stove.cpp), [additional locations](https://github.com/eni23/micronova-controller/blob/f5ecf44f2327185c4b41bfb92825389cedaccf53/doc/stove-locations.md) | L'Asolana Marina, L023_7; ESP32 TCP/Python/optional web interface. RAM/EEPROM maps explicitly model-specific. Reports slow shutdown from a direct state write and a repeated IR-command request alternative; source `off()` uses simulated IR rather than the direct state path. |
| philibertc, `91e5dd4a8e259d16e09f25dff887c4a1d6878ed8` | [README](https://github.com/philibertc/micronova_controller/blob/91e5dd4a8e259d16e09f25dff887c4a1d6878ed8/README.md), [requested sketch](https://github.com/philibertc/micronova_controller/blob/91e5dd4a8e259d16e09f25dff887c4a1d6878ed8/micronova_controller.ino), linked wiki and PCB README | MQTT, software UART 1200 8N2, RX-enable optocoupler interface. Direct state-register commands and source-specific setpoint scaling. Source inspection reveals transaction-boundary and receive-buffer weaknesses; do not adopt as a checked acquisition engine. |
| fabrizio, `34195c650968d8684bcb5b9011aa25c1f1e27a40` | [README](https://github.com/fabrizioromanelli/Pellet-Stove-Control/blob/34195c650968d8684bcb5b9011aa25c1f1e27a40/README.md), [sketch](https://github.com/fabrizioromanelli/Pellet-Stove-Control/blob/34195c650968d8684bcb5b9011aa25c1f1e27a40/Pellet-Stove-Control.ino) | N100 reference with configurable Wi-Fi/MQTT, LittleFS, PCB and command workbook. ON uses an IR-style request location, OFF writes zero to state. This is not the same procedure as eni23 or the bridge. Its command MQTT publication is not proof of controller acknowledgement. |
| ESPHome dev, `8191cd18d27678705881522313153bec19a8fe9e` | [official documentation](https://esphome.io/components/micronova/), [transport](https://github.com/esphome/esphome/blob/8191cd18d27678705881522313153bec19a8fe9e/esphome/components/micronova/micronova.cpp), [switch](https://github.com/esphome/esphome/blob/8191cd18d27678705881522313153bec19a8fe9e/esphome/components/micronova/switch/micronova_switch.cpp), [sensor scaling](https://github.com/esphome/esphome/blob/8191cd18d27678705881522313153bec19a8fe9e/esphome/components/micronova/sensor/micronova_sensor.cpp) | Nonblocking queued transport, 200 ms reply timeout, byte-wrapped header-inclusive checksum, writes before reads, RX gated around transmit with UART flush. Switch uses controller-specific state assumptions and optimistic publication after enqueue, not verified completion. |

#### Encoding and storage evidence

- All four support the basic 1200 8N2, two-byte read/four-byte write framing.
  ESPHome's `memory_location` is a protocol header/location, **not an EEPROM base
  offset**; comparing it with our `mem` selector requires understanding the frame.
- RAM contains live sensors **and** working setpoints/state/timers. EEPROM stores
  persistent parameters, but writes may immediately change operating settings.
  eni23's claim that RAM is battery-backed and can be rewritten "safely" does not
  establish battery backing or safe actuation on Lara.
- eni23 reports ambient raw/2, unit-scale stored target, decimal live clock,
  BCD stored clock and ten-minute schedule units. The README lists RAM 7B twice
  (seconds and weekday), and swaps EEPROM F9/FA hour/minute relative to the
  supplied bridge; keep these discrepancies, do not resolve by copying a table.
- philibertc's sketch multiplies its target-temperature write by two; eni23
  and fabrizio use different stored representations/addresses. ESPHome makes
  thermostat step and sensor scaling configurable. Shared parameter names do
  not imply equal raw encodings or offsets.
- ESPHome's fan implementation returns zero for raw zero, otherwise
  `10*raw + fan_rpm_offset`. That zero case matters. eni23's proposed
  maximum-RPM/255 bias is not a calibrated conversion for Lara.
- Existing [Marina extraction](reference-mappings/micronova-marina.yaml) remains
  reference-only. No addresses or write rules from this review were promoted
  into the maintained Lara map.

#### Transport/code cautions found during review

- eni23's `flushInput()` drains `Serial`, not `StoveSerial`. Its reader wraps the
  two-byte buffer on extra bytes, does not require a complete reply before
  returning a value, and does not reject the checksum mismatch. Its
  checksum-minus-value address comparison omits the EEPROM header. These are
  useful warnings, not acquisition patterns to copy.
- philibertc's requested sketch drains arbitrary available bytes into a two-byte
  array without an index bound. Its ON path places `getStates()` and a one-second
  delay **inside the four-byte write loop**, interleaving reads with a partial
  command. That can disrupt command framing; it is source evidence, not proof
  of behavior on the owner's historical setup.
- fabrizio's current receive loop stops at two bytes, avoiding that particular
  overflow. However, response dispatch reconstructs an address from checksum
  minus value rather than validating against a stored outstanding request.
  EEPROM headers require special care; leftover or late bytes can be attributed
  to the wrong operation. `sendCommand()` does not verify a write reply.
- ESPHome explicitly requires a receive pull-up and an RX-enable output for its
  optocoupler circuit. Our continuously connected diode/BJT receive path is a
  different topology: adding an arbitrary enable pin or copying its UART pin
  choices would not implement RX gating on the owner's HAT.

#### Linked technical sources followed

The bounded follow-up covers relevant protocol, hardware and panel references.
Storefronts, donation links, badges and general site navigation are not protocol
evidence. "Linked" below is deliberately distinct from "content reviewed".

| Linked material | Review status and value |
|---|---|
| [philibertc PCB](https://github.com/philibertc/micronova_controller_pcb), [wiki](https://github.com/philibertc/micronova_controller/wiki), [build guide](https://github.com/philibertc/micronova_controller/wiki/How-to-build-it) | README/wiki source reviewed. Three optocouplers, wiki specifies 470 ohm resistors; fabrizio lists 510 ohm. These are circuit-specific, not replacements for our 10 kohm base resistor. Wiki GPIO35 RX-enable example on ESP32 is input-only on the classic ESP32: do not copy it as an output assignment. |
| [How it works](https://github.com/philibertc/micronova_controller/wiki/How-it-works), [Known issues](https://github.com/philibertc/micronova_controller/wiki/Known-issues), [Powering](https://github.com/philibertc/micronova_controller/wiki/Powering-the-circuit) | Protocol page delegates to ridiculouslab; known-issues/powering pages currently contain placeholder text, not completed validation guidance. |
| [Wiki compatibility](https://github.com/philibertc/micronova_controller/wiki/Compatible-stoves-and-boilers), [upload guide](https://github.com/philibertc/micronova_controller/wiki/How-to-upload-the-firmware), [MQTT guide](https://github.com/philibertc/micronova_controller/wiki/Configuring-MQTT-on-your-home-automation-server), [kit guide](https://github.com/philibertc/micronova_controller/wiki/User-guide-for-the-PCB-kit-(english)), [community discussion](https://github.com/philibertc/micronova_controller/discussions/63) | Discovered from README/wiki navigation; contents not reviewed in this pass. Relevant support/setup leads, not Lara compatibility proof. |
| [fabrizio schematic](https://github.com/fabrizioromanelli/Pellet-Stove-Control/blob/master/PCB/Schematics.png), [PCB sources](https://github.com/fabrizioromanelli/Pellet-Stove-Control/tree/master/PCB), [mapping workbook](https://github.com/fabrizioromanelli/Pellet-Stove-Control/blob/master/docs/micronova_stove_commands_mapping.xlsx) | Linked reference artifacts; directory presence and README description checked. Image netlist and workbook cells not independently analysed in this pass. Do not treat them as extracted Lara data. |
| [k3a serial/IR article](https://k3a.me/ir-controller-for-pellet-stove-with-micronova-controller-stufe-e-pellet-aria-ir-telecomando/) | Reviewed text: distinct PNP/diode experiment and later NPN/protection circuit, model-specific voltage/pinout observations and dependence of echo on electrical thresholds. Does not identify the owner's transistor or certify GPIO protection. |
| [k3a LCD/panel investigation](https://k3a.me/micronova-pellet-stove-lcd-reverse-engineering/), [panel sketch](https://github.com/k3a/MicronovaPelletStoveController/blob/master/StufaLCD.ino), [pinout](https://github.com/k3a/MicronovaPelletStoveController/blob/master/pinouts.png), [board design](https://github.com/k3a/MicronovaPelletStoveController/tree/master/esp_eagle) | LCD article text reviewed: clock/data and ABC multiplexing drive segments and scan buttons; IR is another signal. The panel is not automatically a UART client. Sketch/image/board artifacts are linked for future bench identification, not tested on Lara. |
| [Arduino-IRremote](https://github.com/shirriff/Arduino-IRremote), [IR background](https://learn.sparkfun.com/tutorials/ir-communication), [HC42 decoder datasheet](https://www.ti.com/lit/ds/symlink/sn54hc42.pdf) | Discovered through k3a; contents not reviewed here. Relevant to a separately identified IR/LCD panel interface, not our serial decoder. |
| [ridiculouslab current page](https://www.ridiculouslab.com/arguments/iot/stufa/micronova_en.php), [older converter URL](https://ridiculouslab.altervista.org/en/micronova-protocol-converter/) | Current URL returned HTTP 406 in this pass; previous 2026-10-11 review remains recorded. Older host failed DNS resolution. No claim of a successful fresh re-review. |
| [StufaPellet linked topic 57458738](https://stufapellet.forumcommunity.net/?t=57458738), [original topic 53061907](https://stufapellet.forumcommunity.net/?t=53061907) | eni23 links the first; k3a links the second. Topic 57458738 redirected to login; no authenticated content extracted. Original topic retains prior historical provenance. |

#### Reuse and investigation decisions

Keep our checked, read-only acquisition engine. Prioritise receive-state tests,
late/extra-byte diagnostics and distinguishing command submission from confirmed
controller behavior. Do not add automatic state writes, forced shutdown or IR
request replay based on another stove's examples.

For the spare panel, first identify its connector and electronics: k3a provides
a concrete counterexample to the assumption that every panel uses the external
serial bus. If ours uses multiplexed button/display signals, capture those rather
than trying to decode them as 1200-baud UART.

License notices also constrain reuse: eni23 and fabrizio include GPLv3 notices;
philibertc's current software README specifies CC-BY-NC-SA with a historical
CC-BY-NC-ND boundary, while its PCB README specifies CC-BY-NC-ND. Credit derived
facts and check the exact file/revision terms before importing code or designs.

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
