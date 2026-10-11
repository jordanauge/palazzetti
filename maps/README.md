# Memory maps

The only maintained map is **Palazzetti Ecofire Lara**, the stove we can test.
[palazzetti-ecofire-lara.yaml](palazzetti-ecofire-lara.yaml) is the
single source of truth for its addressed fields and unlocated investigation targets. [docs/memory-map.md](../docs/memory-map.md),
[RAM hex map](../docs/memory-ram.html), [EEPROM hex map](../docs/memory-eeprom.html) and the ESPHome entity packages in
[example/](../example) are generated from them with `make gen`.

Lara uses the **Micronova** protocol (13-bit addressing; most documented fields are
in the first 256 bytes). Other boards and software are
[reference extractions](../docs/reference-mappings/README.md) only. They are not
discovered as maintained profiles, selectable in the atlas, or accepted by firmware
and atlas generators. Their encodings and structures may inform Lara investigations;
their addresses do not establish Lara applicability. Fumis is out of scope;
see [boards.md](../docs/boards.md).

## Profile keys

| Key | Meaning |
|---|---|
| `profile` | name (file stem) |
| `title` | human-readable name |
| `extends` | optional parent profile; fields are merged by `id`, child keys win |
| `sources` | `key: description` of every evidence source used by the fields |
| `fields` | list of fields (below) |
| `unlocated` | inventory of parameters with no assigned address: `id`, `name`, `memory_hint` (`ram`, `eeprom`, `unknown`), category, notes, optional representation candidates and evidence |

## Field keys

| Key | Default | Meaning |
|---|---|---|
| `id` | required | stable identifier for the parameter |
| `mem` | `ram` | `ram` or `eeprom` |
| `addr` | required | address (0x0000–0x1FFF) |
| `count` | 1 | number of consecutive bytes for a block (documented only, no entity generated) |
| `name` | from `id` | entity / documentation name (no `/`) |
| `category` | `Unclassified` | explicit atlas grouping: state, temperatures, combustion, user settings, clock/scheduling, service parameters or identification/constants |
| `unit` | | unit of measurement |
| `scale`, `offset` | 1, 0 | displayed = raw × scale + offset |
| `encoding` | `uint8` | `uint8`, `int8`, `bcd`, `uint16_be`, `uint16_le`, `int16_be`, `int16_le` |
| `values` | | `raw: label` enumeration (quote `"off"`/`"on"`, YAML reads them as booleans) |
| `access` | `r` | `rw` when writing is meaningful; does not itself authorize writes |
| `write_status` | `unverified` | `confirmed` only with separate evidence of the safe write operation |
| `write_sources` | | evidence keys supporting write commands, distinct from reading semantics |
| `raw_min`, `raw_max` | | inclusive safe raw byte bounds required for confirmed writes |
| `status` | `unknown` | `confirmed`, `observed`, `reported`, `hypothesis`, `unknown`, `refuted` |
| `sources` | | keys of `sources` supporting the entry |
| `evidence` | | list of claim-specific records: `source`, `origin` (`own`/`external`), `method`, `supports`, `claim` |
| `notes` | | free text: observations, ranges, caveats |
| `members` | | nested fields inside a block, used by the HTML viewer; each has `id`, `byte_offset` relative to its parent, optional `count`, `members`, and the usual descriptive keys |

Members inherit their parent's memory, evidence status, category and source keys unless overridden.
`byte_offset` is the position inside a structure; `offset` remains the arithmetic
offset in the value conversion. Unassigned bytes stay unknown. Structure boundaries and
member meanings have the same evidence requirements as standalone fields. Nested members
are generated as read-only leaf ESPHome entities at a slow cadence when their
status is selected. Hypotheses remain visibly marked.

### Claim-specific provenance

`supports` lists one or more of `address`, `meaning`, `encoding`, `layout`, `range`,
`default`, `applicability`. `method` is `source_table`, `source_code`,
`source_description`, `disassembly`, `variation`, `panel_match`, `panel_change`,
`static_value`, `default_match`, `range_match` or `adjacency`. The claim explains
exactly what was observed/reported and what remains uncertain.
For example, a panel change is a physical-menu action, **not** our serial write.
Source credit for an encoding never implies that its address applies to Lara.
Defaults and ranges require identified firmware/model evidence; historical actual
readings and observed extrema are neither defaults nor safe limits.

Members retain parent-region provenance in atlas details, explicitly labelled as
region evidence rather than proof of every member meaning. Profile overrides of
addresses, conversions or sources discard inherited evidence unless explicitly
restated. Legacy source lists without structured claims are visibly unclassified.
No evidence record grants write permission.

