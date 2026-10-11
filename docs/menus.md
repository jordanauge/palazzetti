# Lara menus and settings

[README](../README.md) · [memory map](memory-map.md) · [firmware](firmware.md)

This page consolidates owner observations and the register findings. It is not a
copy of a service manual and does not establish factory defaults. The installed
controller revision and firmware have not yet been identified.

## User settings and clock

The 2020 Lara observations associate EEPROM `0x4C`, `0x4D` and `0x4E`
(decimal 76, 77 and 78) with selected power, room-fan level and target temperature.
These are **observed reading semantics**, not verified write commands.
RAM `0x65` and `0x66` reflect power and fan settings in the current profile.
RAM `0x5E`/`0x5F` are BCD minutes/hours; `0x60` is the weekday field.
See the [map](memory-map.md) for scales, enums, evidence and competing annotations.

The ESPHome dashboard displays these values without modifying them. Its SNTP
network clock is separate from the stove clock. The schedule block at EEPROM
`0x3B..0x4C` is a tentative six-triplet interpretation, overlapping the observed
power byte at `0x4C`. Do not treat it as a proven writable scheduler.

## Observed service-menu groups

Owner notes record these display headings; exact access paths vary with firmware:

| Display heading | Conservative interpretation |
|---|---|
| `MENU SAV` | Service parameters |
| `MENU INSTALLAT.` | Installation configuration |
| `MENU DEFAULT` | Defaults-related menu; behaviour not tested |
| `MENU TEST SORTIES` | Output-test menu |
| `MENU NETTOYAGE BRA` | Burn-pot cleaning-related menu |

The notes contain feeder timing (`DON COC`, `DOFF COC`), extractor speed (`G FUMI`),
heat-exchanger fan (`V.SCAMB.`), ignition and temperature/alarm groups. Their
EEPROM offsets remain to be established. Recorded values are evidence for
read-only identification, not recommended tuning values or safe bounds.
All 35 historical service labels are now listed as **unlocated targets** in the
[atlas](https://jordanauge.github.io/palazzetti/memory-eeprom.html), with source credit
and representation hypotheses rather than invented offsets. See the
[evidence workflow](reverse-engineering.md#locating-the-service-settings).
No access-code recipe, reset procedure or output-test instructions are provided.
Changing combustion or safety parameters needs manufacturer-approved service.

## Cross-model references

Public [Lola parameter comparisons](http://palazzetti-lola.blogspot.com/p/parametres-usine-palazzetti.html)
and the [Martina firmware identification article](http://palazzetti-martina.blogspot.com/2021/11/identification-du-firmware.html)
show why menu layout and parameter meaning depend on product, firmware and panel.
They describe other electronics, not a validated Lara menu map. Original
documents and owner notes are retained privately; our observation claims cannot
be independently verified from these public links.

[ESPHome](esphome.md) · [reverse engineering](reverse-engineering.md)
