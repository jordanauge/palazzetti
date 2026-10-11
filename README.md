# palazzetti

Local control and reverse engineering of Palazzetti / Micronova pellet stoves (developed on an **Ecofire Lara**)
with an ESP8266 on the stove's serial port.

**Memory atlas:** [GitHub Pages](https://jordanauge.github.io/palazzetti/) ·
[RAM map](https://jordanauge.github.io/palazzetti/memory-ram.html) ·
[EEPROM map](https://jordanauge.github.io/palazzetti/memory-eeprom.html).
The atlas is generated from the public map profiles, without private captures.

> **Board compatibility.** Palazzetti stoves have one of two controller board families. This repository implements
> the **Micronova** protocol (1200 baud, single wire), which is what the Ecofire Lara speaks. Newer Palazzetti
> stoves with a **Fumis** board (38400 baud, RJ11/RJ12) are **not supported**. See [boards.md](docs/boards.md) to
> tell them apart. Integrated in Home Assistant through **ESPHome**, built with
**PlatformIO**.

- **Everyday use**: temperatures, fans, power, state, errors; set points, power level, on/off, schedules once their
  addresses are confirmed.
- **Deep inspection**: any RAM/EEPROM byte as an entity, plus a TCP *lab server* to scan, watch, and write memory.
  A person or an AI agent can drive it with the `plz` tool to map undocumented parameters.

> ⚠️ Writing the wrong EEPROM byte can make a stove unsafe. Writes are disabled by default; read
> [reverse engineering § safety](docs/reverse-engineering.md#6-safety-rules).

## Repository map

| Path | Content |
|---|---|
| [components/palazzetti](components/palazzetti) | ESPHome external component (hub, entities, `palazzetti.write`, lab server) |
| [example/](example) | ready configurations; `*.entities.yaml` are generated from the maps |
| [maps/](maps) | **memory maps** (YAML, source of truth): generic Micronova layouts and stove profiles |
| [tools/plz](tools/plz) | reverse-engineering lab CLI: dump, watch, mark, diff, analyze, emulate, generate |
| [docs/](docs) | documentation (below) |
| [tests/](tests) | Python tests, host C++ codec test, ESPHome compile test |

## Documentation

| Page | Content |
|---|---|
| [boards.md](docs/boards.md) | Micronova vs Fumis controller boards: which one the Lara has, which one is implemented, how to check |
| [hardware.md](docs/hardware.md) | ESP8266 board, pinout, stove connector, wiring, assembly |
| [adapter.md](docs/adapter.md) | owner's diode/10 kΩ/NPN adapter versus MOSFET reference; UART swap and TX-only debug |
| [protocol.md](docs/protocol.md) | Micronova serial protocol: RAM/EEPROM read/write frames, checksum, timing, stove variants |
| [memory-map.md](docs/memory-map.md) | generated RAM/EEPROM map: common vs stove-specific addresses, status of each entry |
| [RAM hex map](docs/memory-ram.html) / [EEPROM hex map](docs/memory-eeprom.html) | offline interactive bytes, regions and struct members; profile selection, hover details and historical value evolution |
| [esphome.md](docs/esphome.md) | component architecture, build, configuration reference |
| [reverse-engineering.md](docs/reverse-engineering.md) | `plz` workflow for people and agents, analysis, safety, emulator |
| [acquisition.md](docs/acquisition.md) | repeated checked backups, editable autonomous polling plans and live evidence recording |
| [connection-box.md](docs/connection-box.md) | Palazzetti Connection Box: its API, and what its firmware can teach |
| [references.md](docs/references.md) | related projects (ESPHome, Micronova, Palazzetti/Fumis), protocol notes, manuals, scaffolding |
| [firmware.md](docs/firmware.md) | firmware identification and consolidated Lola/Martina findings |
| [menus.md](docs/menus.md) | observed Lara menu groups, read-only clock/settings and schedule limitations |
| [spare-parts.md](docs/spare-parts.md) | consolidated component references with public supplier/datasheet links |

## Quick start

```bash
uv tool install esphome                        # esphome drives PlatformIO
uv sync                                       # install lab tool and tests
cp example/secrets.yaml.example example/secrets.yaml   # only if absent; edit all secrets
make config
make build                                    # compile example/palazzetti-ecofire-lara.yaml
make upload                                   # first time over USB, then: make upload DEVICE=palazzetti.local
plz info                                      # lab server reachable?
plz inspect ram 0xF9                           # checked read with raw evidence
plz dump ram:0-0xFF                            # full RAM image
make test                                     # Python + C++ tests
```

Default: **NodeMCU Devkit V3 ESP-12F** (`nodemcuv2`).
Connect **D8 / GPIO15 → adapter transmit input**, **D7 / GPIO13 ← adapter receive output**,
and verified signal GND; see the [wiring diagram](docs/figures/hardware.2.nodemcu.svg)
and [hardware precautions](docs/hardware.md). Flash over USB with the stove disconnected;
then use OTA and Wi-Fi logs. Browse `http://palazzetti.local/` for the authenticated
ESPHome dashboard. Its Lara settings and schedule bytes are read-only: no confirmed
on/off command or safe write rule exists yet. Separate boot-disabled write/EEPROM switches
never bypass the address/value allowlist.

Keep the device hostname **`palazzetti`**: rebuild with `make build`, then upload
over Wi-Fi with `make upload DEVICE=palazzetti.local`. See
[OTA and device naming](docs/esphome.md#21-ota-and-device-name).

The device-hosted [uploaded-map dashboard](docs/esphome.md#37-uploaded-map-dashboard) at
`http://palazzetti.local/memory` uses plain JSON files instead of firmware-specific UI code.
Export with `plz gen-device-map palazzetti-ecofire-lara -o lara.json` and upload in the page.
Map files persist in flash; shared checked-read cache and byte polling overrides stay in RAM.
It is strictly read-only and reports unavailable/failed/stale values explicitly.

## Status

| Area | State |
|---|---|
| Component | compiles for NodeMCU V3 ESP-12F with web dashboard; codec/write-policy unit tested; on-stove validation pending |
| Adapter / connector | reference design documented; as-built values and stove connector pinout **to verify** |
| Ecofire Lara RAM | state machine (0xF9), fumes temperature, fan speeds, power observed on a 47 h capture; the generic Micronova addresses for status/room temperature do **not** apply |
| Ecofire Lara EEPROM | user settings and tentative chrono triplets documented from 2020 observations; service parameters and actual EEPROM capture still needed |

## Related repositories

- `palazzetti-ecofire-lara` (private): original manuals, website copies, diagrams,
  service dossier and source records. Public derived findings are in this repository's docs.
- `palazzetti-connection-box-reverse` (private): only the conclusions are published here.
  Raw captures, sessions, historical backup sketches and analysis projects
  live there; original software distributions are in the separate binary repository.
- `palazzetti-binaries` (private): LabTools versions,
  firmware packages, bootloaders and original third-party archives.

## Published memory atlas

[GitHub Pages memory atlas](https://jordanauge.github.io/palazzetti/) contains the RAM and EEPROM
hex maps, generated from the YAML profiles **without private capture data**. The
`Publish memory maps` GitHub Actions workflow tests and packages the atlas on changes to
the maps/docs and supports manual runs. It deploys when this repository is public.

Pages uses **GitHub Actions** as its source. The public repository starts with one
audited snapshot commit: original history, legacy firmware/assets, captures and original
documents are preserved privately, not attached as public branches or tags.
Only original implementation, consolidated Markdown documentation, structured maps,
small original SVG diagrams and generated capture-free HTML are published.
External references link to their public sources; no PDF, vendor binary or website mirror
is redistributed here. Private observation evidence remains explicitly labelled as such.

## License

[GPL-3.0](LICENSE). Palazzetti and Micronova are trademarks of their owners. This project is not affiliated with them.