`unlocated` entries appear in the atlas list and details, but **never** highlight a
guessed byte, generate an entity or contribute to mapped-byte coverage. The 35
historical service labels are listed separately from located user settings.
`memory_hint: eeprom` is an investigation target, not established storage.
Encoding candidates are possibilities to test, not configured conversions.
Current/default readings and full backups remain private.

Write generation requires observed/confirmed read status, `access: rw`,
`write_status: confirmed`, nonempty `write_sources`, safe byte bounds and `uint8` encoding.
Enumeration rules authorize exact listed values, not all intermediate bytes.
An observed setpoint alone does not establish a safe command. Lara has **no confirmed
write rules**; its settings are read-only in generated firmware. The manual ESPHome
`write_allowlist` schema is an expert configuration surface, not evidence verification:
never insert guessed addresses. Runtime RAM and EEPROM permission gates still apply.

## Interactive maps and historical captures

Open the two HTML pages directly in a browser; they need no server, network or external assets.
The atlas displays Lara only; there is no board selector. The three panels are a searchable field
catalogue (A–Z or categories), the byte grid, and click-only details. Hover/focus highlights a
region across the list and grid without replacing details. Click or Enter selects it:
white outlines show selection, gold insets show hover, including when they overlap.
Escape clears selection. Arrow keys navigate the grid. Regions, nested members, overlapping
annotations, enums, scales, evidence statuses and sources are preserved.

Without a capture, cell text shows the **low byte of the address** (00–FF), not invented
memory contents; row labels give the full address. Category backgrounds show layout,
bottom-border colors show evidence status, and unmapped cells are muted.
Selecting a capture switches to hex values; a dot means no valid sample. The cell-content
selector can return to address layout while retaining the selected capture.

The Lara map includes the secondary P/V RAM copies at `47`/`46`, the model-code
candidate at `0D`, historical constant-block members and additional addresses of interest.
Unknown meanings remain unknown; historical constants are not factory defaults.
The forum reference extraction retains PG00–PG15, PF00–PF20, P100–P102 and schedule
members from its source table, outside the atlas. Those **reported** addresses and
formulas are not Lara settings. Unassigned slots are not given invented member meanings.

`make gen` regenerates both public pages from YAML only, without private captures.
Historical logs are in the private reverse-engineering repository. For a local private atlas:

```bash
plz gen-html palazzetti-ecofire-lara -o ../palazzetti-connection-box-reverse/atlas \
  --capture ../palazzetti-connection-box-reverse/sessions/2020-02-10-legacy-ram.jsonl.xz \
  --legacy-dir ../palazzetti-connection-box-reverse/legacy/2020-backup/out2
```

`HTML_CAPTURES` and `HTML_LEGACY_DIRS` optionally pass sources to `make gen`; do not commit
capture-bearing output to the public repository.
A byte's displayed value is its last valid read, **not** a coherent
snapshot. Details include exact sample/change counts and distributions, rejection counts,
timestamps and a downsampled evolution plot. No EEPROM capture was supplied: its page shows
address-layout annotations, not actual values.

To use your own captures:

```bash
plz gen-html palazzetti-ecofire-lara -o docs --capture sessions/my-session.jsonl --evidence-profile palazzetti-ecofire-lara
```

`--capture` and `--legacy-dir` are repeatable; the latter requires three columns in each
`addr-XX` file: Unix timestamp, `true`/`false`, hex value. The historical backup's `out1` contains
only values (no timestamps or success flags); it is deliberately not presented as an evolution
capture. The `out2` firmware substitutes `FF` on rejection, so failed values cannot be recovered.
Its checksum comparison misses wrapping, and it accepts zero checksums: a `true` callback is
historical firmware acceptance, not independently revalidated serial data. The February 8
capture spans 6,320 seconds, with 4,714 accepted and 1,607 rejected replies across 256 addresses
(200 with accepted data). In particular `F9` has **no valid samples**: these logs cannot independently
establish its state transitions. Temperature-like trends at `42`, `49`, `4A`, `4B` complement
the later capture; correlation alone does not identify probes.

Generator regression tests are in `tests/test_memory_html.py`. The dependency-free browser
test exercises the generated files with Chrome/Chromium:

```bash
node tests/test_memory_html.cjs "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

On other platforms pass the installed Chrome/Chromium executable path. This runs a separate
headless test instance and does not start a web server or alter an existing browser profile.

Status meanings are in [docs/reverse-engineering.md](../docs/reverse-engineering.md#8-promoting-knowledge).
