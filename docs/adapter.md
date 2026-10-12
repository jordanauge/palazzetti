# Diode, resistor and NPN: the one-wire serial adapter

[README](../README.md) · [hardware](hardware.md) · [protocol](protocol.md) · [firmware and OTA](esphome.md)

This page documents the owner's retained **one diode + one 10 kΩ resistor +
one NPN transistor** drawing. It separates that evidence from the conflicting
MOSFET reference previously used in this documentation, and explains the
ESP8266 UART assignments. This is a serial interface to the stove/display bus,
not a Dallas/Maxim 1-Wire interface and not standard RS232.

**Important:** the drawing omits supply/ground and receive biasing. It establishes
three signal nets and a resistor value, but is not a complete, electrically
validated construction schematic. Physical HAT contact positions, green-wire
identity, transistor part/lead order and stove connector pins remain unresolved.
Do not infer how to insert the ESP from this diagram.

## 1. Configuration A: the retained diode/resistor/NPN drawing

Figure 1 is an independently redrawn net-level interpretation of the owner's
saved schematic. It is not a photograph of the HAT and does not add missing
power rails or an assumed receive pull-up.

![Retained NPN adapter topology](figures/adapter.2.npn.svg)

**Figure 1:** D1 connects the shared bus to the transmit node, with its cathode
bar at TX. R1 connects TX to Q1's base; Q1's arrow-side emitter connects to the
bus and its collector connects to RX. The original drawing labels Q1 as NPN.
These are transistor terminal names, not physical package pin numbers.

| Item | Evidence-backed value / connection | Not established |
|---|---|---|
| D1 | Diode; anode on shared `Tx/Rx`, cathode/bar on `Tx` | Part number, silicon versus Schottky, ratings |
| R1 | **10 kΩ**, between `Tx` and Q1 base | As-built measured resistance, tolerance, power rating |
| Q1 | **NPN**, emitter to bus, collector to `Rx`, base through R1 to `Tx` | Part number, package, B/C/E lead order, ratings |
| `Tx` | ESP sends to adapter; **D8 / GPIO15** | Physical HAT contact |
| `Rx` | Adapter sends to ESP; **D7 / GPIO13** | Physical HAT contact and receive bias/protection |
| `Tx/Rx` | Stove's bidirectional serial bus | Stove/DB9 connector contact |
| Supply and ground | Not shown in the saved circuit | Power source, regulator paths, signal ground, isolation |

Do not replace Q1 with a BSS138: that is a MOSFET, not an NPN transistor.
Likewise, neither a BC547 nor a 2N3904 is identified by the evidence. Both are
examples of small-signal NPN families, but cannot be specified as the installed
part; their package pinouts can differ. BAT85/1N5817 are parts proposed for the
separate reference circuit, **not identified parts of this HAT**.

### Intended signal behavior and missing conditions

When TX is low and the bus is high, D1 can conduct from bus to TX, pulling the
bus toward the TX low level plus the diode's forward drop. That drop depends
on the actual diode and current; a part number cannot be chosen from a symbol.
When the bus is low and TX is high, D1 is reverse-biased.

With Q1 wired as drawn, a low bus emitter and high TX through R1 can turn Q1 on.
Its collector can then pull RX low. If an appropriate **3.3 V receive pull-up**
exists elsewhere, this would reproduce bus-low as RX-low. At bus idle high,
Q1 should be off and that pull-up would establish RX-high. This is the intended
non-inverting interpretation; **the required bias, off-state junction stress,
GPIO back-power paths and actual voltage levels have not been verified**.

R1 limits **base current**, not bus voltage. Its 10 kΩ value does not make RX
5 V tolerant and does not prove TX is protected from the stove's bus voltage.
This asymmetric transistor arrangement is not automatically equivalent to a
bidirectional level shifter.

The drawing alone cannot establish:

- whether RX has a pull-up and which rail it uses;
- whether the stove/panel already supplies the bus pull-up;
- safe behavior with the ESP unpowered or during reset;
- whether the bus can pull GPIO15 high enough to prevent boot;
- whether connector ground is safely compatible with USB/computer ground.

The intended receive path can echo our transmitted bits. The firmware uses
`echo: auto` to distinguish echo from a reply; echo handling is separate from
UART pin mapping and electrical inversion.

