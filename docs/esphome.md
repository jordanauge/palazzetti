# ESPHome component

[← README](../README.md) · [hardware](hardware.md) · [memory map](memory-map.md) · [reverse engineering](reverse-engineering.md)

`components/palazzetti` is an ESPHome external component that speaks the [Micronova protocol](protocol.md). It is
built like any ESPHome firmware: ESPHome generates a PlatformIO project and PlatformIO fetches the ESP8266
toolchain and framework, so no separate Espressif toolchain is needed.

## 1. Architecture

![Component architecture](figures/esphome.1.architecture.svg)

**Figure 1**: One `palazzetti` hub owns the UART and a request queue. Entities (sensor, text sensor, number,
switch) and the `palazzetti.write` action enqueue reads/writes; the optional lab server shares the same queue, so
interactive commands from `plz` never collide with entity polling.

| File | Role |
|---|---|
| [micronova.h](../components/palazzetti/micronova.h) | frame building and reply checks, pure C++ (host-tested) |
| [write_policy.h](../components/palazzetti/write_policy.h) | central address/value allowlist and volatile RAM/EEPROM permission gates |
| [polling_plan.h](../components/palazzetti/polling_plan.h) | bounded volatile range scheduler; shared hub keeps checked plan results |
| [read_cache.h](../components/palazzetti/read_cache.h) | bounded volatile cache of final checked reads, shared by entities, lab and map dashboard |
| [map_web.cpp](../components/palazzetti/map_web.cpp), [map_web.html](../components/palazzetti/map_web.html) | optional authenticated dashboard and persistent JSON-map storage |
| [palazzetti.h](../components/palazzetti/palazzetti.h), [palazzetti.cpp](../components/palazzetti/palazzetti.cpp) | hub: queue, UART state machine, echo handling, retries, statistics |
| [bus_entity.h](../components/palazzetti/bus_entity.h), [bus_entity.cpp](../components/palazzetti/bus_entity.cpp) | sensor / text sensor / number / switch bound to one address |
| [lab_server.h](../components/palazzetti/lab_server.h), [lab_server.cpp](../components/palazzetti/lab_server.cpp) | TCP line protocol for the [lab tool](reverse-engineering.md) |
| `__init__.py`, `sensor.py`, `text_sensor.py`, `number.py`, `switch.py` | configuration schema and code generation |

## 2. Build

```bash
uv tool install esphome             # brings PlatformIO; no separate ESP toolchain
uv sync                            # lab tool and tests
cp example/secrets.yaml.example example/secrets.yaml   # only if no secrets file exists
make config                         # validate configuration after editing secrets
make build                          # esphome compile example/palazzetti-ecofire-lara.yaml
make upload DEVICE=/dev/cu.usbserial-xxxx   # first flash over USB; later: DEVICE=palazzetti.local
make logs
```

Use a USB data cable and select the actual serial device path for the first upload.
Disconnect the stove and adapter during flashing. Fill **all** entries in
[secrets.yaml.example](../example/secrets.yaml.example), including API encryption, OTA,
fallback AP and web credentials; use unique passwords. Do not overwrite an existing secrets file.
The default board is `nodemcuv2`, the PlatformIO definition used for NodeMCU V3 ESP-12F.
After connecting to Wi-Fi, use `make upload DEVICE=palazzetti.local` for OTA and
`make logs DEVICE=palazzetti.local` for logs. Runtime logs are not on the USB UART.
No upload is needed to inspect build output; compilation does not touch the stove.

Other targets: `make test` (Python + host C++ tests), `make test-compile` (every platform/option), `make gen`
(regenerate the memory map doc and entity packages from `maps/`).

If PlatformIO fails to download a package (e.g. TLS errors on a registry mirror), it retries other mirrors. A
package can also be installed from a local archive (`pio pkg install -g -t file:///path/pkg.tar.gz`); then make sure
its `.piopm` carries `"owner": "platformio"` so that ESPHome's `platformio/<name>` requirement matches it.

### 2.1 OTA and device name

The selected device name is **`palazzetti`**, set by the base package's `name`
substitution and used by `esphome.name`. Keep it independent of the profile:
`palazzetti-ecofire-lara.yaml` describes the Lara configuration, not the hostname.
The friendly display name is **Palazzetti stove**. `ecofire`, `ecofire-lara` and
`lara` would be valid alternative device names, but are **not aliases** of the
currently flashed device.

| Identifier | Current value |
|---|---|
| Firmware project / component | `palazzetti` |
| Device name / mDNS host | `palazzetti` / `palazzetti.local` |
| Configuration profile | `palazzetti-ecofire-lara` |
| Wi-Fi fallback AP | `palazzetti fallback` |
| OTA transport | ESPHome native OTA, TCP **8266** on ESP8266 |

