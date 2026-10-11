# Palazzetti Connection Box

[← README](../README.md) · [reverse engineering](reverse-engineering.md) · [memory map](memory-map.md) · [references](references.md)

The Connection Box ("ConnBox", also built into some recent stoves) is Palazzetti's Wi-Fi/Ethernet module for the
stove. It plugs on the same serial port as this project's adapter, polls the controller, and exposes the values
over a local HTTP API used by the Palazzetti app and by Home Assistant.

Its firmware therefore contains what this project tries to recover: **a table from API fields to controller
RAM/EEPROM addresses, per stove family**. Extracting it is the most direct path to a complete memory map.

## 1. Local HTTP API (public knowledge)

The API is documented by community clients such as
[dotvav/py-palazzetti-api](https://github.com/dotvav/py-palazzetti-api) (used by the Home Assistant `palazzetti`
integration), [Vost3/hass-palazzetti](https://github.com/Vost3/hass-palazzetti) and
[marcopal74/palazzetti_local_api](https://github.com/marcopal74/palazzetti_local_api); the full list, with
box replacements such as Domochip/WPalaControl, is in [references.md](references.md#4-palazzetti-connection-box-and-fumis).

```text
GET http://<box>/cgi-bin/sendmsg.lua?cmd=<COMMAND>
```

| Command | Effect |
|---|---|
| `GET STAT` | online check |
| `GET STDT` | static data: model, firmware versions, capabilities |
| `GET ALLS` | live state: status code, temperatures T1–T5, set point, power, fans, pellet quantity |
| `SET SETP <t>` | target temperature |
| `SET POWR <1-5>` | power level |
| `SET RFAN <n>`, `SET FN3L`, `SET FN4L`, `SET SLNT 1` | main/left/right fans, silent mode |
| `CMD ON`, `CMD OFF` | switch on/off |

Other commands found in the firmware (2020 notes; meanings inferred from names, not all verified):

| Group | Commands |
|---|---|
| read | `GET CHRD` (chrono), `GET TMPS` (temperatures), `GET IOPT` (inputs/outputs), `GET DPRS` (pressure), `GET FAND` (fans), `GET SETP`, `GET MDVE` (model/version), `GET FWST`, `GET TIME`, `GET PARM` / `GET HPAR…` (parameters), `GET RFAN`, `GET POWR` |
| write | `SET CPRD`, `SET CSST`, `SET CDAY`, `SET CSTH`, `SET CSTM`, `SET CSPH`, `SET CSPM`, `SET CSET` (chrono programs), `SET TIME`, `SET TOUT`, `SET DOUT`, `SET PARM`, `SET LMAX`, `SET LMIN`, `SET HPAR…`, `SET STAT` |
| extended | `EXT FWUP` (firmware update), `EXT LMXL`, `EXT LMNL`, `EXT PARL`, `EXT HPRL`, `EXT STDT`, **`EXT ADRD` / `EXT ADWR`** (raw address read/write) |

`EXT ADRD` / `EXT ADWR` appear to give raw memory access through the box. With a box on the stove, they would
allow reading the Lara's memory without our adapter, and cross-checking our reads.

`GET ALLS` fields include `MBTYPE`, `FWDATE`, `STOVE_DATETIME`, `STATUS`, `SETP`, `POWER`, `RPOWER`, `FEEDER`,
`FAN_FAN1V`, `FAN_FAN1RPM`, `FAN_FAN2LEVEL`, `FAN_FAN2V`, `DP_TARGET`, `DP_PRESS`, `PELLET_QTUSED`,
`IN_I01..04`, `OUT_O01..06` and `TMP_*` probes. Some exist only on some models.

The status codes the API reports (`0` off, `2` test fire, `3` heat-up, `4` fueling, `5` ignition test, `6` burning,
`7` burning modulating, `9` cooling, `10` fire stop, `11` clean fire, `241`–`253` alarms…) are an **abstraction**
computed by the box. On the Ecofire Lara, the controller's own state register (RAM 0xF9) uses other codes
(0x1A off, 0x2B ignition, 0x4B working, 0x1D final cleaning; see the [memory map](memory-map.md)). The box firmware
contains the translation.

## 2. What we already know from the firmware

A first pass on the box firmware in 2020 (IDA) found that:

- the serial daemon reads a **board/model code at RAM 0x0D** first; the code is tied to a `micronova_code` table;
- it then uses **model-dependent address sets**: target temperature at RAM 0x36 (one model) or 0xA0; power at
  0x37/0x64 or 0x97/0x34;
- `SET STAT` writes RAM 0x21, and `GET PARM` reads the EEPROM from 0x28.

They are recorded as `reported` in [the reference extraction](reference-mappings/palazzetti-connbox.yaml), not the maintained map. On the Lara,
RAM 0x0D is constant 232 and RAM 0x21 is constant 5. So the Lara is probably on another branch of these tables:
finding the branch for code 232 is the next step.

## 3. What we want from the firmware

| Question | Where it helps |
|---|---|
| Address and scale of every `GET ALLS`/`GET STDT` field, per stove family | reference hypotheses; promote only Lara-applicable evidence to [its map](../maps/palazzetti-ecofire-lara.yaml) |
| How the box identifies the stove (model / firmware registers) | identifies which software branch may apply to Lara |
| Exact frames used for `CMD ON/OFF`, `SET POWR`, `SET SETP`, chrono | safe write paths for the [ESPHome component](esphome.md) |
| Serial timing, retries, echo handling | validates the [protocol](protocol.md) notes |
| Names, ranges and order of the technical parameters (the service-menu tables) | names for EEPROM blocks |

## 4. Where the artefacts live

Original binaries, firmware images and service/flash software stay in private
`palazzetti-binaries`. Disassembly, raw captures and investigation artifacts stay in
private `palazzetti-connection-box-reverse`; original manuals and website copies belong
in private `palazzetti-ecofire-lara`. Only consolidated conclusions are published here:
addresses, scales, meanings, frames and evidence keys. Private observation/disassembly
provenance is not represented as an independently accessible public reference.

## 5. Method

1. Identify the box's platform and unpack its filesystem; the HTTP handler is a Lua CGI (`sendmsg.lua`).
2. Follow `sendmsg.lua` to the daemon that owns the serial port, and find the command → frame tables.
3. Cross-check each candidate with a live session: `plz watch` + the box's own API on the same stove
   ([reverse engineering](reverse-engineering.md)), or with a capture of the box's serial traffic.
4. Promote the results in `maps/` (`sources: [connbox-fw]`).

[← reverse engineering](reverse-engineering.md) · [references →](references.md)
