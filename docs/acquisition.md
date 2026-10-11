# Read-only acquisition: backups and autonomous polling

[README](../README.md) · [reverse engineering](reverse-engineering.md) · [ESPHome](esphome.md)

This workflow separates **baseline preservation** from **targeted evolution logging**.
Both use checked byte reads through the shared hub; neither enables stove writes.
At 1200 baud a scan is sequential, not a simultaneous snapshot. Firmware, model
and menu observations must be recorded alongside captures to interpret differences.

## 1. Establish repeatable EEPROM and RAM baselines

Keep all evidence and polling-plan files in the private reverse repo:

```sh
export PLZ_HOST=palazzetti.local
export PLZ_SESSIONS=../palazzetti-connection-box-reverse/sessions
export PLZ_SESSION=lara-baseline
plz info
plz backup eeprom:0-0xFF --passes 3 --gap 2 --require-stable \
  -o ../palazzetti-connection-box-reverse/dumps/lara-baseline-eeprom
plz backup ram:0-0xFF --passes 3 --gap 1 \
  -o ../palazzetti-connection-box-reverse/dumps/lara-baseline-ram
```

These commands cover the first **256 bytes** of each space, not certified full
installed memory. The protocol can address `0..0x1FFF` (8192 bytes per space);
the installed controller's capacity, aliasing and implemented ranges remain unknown.
For an explicitly chosen entire protocol-space scan, replace the target with
`eeprom:0-0x1FFF` or `ram:0-0x1FFF`. Do not infer meaningful physical storage
from a successful response alone. Unimplemented ranges may time out or alias.
Backup destinations must be new directories: existing evidence is not overwritten.

`--at 2026-10-12T10:00:00+02:00` waits on the client until that timestamp, then
starts the first sequential read. This is not an ESP alarm or an atomic image.
Keep the client running. Log a mark with the current panel state and firmware;
avoid changing settings during EEPROM passes.

The command temporarily stops the autonomous plan and pauses normal entity polling,
then restores the prior running/paused state while the connection is healthy.
It does not interrupt reads already queued/in flight or stop the stove panel.
A broken connection can prevent restoration; reconnect and inspect `info`/`poll list`
before resuming. Reads still share the wire with the panel.

Each backup contains:

- `pass-01.jsonl`, etc.: per-byte request/completion timestamps, validity, value,
  transmitted/received frame, checksum result, attempts and final-attempt latency.
  Invalid values are `null`, never fabricated zero or `FF`.
- `manifest.json`: selected ranges, device boot identifier, polling configuration,
  pass-file SHA-256 hashes, every byte's values across passes and stability.
  `passes_finished` means all requested attempts completed; `complete` additionally
  requires every byte to be valid in every pass. `consistent` also requires agreement.
- Session events: reads/failures and pass boundaries, reusable by `diff`, `analyze`
  and the private HTML atlas. An interrupted acquisition retains partial files
  and a manifest when the client can run its finalization.

Exit 2 means incomplete byte evidence; exit 3 means `--require-stable` found
variation. Without that option, RAM variation is recorded without a failure exit.
EEPROM disagreement is **not resolved by majority voting**: inspect failed checks,
concurrent changes, aliasing and scales first. A stable capture proves repeatability,
not a safe write/restore command. No restore command is implemented.

## 2. Maintain a targeted plan on the ESP

The plan is empty and stopped at boot, stored only in RAM. It keeps up to **32
non-overlapping ranges**, each with its own requested sweep period. A one-byte
range gives that byte its own frequency; a multi-byte range is read one byte at
a time. You can mix fast state reads with slow EEPROM observation.

```sh
plz poll set ram:0xF9 ram:0x42 --interval-ms 500
plz poll set ram:0x49-0x4B --interval-ms 2000
plz poll set eeprom:0x4C-0x4E --interval-ms 60000
plz poll list
plz poll start
plz poll record -i 0.5 -d 600
```

Scheduling is round-robin between due ranges. At most one plan read is queued/in
flight, avoiding a full-range request backlog that blocks a short fast range.
`interval_ms` is a requested **start-to-start sweep period**, 100..86400000 ms.
Overruns do not queue catch-up sweeps; larger ranges cannot meet a period shorter
than their actual bus acquisition time. Normal entity polling and interactive
commands share the queue. `plz send pause` suppresses both entity and plan scheduling
while that connection remains open; `poll stop` controls only the plan.
For focused high-rate work, use a firmware profile without unrelated entity polls.