After the initial USB flash, build and upload over Wi-Fi:

```bash
make build
make upload DEVICE=palazzetti.local
# If mDNS is unavailable, use the actual current DHCP address:
make upload DEVICE=192.168.0.235
make logs DEVICE=palazzetti.local
```

`make upload` uploads the already compiled image; rebuild after changing source
or YAML. Alternatively, `esphome run example/palazzetti-ecofire-lara.yaml
--device palazzetti.local` builds, uploads and then follows logs.
Use the same ignored secrets file: native OTA uses **`ota_password`**, whereas
Home Assistant/network logs use **`api_key`** and HTTP uses web credentials.
ESPHome reads those automatically; do not paste passwords into CLI arguments.
The IP above is a deployment example and can change with DHCP.

OTA requires reachable Wi-Fi (ESP8266 supports **2.4 GHz only**) and sufficient
firmware space. It does not require a stove/HAT connection or UART pins.
It updates the ESP, not stove firmware. Normal OTA preserves the uploaded
LittleFS maps; runtime cache/overrides reset on reboot. Keep power stable during
an update, and retain USB recovery access. Do not expose OTA/HTTP/lab ports to
the Internet.

Serial pin routing and the separate TX-only debug UART are explained in the
[adapter guide](adapter.md#3-uart0-before-and-after-serialswap).

## 3. Configuration

The example is split in three packages:

- [palazzetti-base.yaml](../example/palazzetti-base.yaml): board, Wi-Fi, API, UART, hub, lab server;
- [palazzetti-ecofire-lara.entities.yaml](../example/palazzetti-ecofire-lara.entities.yaml): one entity per known
  address, **generated** from [maps/palazzetti-ecofire-lara.yaml](../maps/palazzetti-ecofire-lara.yaml)
  (`plz gen-esphome`). Hypotheses are created `disabled_by_default`.
- [palazzetti-web.yaml](../example/palazzetti-web.yaml): native ESPHome web server, diagnostic entities,
  network time, permission switches, encrypted native-API read action and uploaded-map dashboard.
  Remove this package to omit both dashboards.

[palazzetti-ecofire-lara.yaml](../example/palazzetti-ecofire-lara.yaml) includes all three. For another stove, add a
profile in `maps/` and generate its package.

### 3.1 Hub

```yaml
uart:
  id: stove_uart
  tx_pin: GPIO15
  rx_pin: GPIO13
  baud_rate: 1200
  stop_bits: 2

palazzetti:
  id: stove
  uart_id: stove_uart
  echo: auto            # auto | true | false: own frames echoed on RX (1-wire adapter)
  reply_timeout: 300ms
  frame_gap: 30ms
  max_retries: 2
  max_queue: 48
  lab_server:           # optional, see reverse-engineering.md
    port: 6638
    allow_write: false  # additional compile-time permission for lab w; raw writes never allowed
  write_allowlist: []   # generated from separately confirmed write evidence; Lara currently empty
```

### 3.2 Entities

All platforms share `palazzetti_id`, `memory` (`ram` default, or `eeprom`), `address` (0x0000–0x1FFF), `encoding`
(`uint8`, `int8`, `bcd`, `uint16_be`, `uint16_le`, `int16_be`, `int16_le`) and `update_interval`.

```yaml
sensor:
  - platform: palazzetti
    name: Fumes temperature
    address: 0x42
    unit_of_measurement: °C
    update_interval: 30s

text_sensor:
  - platform: palazzetti
    name: Power state
    address: 0xF9
    map: {0x1A: "off", 0x2B: ignition, 0x4B: working, 0x1D: final cleaning}

```

`number` and `switch` platforms remain available for a controller with verified write semantics;
`number` uses `displayed = raw * multiply + offset`, with positive `multiply`.
Every write, including custom entities and automations, must pass the hub policy.
Multi-byte entity writes are refused because sequential bus transactions are not atomic.
The switch defaults to `restore_mode: DISABLED`: it never restores a stove write at boot.
The Lara package generates read-only sensors for its observed settings. Nested chrono bytes
are hypotheses, marked `(?)`, with 300-second polling. `disabled_by_default` hides an entity
initially in Home Assistant but does **not** stop polling; remove unwanted entities or use lab `pause`.

### 3.3 Action

The `palazzetti.write` action accepts `id`, `memory`, `address` and a templatable byte `value`.
It does not bypass the policy. Do not add Lara power or schedule actions until command evidence is established.

### 3.4 Web dashboard and write mode

Browse `http://palazzetti.local/` (or its IP), using your web credentials. The native ESPHome
dashboard displays stove state, temperatures, power/fan settings, stove clock bytes, chrono
bytes and bus diagnostics. The SNTP **Network clock** is separate from the stove clock;
it does not synchronize or write stove time. Unknown schedule encodings are not a working scheduler.
The standard ESPHome v3 frontend loads assets from ESPHome's CDN and needs browser Internet access.

**Stove write mode** and **EEPROM write permission** both start off and are not restored.
Turning the general mode off revokes EEPROM permission and cancels pending writes at dispatch.
It cannot undo an already transmitted command. EEPROM permission also requires general mode.
Neither switch grants arbitrary memory access: address, memory and byte value must match a
confirmed rule. The current Lara rule count is **zero**, so toggling either mode cannot write
stove settings. EEPROM writes persist and need stronger evidence than RAM observations.

The web server uses Basic authentication over HTTP, not TLS. Use a trusted isolated LAN;
do not forward its port or the unauthenticated TCP lab port to the Internet.
With the current ESP8266 web library, keep `username:password` at most 53 UTF-8 bytes:
longer credentials hit a Base64 line-break incompatibility. A 32-character random hex
password (128 random bits) fits with `admin`. Map-web configuration rejects this known
failure case. Digest authentication avoids it; select `auth.type: digest` on ESPHome
versions supporting that option, and use curl `--anyauth`.

### 3.5 Native API read action

Home Assistant exposes `read_memory` through the encrypted ESPHome API. Its integer arguments
are `memory` (0 RAM, 1 EEPROM) and `address` (0..8191). The action queues a checked read
and publishes **Last API memory read**, including validity, reply length, checksum result,
attempt count and final-attempt latency. Invalid arguments and full queues publish errors.
For machine-readable complete byte evidence and session logging, use `plz inspect`;
this text entity only retains the latest action result.

### 3.6 Autonomous polling

The hub has a volatile 32-range read plan, stopped/empty at boot, plus a bounded
32-result drain buffer. The lab API and native actions edit it without reflashing.
It continues between client connections but never writes to the stove or ESP flash.
See [acquisition.md](acquisition.md) for periods, fairness, runtime capacity,
gap/reboot handling, CLI recording and repeated baseline backups.

### 3.7 Uploaded-map dashboard

Browse `http://palazzetti.local/memory` using the same credentials as the native dashboard.
This page is fully device-hosted, with no CDN dependency. It displays arbitrary mapped
fields without regenerating firmware or ESPHome entities. Its only stove operations are
**reads**. The page reports absent data, final read failures, pending requests and stale
values separately; a disconnected stove is not represented as zero.

The optional hub configuration is `map_web: {}`. It currently requires one ESP8266 hub
and an authenticated `web_server`. The standard example enables it. Flash files persist;
cache entries and polling overrides are volatile. Neither file uploads nor interval changes
grant any stove write permission.
The web package selects PlatformIO `board_build.ldscript: eagle.flash.4m1m.ld` for the
4 MiB NodeMCU, reserving roughly 1 MiB for LittleFS while retaining firmware/OTA space.
ESPHome's default `eagle.flash.4m.ld` has **no filesystem space**. For another board,
choose an explicit linker layout with a filesystem region that fits its actual flash;
do not reuse the 4 MiB layout on a smaller module.

Generate a compact map from the existing YAML source:

```bash
plz gen-device-map palazzetti-ecofire-lara -o lara.json
# Narrow the map or include explicitly selected hypotheses:
plz gen-device-map palazzetti-ecofire-lara \
  --field power_state --field fumes_temperature \
  --field chrono_programs.program_1.start --interval-ms 30000 -o focused.json
```

The default export includes located `observed`/`confirmed` scalar fields only.
Explicit selection preserves hypothesis/reported/refuted status; it does not verify
applicability. Struct leaves use dotted IDs. Unlocated parameters never get guessed
addresses, and raw byte arrays require named scalar members or separate custom fields.
Evidence remains in the public atlas/YAML; a compact device file is a display
description, not a replacement for source provenance.

Select the JSON file and click **Upload maps**. On a new board whose LittleFS partition
cannot mount, first explicitly initialize storage. **Initialization formats that partition**:
never use it on a board containing files you need to recover. Startup does not auto-format.
Initialization is refused when the filesystem already mounts. A valid upload is written
to a staging file and atomically renamed before activation; invalid or interrupted uploads
leave the previous stored/active map intact. Boot ignores a leftover staging file and logs
invalid stored maps. Normal USB firmware uploads and OTA do not upload/erase this partition;
an entire-chip erase or changed flash layout can remove it.

The plain file format supports up to four simultaneous map groups:

```json
{"format":1,"maps":[{"id":"lara","name":"Lara","interval_ms":15000,"fields":[
  {"id":"state","name":"Power state","mem":"ram","addr":249,"width":1,
   "encoding":"uint8","values":{"26":"off","43":"ignition","75":"working"},
   "status":"observed"},
  {"id":"target","name":"Target temperature","mem":"eeprom","addr":78,
   "unit":"C","scale":1,"offset":0,"interval_ms":60000,"status":"observed"}
]}]}
```

Addresses and periods are **decimal integers** in JSON. Map IDs and field IDs within
each map must be unique (1..80 characters). Supported encodings are `uint8`, `int8`,
`bcd`, `uint16_le`, `uint16_be`, `int16_le`, `int16_be`; 16-bit fields require `width:2`,
all others `width:1` (the default). Conversion is `raw * scale + offset`, with defaults
1 and 0. Enum keys refer to the decoded raw integer before conversion. Enum labels,
names, units and evidence statuses are displayed as text, never executable HTML.

Limits: **8192 file bytes, 48 fields total, 64 unique memory bytes**, addresses
0..8191 and periods 100..86400000 ms. Installed memory capacity is still unverified.
Low parsing heap or a concurrent upload can also reject a file explicitly; use smaller focused maps.
The page reports free heap. All uploaded groups poll continuously; the dropdown changes
display only. A single stored JSON document contains the groups; uploading replaces it.

For each shared byte, the shortest declared map/field period wins. A byte-specific runtime
override takes precedence, even when slower. Enter **0** to restore its declared cadence.
The UI applies both bytes of a word independently; shared/overlapping fields see the same
override. Overrides reset on reboot or a successful map upload.

Every final checked read from entities, lab requests or either scheduler updates the same
128-entry cache. Failures invalidate that value; writes invalidate it too, because an
acknowledgement is not independent read evidence. Cache entries are replaced cyclically
when full. The map scheduler skips fresh cached bytes and queued/in-flight reads, queues
at most one of its own requests at a time, and respects the hub's lab `pause` state.
An interval is a freshness target, not a guaranteed sampling rate: 1200-baud transactions,
retries and other clients limit throughput. Unsuccessful attempts are paced as well.
Existing entity/lab schedules can still read more frequently than a dashboard override.
`poll stop` stops the lab plan only; use `pause` to pause entities and map polling too,
as the backup CLI already does.

Multi-byte fields are assembled from individually checked bytes and **are not atomic**.
The page shows each byte's age. It is a live view, not a history recorder;
use [acquisition.md](acquisition.md) for retained samples and checked backups.

All routes below inherit ESPHome's authenticated handler wrapper:

| Method | Path | Result |
|---|---|---|
| GET | `/memory` | generic offline-capable HTML/JS |
| GET | `/memory/map` | stored JSON document, or explicit 404 |
| POST | `/memory/map` | raw JSON body, validate/store/activate |
| GET | `/memory/cache` | boot ID, uptime, free heap, pause/storage state and mapped-byte validity/value/error/age/pending/staleness/cadence |
| POST | `/memory/override` | form fields `mem`, `addr`, `interval_ms`; mapped bytes only, 0 restores default |
| POST | `/memory/initialize` | form field `confirm=INITIALIZE`; explicit filesystem format, only while unmounted |

For scripted use, curl prompts for the password rather than embedding it in command history:

```bash
curl --fail-with-body --user admin -H 'Content-Type: application/json' \
  --data-binary @lara.json http://palazzetti.local/memory/map
curl --fail-with-body --user admin http://palazzetti.local/memory/cache
curl --fail-with-body --user admin \
  --data 'mem=ram&addr=249&interval_ms=1000' http://palazzetti.local/memory/override
```

Uploads stream to the staging file and parsing retains only scheduling/conversion metadata;
display labels/enums stay in the file and browser, not ESP RAM. Cache responses stream
bounded snapshots rather than constructing a whole JSON response in heap.
Basic authentication still runs over HTTP: use only a trusted LAN. Private map uploads
may contain personal settings labels; do not publish files containing captures or credentials.

## 4. Tests

- `tests/test_micronova.cpp`: host tests of the codec, policy, plan and cache (`make test-cpp`).
- `tests/test_*.py`: codec mirror, maps, sessions/analysis, emulator ↔ client round trip (`make test-py`).
- `tests/compile-esp8266.yaml`: compiles every platform and the action (`make test-compile`).
- `tests/test_memory_html.cjs`: real Chrome tests of atlas interactions and the uploaded-map
  dashboard with mocked HTTP responses. Live upload/reboot tests require a connected ESP.
- `PLZ_DEVICE_URL=http://palazzetti.local .venv/bin/python -m pytest tests/test_device_web.py`
  opts into live HTTP tests using the ignored local web credentials. It temporarily replaces
  then restores the existing map; storage must already be initialized and contain a map.
  This checks authentication, invalid bounds/encodings, exact 8 KiB uploads, the 64-byte
  response limit, overrides and interrupted-upload recovery. Set the same environment
  variable when running the Chrome test to exercise the real file-picker upload workflow.

[← README](../README.md) · [reverse engineering →](reverse-engineering.md)
