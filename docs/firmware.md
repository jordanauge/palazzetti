# Firmware identification and the Lola / Martina sources

[README](../README.md) · [boards](boards.md) · [protocol](protocol.md) · [references](references.md)

The [Lola blog](http://palazzetti-lola.blogspot.com/) and
[Martina blog](http://palazzetti-martina.blogspot.com/) document newer Palazzetti
electronics, firmware versions and service parameters. Both were examined from
their live websites on 2026-10-11: 13 Lola posts, its static parameter-comparison
page, eight Martina posts, and the complete available comment feeds.
Copies and linked documents are kept in the private reverse-engineering workspace.

**They do not identify the firmware installed in our Ecofire Lara.** The Lara
speaks Micronova; the Martina Hydro source explicitly identifies its electronics
as **Fumis by Atech**. Its frames, register addresses and RJ12 wiring are not
compatible with the component implemented here.

## 1. Identifying firmware on the newer electronics

The [Martina firmware-identification article](http://palazzetti-martina.blogspot.com/2021/11/identification-du-firmware.html)
describes system-information menu `[5]`:

| Displayed information | Meaning reported by the source | Example |
|---|---|---|
| `cXXX` | Installed firmware version | `c047`: version 47 |
| `dYYY` | Displayed field; meaning not established by this article | Keep the complete value in the device record |
| `ZZZZ` | Firmware type identifier | `0308`: type 308 |

A firmware version is not a firmware type. Different products can show the same
`cXXX` while requiring different firmware files.

The article gives two filename examples:

- `002_000119_47_308.hex`: version 47, type 308.
- `002_000136_48_308.hex`: version 48, type 308.

The meanings of `002` and the second numeric field are not established here.
Type `0039` appears as `_039.hex`, type `0308` as `_308.hex`, and type `1220`
as `_1220.hex` in the examples. These are source-reported naming conventions,
not sufficient evidence that a file is safe to flash.

### Product reference and LabTools

The serial-number example `LT2016081 805801420 19183` contains:

1. `2016`: year.
2. `081`: day-of-year field.
3. `805801420`: nine-digit product reference.
4. A remaining suffix whose meaning is not explained in the article.

LabTools 2.7 associates product references with firmware types through
`firmware/sn.ini`. For example, a section `[004]` lists product references
associated with files ending `_004.hex`. The index may be incomplete.
LabTools 3 is reported to identify firmware from the entered serial number.

For an identification record, collect the exact model/product reference, board
markings, the complete system-information display, LabTools version and the
selected filename. **Do not substitute the Lara's suspected RAM model byte
at `0x0D` for a Fumis firmware type or a product reference.**
Only use vendor-verified firmware matching the hardware; this page is not a
flashing or combustion-tuning procedure.

### Locally supplied service packages

The October 2026 repository additions provide further **metadata**, not an
identification of the installed Lara firmware:

- The private binary repository's `firmwares/sn.ini` contains numeric type sections and nine-digit
  product references, matching the index structure described above.
- `MD5_PA.txt` lists named HEX releases, including `002_000119_45_020.hex`
  and `002_000119_44_025.hex`. A checksum index proves neither that the HEX
  payload is present nor that it matches this stove. It is not a publisher signature.
- The `002520066_PA.tar.gz` package contains a `PXL-APP-PALAZZETTI-1.5.0-A2A1.bin`
  image, resources and INI metadata. This is a different package naming scheme;
  it must not be assigned to the Lara or conflated with the numbered HEX releases.
- The archive named `LabTools_3.1.89.zip` includes an installer internally named
  `LabTools 3.0.msi`, plus a README describing a modified executable. The archive
  filename is not sufficient version/authenticity evidence. These packages were
  inspected read-only; no installer, patch or replacement executable was run.

The supplied distributions are now stored in the private
`palazzetti-binaries` repository,
with one LabTools directory per supplied version. Manuals and parameter documents
are in the reference repository; captures and disassembly belong in the private
reverse-engineering repository. Redistribution rights and provenance need checking
before publishing any original material. Only derived facts belong here.

## 2. What the Lola firmware comparisons teach

The [c032 article](http://palazzetti-lola.blogspot.com/2013/11/palazzetti-lola-nouveau-firmware-c032.html)
compares c019 and c032; the [c033 article](http://palazzetti-lola.blogspot.com/2014/01/lola-nouveau-firmware-c033.html)
reports further changes to P050, P053, P080 and P102.
The [static parameter table](http://palazzetti-lola.blogspot.com/p/parametres-usine-palazzetti.html)
compares Sophie c023 and Lola c019/c023/c032/c033.

The main lesson is that **defaults, permissible ranges and meanings must be
recorded per product and firmware**, not just per brand. The table groups
feeder timings, smoke extraction, room ventilation, hydro options, cleaning,
temperature thresholds and service notifications. It reports `/10`, `x2`
and `x5` conversions for different parameters.

Unknown or absent features are explicitly marked. Some values fall outside
the printed limits, and descriptions differ between articles. Treat these
tables as investigation sources, not calibrated settings or Lara EEPROM maps.
The [two-panel article](http://palazzetti-lola.blogspot.com/2014/02/attention-il-existe-2-versions-du.html)
also warns that menu locations differ between panel versions.

## 3. Martina's Fumis protocol and register evidence

The [serial-line article](http://palazzetti-martina.blogspot.com/2020/01/la-liaison-serie.html)
and its connector diagram describe **38400 baud, 8N2**, approximately 3.3 V
signals and a stove-master multipoint bus. There are separate TX/RX lines and
an inverted combined line. The author's reconstructed schematic labels a
PIC24FJ64GA104; this is not an identification of the Lara's processor.

The [frame article](http://palazzetti-martina.blogspot.com/2020/01/les-trames.html)
describes 11 bytes: ID, eight data bytes, PAD and checksum. PAD is reported as
`0x40` from the stove and `0x00` from a peripheral. The checksum is the
eight-bit sum of the preceding ten bytes. A PC request follows the stove's
ID `0x00` synchronization frame, within an approximately 30 ms window.
Addresses are transmitted low byte first; a read returns eight consecutive bytes.

The [register table](http://palazzetti-martina.blogspot.com/2020/02/la-table-des-registres.html)
provides these **reported, unvalidated** locations:

| Area | Address or range | Source interpretation |
|---|---|---|
| Setup | `0x1C00 + n` for listed Pn entries | Factory parameters; model-dependent meanings |
| Identity | `0x1E04`, `0x1E06` | Two-byte little-endian firmware version and model/type |
| Logs | `0x1F01 + 8*n` | Date/time and error code; 13 entries described |
| Temperatures | `0x200A`, `0x200E`, `0x2010`, `0x2012` | Fumes and T01/T02/T05; the latter scaled by 0.1 |
| State and pressure | `0x201C`, `0x2020` | State byte and pressure difference |
| Fans and power | `0x2026`, `0x2028`, `0x202A` | Room fan, extractor and power level |
| Inputs and outputs | `0x203C`, `0x2040` | Door/safety bits and output bits |
| Clock | `0x204E`-`0x2054` | Seconds through year, including a GMT field |
| Counters | `0x2066` onward | Starts, operating/heating/service time and failures |
| Schedules | `0x8000`-`0x802C` | Six programs and three slots per weekday |

The source repeats `0x8031` for two program temperatures and includes 60 in
minute ranges; neither is adopted as a verified map. Its sample read at
`0x1E04` returns firmware 45 and model 39, not Lara data.

The RJ12 pinout in that article is for this **Fumis** interface: pin 1
inverted combined line, 2 stove TX, 3 stove RX, 4 ground, 5 +5 V, 6 +3.3 V.
Do not apply it to the Lara's connector. The schematic's +5 V pull-ups differ
from the prose's measured levels; actual hardware needs verification.

## 4. Other reusable material and remaining limits

- Lola links scanned installer-training slides, operating-phase diagrams,
  parameter PDF/XLS files and external-thermostat/disassembly videos.
  Four PDF/XLS attachments were recovered into the private archive; videos
  were not downloaded.
- Martina covers USB-TTL adapter selection, Windows COM-port recognition and
  miswiring symptoms. It recommends 3.3 V operation, crossed TX/RX and
  continuity checks, and warns that miswiring may cause E004.
- Its [C# test application article](http://palazzetti-martina.blogspot.com/2020/03/une-petite-apllication-pour-tester.html)
  links [palazzetti-simple-com](https://sourceforge.net/p/palazzetti-simple-com),
  another Fumis frame implementation to inspect.
- Some original Free.fr documents and Postimg images are unavailable.
  The complete coverage and failed-link record are kept with the private archive.

No Lara firmware version, firmware HEX file, validated Lara EEPROM offset,
or new runtime functionality was obtained from these sources.

[README](../README.md) · [boards](boards.md) · [references](references.md)
