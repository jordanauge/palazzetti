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
may contain translations for supported controllers; a Lara-specific translation has
not been identified in the supplied build.

## 2. What we already know from the firmware

The supplied `plzbridge` executable has SHA-256
`4fedc1bc89e47c1448dec277e6b9d5f2c44e6b5265aa7c86ea0818c4475b7562`.
Its IDA assembly export identifies the same binary by MD5
`69055a2889734015f2bc6b1b6db4c2d6`. Static inspection corrects two historical
assumptions: **branch selection reads RAM 0x6E, not 0x0D**, and **`GET PARM n`
reads EEPROM address n directly, not a block based at 0x28**.

| Derived fact for this build | Evidence anchor |
|---|---|
| RAM 6E: raw 1/2/3 selects Micronova types 12/13/14; other accepted values fall back to type 11 | `40D7F8` |
| RAM 0D is decoded as `FEEDER = raw/10`, not a model code | `40D98C`; `GET ALLS` output |
| Type 11 target is RAM 36, integer raw/2; other types use RAM A0 | `40DB74` |
| Type 11 `POWER`/`RPOWER` use RAM 37/64; other types use RAM 97/34 | `40D98C` |
| Room/water probe uses RAM 01, raw/2; type 11 exhaust uses RAM 02, raw+30; others use big-endian RAM 3D–3E | `40E7B0` |
| Extractor RPM uses RAM 67 (type 11) or 48 (others): zero if raw=0, otherwise 10*raw+250 | `40E5C4` |
| Word reads combine two separate byte transactions, high byte first | `40CA3C` |
| `GET PARM` accepts 1..200; `EXT PARL` exposes a 47-byte cache loaded from EEPROM 00–2E in chunks of 24 | `40DC78`, `40E054`, `401C80` |
| The PHP service table displays parameter number n using zero-based cache index n-1 | supplied parameter frontend |
| `GET CHRD` rejects the Micronova family as unsupported | `402794` |
| `CMD ON/OFF` performs several preparation writes before writing RAM 21, rather than one universal state write | `40F198`, `40F390` |

These are **build-specific reference layouts**, retained in
[the reference extraction](reference-mappings/palazzetti-connbox.yaml), not new
Lara mappings. Lara's RAM 0D constant 232 remains unidentified; it does not
establish “model 232” or a feeder duration. Its RAM 21 constant 5 and state at
F9 contradict a straightforward use of the box layout. No verified Lara match
has been found in this binary or the supplied LabTools firmware packages.

The service table supplies useful **encoding search hypotheses**: auger raw/10
seconds, extractor 10*raw+250 RPM, convection 5*raw+60 volts, selected temperature
thresholds raw+30 or raw+245 and maintenance raw*100 hours. Do not import its
row numbers, defaults or bounds into Lara. A repeated EEPROM backup and paired
panel readings are still required.

The separate Lua frontend caches successful `GET STDT` replies and handles
`GET/SET JTMR` as box-side timers. Web scheduling controls therefore do not prove
a stove EEPROM schedule layout, nor that the Lua snapshot matches this ELF.

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

1. Identify each binary by hash and keep PHP/Lua frontend versions separate.
2. Follow the handler to the serial daemon, distinguishing live wire reads from box-side caches/timers.
3. Cross-check each candidate with a live session: `plz watch` + the box's own API on the same stove
   ([reverse engineering](reverse-engineering.md)), or with a capture of the box's serial traffic.
4. Keep derived other-board facts in `docs/reference-mappings/`. Promote only
   independently supported Lara findings into `maps/`, with claim-level evidence.

[← reverse engineering](reverse-engineering.md) · [references →](references.md)
