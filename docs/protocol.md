# Serial protocol

[← README](../README.md) · [boards](boards.md) · [hardware](hardware.md) · [adapter](adapter.md) · [memory map](memory-map.md) · [reverse engineering](reverse-engineering.md) · [references](references.md)

Older Palazzetti stoves, including the Ecofire Lara, have a controller board that speaks the **Micronova**
protocol, like many Italian pellet stove brands (Extraflame, Laminox, La Nordica, Piazzetta, ...). Newer
Palazzetti stoves use a **Fumis** board with a different protocol that is not covered here; see
[boards.md](boards.md) for the differences and how to tell which one a stove has. The Micronova board exposes
a serial bus that the display panel, the Palazzetti Connection Box and service tools use to read and write the
controller's **RAM** (live state) and **EEPROM** (persistent settings). This page describes that bus as
implemented in [micronova.h](../components/palazzetti/micronova.h) and [codec.py](../tools/plz/codec.py).

## 1. Physical layer

| Property | Value |
|---|---|
| Baud rate | 1200 |
| Framing | 8 data bits, no parity, **2 stop bits** (8N2) |
| Medium | **single wire**, half-duplex, open-collector style, 5 V logic (TO VERIFY on the Lara connector) |
| Roles | one master (us, the display panel, the Connection Box) polls; the controller answers |

Because TX and RX share one wire, everything the master sends is also seen on its own RX line ("echo").
The [adapter](adapter.md) makes this visible to the ESP8266, and the component discards the echo
(`echo: auto` detects whether an echo is present on the first frame).

A frame of 2 bytes at 1200 8N2 takes ~18 ms; a full transaction (request + reply) takes ~40–60 ms.
Polling 256 RAM addresses therefore takes ~15 s.

## 2. Frames

The first byte (header) encodes the operation, the memory, and the 5 high address bits; the second byte is the
low address byte. Addresses are thus 13 bits (0x0000–0x1FFF), although the known maps only use 0x00–0xFF.

| Operation | Header | Request | Reply |
|---|---|---|---|
| Read RAM | `0x00 \| addr>>8` | `[hdr, addr]` | `[csum, value]` |
| Read EEPROM | `0x20 \| addr>>8` | `[hdr, addr]` | `[csum, value]` |
| Write RAM | `0x80 \| addr>>8` | `[hdr, addr, value, csum]` | `[addr or csum, value]` |
| Write EEPROM | `0xA0 \| addr>>8` | `[hdr, addr, value, csum]` | `[addr or csum, value]` |

Checksum: `csum = (hdr + addr + value) & 0xFF`.

Example, reading the Lara power state at RAM 0xF9 while the stove is off (value 0x1A):

```
→ 00 F9          read RAM 0xF9
← 13 1A          0x13 = (0x00 + 0xF9 + 0x1A) & 0xFF, value 0x1A
```

Example, the generic Micronova on/off frames (RAM 0x21; **not valid on the Ecofire Lara**, see §4):

```
→ 80 21 01 A2    write RAM 0x21 = 1 (on)
→ 80 21 06 A7    write RAM 0x21 = 6 (off)
```

### 2.1 Checksum caveats

- The checksum **must be masked to 8 bits**. The 2020 Arduino code (`legacy/arduino`, `RCSUM`) did not, so it
  rejected every valid reply where `addr + value ≥ 256`. This explains nearly all "failed" reads in the 2020 dumps.
- For RAM reads the header is 0 so `hdr + addr + value` and `addr + value` are indistinguishable. For EEPROM
  reads some sources compute the checksum without the header; the decoder accepts both and reports
  `ok-noheader` so the variant can be identified per stove (TO VERIFY on the Lara).

### 2.2 Write reply variants

Write replies are reported as `[addr, value]` by some sources and `[csum, value]` by others. The component
accepts either, provided the value byte equals the written value (`check_write_reply`). The Lara variant is
TO VERIFY: the lab tool logs the raw reply of every write (`plz write`) so it can be settled from sessions.

## 3. Timing and bus sharing

| Parameter | Default | Component option |
|---|---|---|
| Reply timeout | 300 ms | `reply_timeout` |
| Gap between frames | 30 ms | `frame_gap` |
| Retries on timeout/bad checksum | 2 | `max_retries` |

