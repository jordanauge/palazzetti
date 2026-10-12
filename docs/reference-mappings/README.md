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
| [palazzetti-connbox.yaml](palazzetti-connbox.yaml) | Identified 69055a28 Connection Box build; corrects historical dispatch/parameter claims, applicability not established on Lara |

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
The [2026-10-12 direct review](../references.md#31-direct-source-review-2026-10-12)
compares eni23, philibertc, fabrizio and official ESPHome code, including linked
hardware/panel research, transport weaknesses and conflicting encodings.

## Controller manuals: storage and version-dependent meanings

The owner's Italian **I023 GEN_02 v1.0 (22/03/2007, 38 pages)** and French
**I023 air (46 pages)** manuals are separate reference variants, not a Lara
memory map. Originals and page-level provenance remain in the private Lara
repository. The Italian appendix explicitly names **EDILVAL1.ENC** and
**EDILVAL1.snet**; it is not a Palazzetti Lara parameter/default specification.

| Evidence | Reusable fact | Limit on applicability |
| --- | --- | --- |
| Italian p.27; French section 11.12 | User UT and technical PR settings are in EEPROM; preset parameter banks are separate; selecting a bank replaces PR settings, not UT; executable firmware is in FLASH | Does not give Lara offsets, full EEPROM capacity or RAM mirror locations |
| Italian pp.17-19 | Clock, weekday and schedule settings; schedule UI uses ten-minute steps | UI steps do not establish wire encodings; printed minute range 00..60 is anomalous |
| Italian pp.30-31 | Timing, feed, fan, temperature and supplementary parameter groups; multiple default banks | Defaults are version/model-specific, not safe Lara tuning values |
| Italian p.31 versus French revision history p.4 | Italian auger cycle is six seconds; French air manual records a correction to four seconds | Neither should be imposed on Lara's recorded ON/OFF timings |
| Italian p.34 | State sequence 0 off, 1 ignition fan, 2 pellet load, 3 fire-on, 4 running, 5 stopping, 6 burn-pot clean, 7 cool-fire, 8 alarm | These are that manual's state codes, not Lara RAM F9 encodings |
| Italian p.7 and French connector table | CN5 is console; CN13 is serial through an adapter; CN9 encoder supply is +5 V | Not an identification of Lara's installed PCB or a CN13 voltage/pinout specification |

The Italian manual also assigns Pr28 a pellet-overtemperature role in its
operating description but labels it future use in the parameter table. Preserve
this conflict instead of inventing a universal meaning. Service access,
calibration and reset codes remain private reference evidence; they do not
authorize changes to the physical Lara.

The Lara-specific **KIT SUPERVISORE 004721835 (09/2005)** independently
specifies **1200 8N2 with no flow control** for its non-MiniStandard models.
It distinguishes older non-universal boards from universal boards with firmware
version at least 12. Its CN4 four-pin installation instruction and PC-side
RS232/null-modem cabling refer to the supplied adapter system; they must not
overwrite the I023 CN13 reference or establish bipolar voltage levels on the
bare stove signal.