The physical ceiling with the default 30 ms inter-frame gap is roughly **15
successful byte transactions/s**, before contention, retries or queue waits.
An interval of 100 ms is accepted as a request, not a throughput guarantee.
Full 8192-byte sweeps take minutes, multiplied by repeated passes; failed reads
and retries can make them substantially slower.

Live edits (including from another CLI terminal):

```sh
plz poll set ram:0xF9 --interval-ms 1000  # update exact matching range
plz poll remove ram:0x49-0x4B            # exact range identity
plz poll stop
plz poll save ../palazzetti-connection-box-reverse/sessions/state-plan.json
plz poll clear                          # stop and remove all rules
plz poll load ../palazzetti-connection-box-reverse/sessions/state-plan.json --start
```

Save refuses to overwrite a file. Load validates the complete file before clearing
the old plan; a transport error during upload is reported and may leave a **stopped,
partial plan**. Inspect/reload rather than assuming success. Removing/clearing/stopping
does not retract a read already accepted by the hub; its completion may still appear.
The CLI recorder releases the single lab connection between short batches so another
CLI can edit the plan. There is no exclusive campaign ownership: coordinate edits.

## 3. Scan unknown or uncertain bytes

`--unknown --profile` excludes only bytes with **observed or confirmed** reading
semantics in that profile. Reported, hypothesis, unknown and refuted entries remain
eligible; nested leaf members are considered and unassigned struct bytes stay unknown.
This is a selection convenience, not proof that excluded interpretations are correct.

```sh
plz poll set ram:0-0x7F --interval-ms 30000 \
  --unknown --profile palazzetti-ecofire-lara
plz poll list
```

The CLI coalesces contiguous selected bytes into ranges. If fragmentation exceeds
32 rules or overlaps the existing plan, it rejects the update before changing it.
Choose narrower areas or clear/rebuild a plan; it never silently includes skipped bytes.
`plz dump` and `watch` remain available for ordinary range scans.

## 4. Retained results and live API

The ESP keeps the latest **32 plan results**, including failed reads. It is a small
drain buffer, not a permanent logger. `poll record` drains at a configurable client
interval, logs each read/failure with sequence, boot ID, plan revision, device uptime
and host reception time, and leaves the plan running after Ctrl-C.

When results are overwritten, it emits a warning and a `poll_gap` session event with
the lost count. Reboots produce `poll_boot` events and reset the cursor; the plan
must be reloaded explicitly. Normal entities/interactive reads are not in this
plan-result buffer (`monitor` is still the separate successful-traffic stream).
No buffered result is represented as new just because it was received later.
Session `t` for drained samples is estimated from host receipt time minus device
uptime age, not an NTP-synchronized ESP timestamp; raw uptime/reception fields remain.

TCP lab commands (unauthenticated, trusted LAN only):

| Line | Result |
|---|---|
| `poll list` | `p mem=... start=... end=... interval_ms=...` lines; final running/revision/boot/sequence/capacity/history |
| `poll set ram 0xF9 0xF9 500` | Add/update one exact range; reject overlap, invalid bounds/period or full plan |
| `poll remove ram 0xF9 0xF9` | Remove exact range or report error |
| `poll start`, `poll stop`, `poll clear` | Control scheduling; clear also stops |
| `poll events 12` | Checked `s` result lines newer than sequence 12; final boot/latest/oldest/lost/uptime fields |

The web package also exposes encrypted ESPHome native-API actions:
`set_poll_range(memory,start,end,interval_ms)`, `remove_poll_range(memory,start,end)`
and `control_polling(enabled)`, with memory 0 RAM / 1 EEPROM.
Errors are logged and published in **Last API memory read**. Use the TCP/CLI list
and result APIs for structured inspection and capture; native actions do not stream
the ring into Home Assistant.

## 5. Connect evidence, not guesses

Keep a private current-stove dossier for menus/codes, dated actual readings and
separately evidenced defaults. Capture firmware/type/panel identification first.
Correlate marked physical-panel observations with repeated reads, public parameter
references and static firmware/PLZBridge findings once available. Preserve originals
in the binary/reference repos and working analysis in reverse; promote only verified
derived facts to public maps/docs. None of these read APIs relaxes the write policy.

[Memory maps](memory-map.md) · [Reverse engineering](reverse-engineering.md)