[k3a's circuit investigation](https://k3a.me/ir-controller-for-pellet-stove-with-micronova-controller-stufe-e-pellet-aria-ir-telecomando/)
describes a PNP/diode experiment followed by a different NPN circuit with TX
protection, and reports echo dependence on voltage thresholds. These are useful
comparison circuits, not identification of the owner's HAT or proof that its
GPIOs are protected. The [source review](references.md#31-direct-source-review-2026-10-12)
also distinguishes optocoupler RX gating from this continuously connected path.

## 2. Configuration B: the conflicting MOSFET reference

The previous page centered the following **different** reference topology.
It remains here for comparison, not as evidence of the owner's board.

![Separate MOSFET reference circuit](figures/adapter.1.schematic.svg)

**Figure 2:** A BSS138 joins separate 5 V and 3.3 V pulled-up lines. ESP RX reads
the low-voltage line directly; TX pulls it low through a Schottky diode.
Unlike Figure 1, this circuit has two resistors and explicitly drawn supply rails.

| Item | Configuration A: retained drawing | Configuration B: reference proposal |
|---|---|---|
| Transistor | NPN, part unknown | BSS138 N-channel MOSFET |
| Transistor terminals | Base through resistor to TX; emitter to bus; collector to RX | Gate to 3.3 V; source to low-voltage line; drain to bus |
| Resistors | One **10 kΩ** base resistor | Two **10 kΩ** pull-ups, one per rail |
| Diode | Part unknown; cathode to TX | BAT85 or 1N5817 Schottky proposal; cathode to TX |
| Receive path | Transistor collector; external bias missing from drawing | Directly reads the pulled-up 3.3 V line |
| Evidence | Owner's retained drawing; as-built match unverified | Documentation reference; not the owner's identified HAT |
| Firmware expectation | Intended non-inverting, needs electrical confirmation | Intended non-inverting, needs electrical confirmation |

**These configurations cannot be combined by exchanging transistor names.**
An NPN common-emitter transmitter (emitter to ground, collector to bus) is yet
another circuit: TX-high turns the transistor on and pulls the bus low, which
inverts TX. That is **not** Q1's role in Figure 1. Do not enable UART inversion
because a drawing merely contains an NPN.

## 3. UART0 before and after `Serial.swap()`

The original firmware configures the stove UART as:

```cpp
Serial.begin(1200, SERIAL_8N2);
Serial.swap();  // RX = D7, TX = D8
```

`Serial` is **UART0**, the full transmit/receive hardware UART. Swapping changes
its pin routing, not its baud rate, data bits, parity, stop bits or polarity.

| Function | Before swap: UART0 default | After swap: UART0 alternate |
|---|---|---|
| TX | **GPIO1**, devkit `TX`; connected to USB serial chip's RX | **GPIO15 / D8** → adapter `Tx` |
| RX | **GPIO3**, devkit `RX`; connected to USB serial chip's TX | **GPIO13 / D7** ← adapter `Rx` |
| Protocol | 1200 baud, 8 data bits, no parity, 2 stop bits after `begin` | Same **1200 8N2** |
| Debug output | Must not mix logs into a stove UART | Still must not mix logs into UART0 |
| USB upload | Boot ROM uses default GPIO1/GPIO3 | Reset/upload still uses default GPIO1/GPIO3 |

Swapping lets the stove use a dedicated hardware UART on D7/D8 without sharing
the USB chip's runtime TX/RX wires. It also preserves the original HAT's intended
signal assignment. **It does not create a second full UART on GPIO1/GPIO3.**
After reset the boot ROM operates independently; the swap is applied again by
the firmware at startup. This is why USB flashing still works.

ESPHome selects that alternate routing from the explicit pins; no custom
`Serial.swap()` lambda should be added:

```yaml
uart:
  id: stove_uart
  tx_pin: GPIO15  # D8, ESP sends
  rx_pin: GPIO13  # D7, ESP receives
  baud_rate: 1200
  data_bits: 8
  parity: NONE
  stop_bits: 2
```

GPIO15 is a boot strap and **must be low during reset**. The devkit pull-down
must remain in place; the HAT must not defeat it. Once booted, the UART uses
its normal idle-high TX level. Debug or OTA configuration does not remove this
electrical boot constraint.

## 4. Debug needs TX only: use UART1, not the stove UART

The original code separately uses `Serial1.begin(115200)` and
`Serial1.println(...)`. ESP8266 **UART1 has a usable TX output only**, on
**GPIO2 / D4**. That is sufficient to send logs to a computer; no debug RX is needed.
The current ESPHome configuration preserves this separation:

```yaml
logger:
  hardware_uart: UART1
  baud_rate: 115200
```

For a hardware debug connection, use a **3.3 V TTL USB-UART receiver**, with
its RX connected to D4 and a suitable common ground, at **115200 8N1**.
Leave its TX and power pins disconnected. Do not use a ±12 V RS232 adapter.
GPIO2 must remain high during boot; do not attach a receiver/load that pulls it low.
Only attach grounded computer equipment once the stove-side isolation/ground
arrangement is verified.

Alternatively, `make logs DEVICE=palazzetti.local` receives ESPHome logs over
Wi-Fi. Native API transport encryption is automatic; it is not a requirement
to encrypt saved log files. The devkit's existing USB chip is on GPIO1/GPIO3,
so it does **not** receive UART1/D4 runtime logs. ROM boot messages can still
appear on GPIO1; they are not the application log stream.

Never use `Serial.print()` for debugging on the stove UART: even an ASCII
message becomes unintended traffic on the shared bus.

## 5. Establish the as-built circuit before connecting

Keep the stove and USB disconnected while tracing the HAT. Record the actual
diode marking/polarity, Q1 marking and datasheet lead order, resistor value,
every socket contact, supply/ground paths and any hidden RX pull-up.
Green is a wire color, not a signal definition. D7/D8 net identities do not
establish which way around the ESP fits the socket.

Have the incomplete circuit checked on an isolated bench before stove use.
Verify ESP-side levels, reset/unpowered behavior and bus-low behavior against
the actual component specifications. Live measurements inside the stove
require a qualified technician and suitable isolated equipment; do not use
a grounded scope/USB cable to guess connector pins.

Firmware is already available over **`palazzetti.local`**; OTA and the device
name are documented in [ESPHome §2.1](esphome.md#21-ota-and-device-name).
An OTA upload updates ESP flash, **not the stove controller firmware**.

[Hardware](hardware.md) · [Protocol](protocol.md) · [ESPHome and OTA](esphome.md)