The display panel is also a master on the same wire. Collisions show up as timeouts or bad checksums and are
retried; `plz info` (or `info` on the lab server) exposes the counters. Keep polling intervals reasonable
(≥ 10 s per entity) so the panel stays responsive.

## 4. Variations across stoves

The frame format is common to all Micronova boards seen so far; **the memory layout is not**. The same parameter
can live at a different address, have a different scale, or not exist at all. [memory-map.md](memory-map.md)
documents Lara only; other-board layouts stay in [reference notes](reference-mappings/README.md). Known differences:

| Aspect | Generic Micronova (ESPHome `micronova`, StufaPellet) | Palazzetti Ecofire Lara |
|---|---|---|
| Status register | RAM 0x21 (0 off … 7 final cleaning) | RAM 0xF9 (0x1A off, 0x2B ignition, 0x4B working, 0x1D final cleaning); RAM 0x21 is constant 5 |
| On/off | write RAM 0x21 = 1 / 6 | **unknown**; do not write RAM 0x21 (TO VERIFY with a lab session) |
| Room temperature | RAM 0x01 | RAM 0x49 (hypothesis); RAM 0x01 refuted |
| Fumes temperature | RAM 0x5A | RAM 0x42 / 0x4B; RAM 0x5A is a flag byte (63 off, 255 running) |
| Power level | RAM 0x34 | RAM 0x3F (observed); RAM 0x34 refuted |
| Settings | Model-specific PG/PF/user/chrono layouts | observed user bytes 0x4C/0x4D/0x4E; service EEPROM offsets unknown; chrono triplets tentative |

Some boards (e.g. Micronova P937 variants) use a different water temperature address or BCD-encoded clock
registers; the component's `encoding:` option (`uint8`, `int8`, `bcd`, `uint16_be/le`, `int16_be/le`) covers these.

The inspected Palazzetti Connection Box build selects a Micronova branch using
**RAM 0x6E**, then uses several address sets (e.g. target temperature at RAM
0x36 or 0xA0, power at 0x37/0x64 or 0x97/0x34). Its RAM 0x0D is a scaled
`FEEDER` reading, not model identification. This corrects the earlier 2020 note.
See [connection-box.md](connection-box.md) and the
[reference extraction](reference-mappings/palazzetti-connbox.yaml). Lara's constant
232 at RAM 0x0D remains unidentified; none of these branch layouts is verified
for Lara. The bridge's 16-bit reads are big-endian and consist of two non-atomic
byte reads; this is an encoding hypothesis when searching Lara storage, not proof
that Lara multi-byte parameters use the same order.

Newer Palazzetti stoves (and Jotul, Godin, TurboFonte…) use a **Fumis** board instead: 38400 baud, 11-byte
frames and 16-bit addresses (`0x2000`–`0x2100`). It is a different protocol, out of scope for this component;
see [boards.md](boards.md).

## 5. Safety

- **Never write an address whose meaning is not confirmed.** A wrong EEPROM write persists across power cycles
  and can change combustion parameters (auger time, fan speeds) or disable safety thresholds.
- Note the original value before writing (`plz write` does it and logs the reply).
- The lab server refuses writes and raw frames unless `allow_write: true` is set in the firmware.

## 6. References

- ESPHome `micronova` component: <https://esphome.io/components/micronova.html>
- StufaPellet forum thread and PlatformIO project (copy in the private repo `thirdparty/`):
  <https://stufapellet.forumcommunity.net/?t=53061907>
- Philibert Cheminot, *micronova_controller*: <https://github.com/philibertc/micronova_controller>
- ridiculouslab, *Micronova protocol analysis*: <https://www.ridiculouslab.com/arguments/iot/stufa/micronova_en.php>

Other implementations, adapters and manuals are listed in [references.md](references.md).

The two directly reviewed reference tables are retained outside the maintained map:
[ridiculouslab](reference-mappings/micronova-ridiculouslab.yaml) and
[eni23's L'Asolana Marina](reference-mappings/micronova-marina.yaml). They disagree on some
representations and command labels. Ridiculouslab explicitly did not investigate EEPROM;
its Modbus register numbers are translated addresses, not stove EEPROM offsets.
These references supply **testable representation hypotheses**, not Lara address proof.
The [provenance rules](reverse-engineering.md#8-promoting-knowledge) distinguish
mapping, encoding, layout and interpretation claims.

[← README](../README.md) · [memory map →](memory-map.md)
