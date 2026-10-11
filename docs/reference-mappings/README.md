# Reference mapping extractions

These files retain derived facts from other boards, community documents and
Connection Box software. They are **reference notes, not maintained stove maps**:
they are excluded from the atlas, default map discovery and firmware generation.
The only maintained map is [Ecofire Lara](../../maps/palazzetti-ecofire-lara.yaml).

| Extraction | Source and scope |
|---|---|
| [micronova-common.yaml](micronova-common.yaml) | ESPHome Micronova and community layout; source pointers in `sources` |
| [micronova-forum.yaml](micronova-forum.yaml) | [StufaPellet forum](https://stufapellet.forumcommunity.net/?t=53061907); parameter formulas and schedule structures |
| [micronova-p937.yaml](micronova-p937.yaml) | Historical community JavaScript P937 controller notes; original evidence retained privately |
| [micronova-ridiculouslab.yaml](micronova-ridiculouslab.yaml) | [ridiculouslab](https://www.ridiculouslab.com/arguments/iot/stufa/micronova_en.php); RAM table only |
| [micronova-marina.yaml](micronova-marina.yaml) | [eni23/micronova-controller](https://github.com/eni23/micronova-controller); L'Asolana Marina layout |
| [palazzetti-connbox.yaml](palazzetti-connbox.yaml) | Historical Connection Box disassembly notes; model branch not established on Lara |

Each file retains its source descriptions, formulas, uncertainties and any
claim-specific evidence. The YAML format is kept to avoid losing structured
information; it does not make these files supported profiles. Relative `extends`
links describe relationships between reference tables only.

Use representations, ranges and structure layouts as investigation hints.
Do not copy an address into the Lara map without Lara-specific evidence; credit
encoding hints separately from address claims. Conflicts between sources remain
unresolved here, not additional selectable boards in the web UI.

See [references](../references.md) for related projects and
[the map schema](../../maps/README.md) for provenance conventions.
