"""Memory map profiles (maps/*.yaml): loading, documentation and ESPHome generation."""

from collections import Counter
import json
import math
from pathlib import Path

import yaml

from .codec import EEPROM, RAM

MAPS_DIR = Path(__file__).resolve().parents[2] / "maps"
STATUSES = ("confirmed", "observed", "reported", "hypothesis", "unknown", "refuted")
STATUS_HELP = {
    "confirmed": "verified by a write/read round trip or by the manufacturer",
    "observed": "seen behaving as described on this stove (dump or live session)",
    "reported": "taken from a third-party source, not verified on this stove",
    "hypothesis": "plausible interpretation of observations, needs a targeted test",
    "unknown": "address of interest, meaning not understood",
    "refuted": "generic meaning checked and wrong for this stove",
}
EVIDENCE_METHODS = (
    "source_table", "source_code", "source_description", "disassembly",
    "variation", "panel_match", "panel_change", "static_value",
    "default_match", "range_match", "adjacency",
)
EVIDENCE_ASPECTS = ("address", "meaning", "encoding", "layout", "range", "default", "applicability")


def _validate_evidence(field: dict, sources: dict) -> None:
    records = field.get("evidence", [])
    if not isinstance(records, list):
        raise ValueError(f"Evidence must be a list for {field['id']}")
    for record in records:
        if (not isinstance(record, dict) or record.get("source") not in sources or record.get("origin") not in ("own", "external")
                or record.get("method") not in EVIDENCE_METHODS
                or not record.get("supports") or not isinstance(record["supports"], list)
                or any(aspect not in EVIDENCE_ASPECTS for aspect in record["supports"])
                or not isinstance(record.get("claim"), str) or not record["claim"].strip()):
            raise ValueError(f"Invalid evidence for {field['id']}: {record}")
    for child in field.get("members", []):
        _validate_evidence(child, sources)


def _path(name: str) -> Path:
    p = Path(name)
    return p if p.suffix else MAPS_DIR / f"{name}.yaml"


def _norm(f: dict) -> dict:
    f = dict(f)
    f["mem"] = f.get("mem", RAM)
    assert f["mem"] in (RAM, EEPROM), f
    assert f.get("status", "unknown") in STATUSES, f
    f.setdefault("status", "unknown")
    f.setdefault("name", f["id"].replace("_", " ").capitalize())
    f["addr"] = int(f["addr"])
    f.setdefault("write_status", "unverified")
    if f["write_status"] not in ("unverified", "confirmed"):
        raise ValueError(f"Invalid write_status for {f['id']}")
    if f["write_status"] == "confirmed":
        if (f.get("access") != "rw" or f["status"] not in ("observed", "confirmed")
                or not f.get("write_sources") or not all(key in f for key in ("raw_min", "raw_max"))):
            raise ValueError(f"Confirmed write requires rw, reliable read semantics, write_sources and raw bounds: {f['id']}")
        if (any(type(f[key]) is not int for key in ("raw_min", "raw_max"))
                or not 0 <= f["raw_min"] <= f["raw_max"] <= 255):
            raise ValueError(f"Invalid raw write bounds for {f['id']}")
        if f.get("count", 1) != 1 or f.get("encoding", "uint8") != "uint8":
            raise ValueError(f"Only uint8 confirmed writes are supported: {f['id']}")
        if f.get("scale", 1) <= 0:
            raise ValueError(f"Confirmed writes require a positive scale: {f['id']}")
        if f.get("values") and not any(f["raw_min"] <= value <= f["raw_max"] for value in f["values"]):
            raise ValueError(f"Confirmed write enum has no values inside safe bounds: {f['id']}")
    return f


def load(name: str) -> dict:
    """Load a profile, resolving `extends` (fields merged by id, child keys win)."""
    raw = yaml.safe_load(_path(name).read_text())
    fields: dict[str, dict] = {}
    sources: dict[str, str] = {}
    if parent := raw.get("extends"):
        base = load(parent)
        fields = {f["id"]: f for f in base["fields"]}
        sources = dict(base["sources"])
    for f in raw.get("fields", []):
        inherited = dict(fields.get(f["id"], {}))
        if "evidence" not in f and any(key in f and f[key] != inherited.get(key)
                                      for key in ("addr", "mem", "scale", "offset", "encoding", "sources")):
            inherited.pop("evidence", None)
        fields[f["id"]] = _norm({**inherited, **f})
    sources.update(raw.get("sources", {}))
    for f in fields.values():
        _validate_evidence(f, sources)
    unlocated = raw.get("unlocated", [])
    if not isinstance(unlocated, list):
        raise ValueError("unlocated must be a list")
    ids = set(fields)
    for f in unlocated:
        if (not isinstance(f, dict) or not isinstance(f.get("id"), str) or f["id"] in ids or "addr" in f
                or not f.get("name") or f.get("memory_hint") not in (RAM, EEPROM, "unknown")):
            raise ValueError(f"Invalid unlocated parameter: {f}")
        ids.add(f["id"])
        _validate_evidence(f, sources)
    return {**raw, "fields": list(fields.values()), "sources": sources, "unlocated": unlocated}


def profiles() -> list[str]:
    return sorted(p.stem for p in MAPS_DIR.glob("*.yaml"))


def by_key(profile: dict) -> dict[tuple[str, int], dict]:
    return {(f["mem"], f["addr"]): f for f in profile["fields"]}


def _addr(f: dict) -> str:
    a = f"0x{f['addr']:02X}"
    if f.get("count", 1) > 1:
        a += f"–0x{f['addr'] + f['count'] - 1:02X}"
    return a


def _scale(f: dict) -> str:
    parts = []
    if f.get("scale", 1) != 1:
        parts.append(f"×{f['scale']}")
    if f.get("offset"):
        parts.append(f"{f['offset']:+}")
    if f.get("encoding"):
        parts.append(f["encoding"])
    return " ".join(parts)


def _values(f: dict) -> str:
    v = f.get("values")
    return ", ".join(f"{k}={n}" if not isinstance(k, int) or k < 10 else f"0x{k:02X}={n}"
                     for k, n in v.items()) if v else ""


def _cell(s) -> str:
    return str(s or "").replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(names: list[str]) -> str:
    profs = [load(n) for n in names]
    out = [
        "# Memory map",
        "",
        "<!-- Generated by `plz gen-docs` from maps/*.yaml: edit the YAML, not this file. -->",
        "",
        "Every address is one byte. RAM and EEPROM are separate address spaces "
        "(see [protocol.md](protocol.md)). Addresses are hexadecimal unless noted.",
        "",
        "## Status legend",
        "",
    ]
    out += [f"- **{s}**: {h}" for s, h in STATUS_HELP.items()]
    out += ["", "## Same parameter, different address", "",
            "Where each profile places a parameter (`—` absent, ~~struck~~ refuted).", ""]
    ids = []
    for p in profs:
        ids += [f["id"] for f in p["fields"] if f["id"] not in ids]
    out.append("| Parameter | " + " | ".join(p["profile"] for p in profs) + " |")
    out.append("|---" * (len(profs) + 1) + "|")
    for i in ids:
        cells = []
        for p in profs:
            f = next((f for f in p["fields"] if f["id"] == i), None)
            if f is None:
                cells.append("—")
            else:
                a = f"{f['mem']} {_addr(f)}"
                cells.append(f"~~{a}~~" if f["status"] == "refuted" else a)
        if sum(c != "—" for c in cells) > 1:
            out.append(f"| {i} | " + " | ".join(cells) + " |")

    for p in profs:
        out += ["", f"## {p.get('title', p['profile'])}", "", f"Profile `{p['profile']}`"
                + (f", extends `{p['extends']}`" if p.get("extends") else "") + ".", ""]
        for mem in (RAM, EEPROM):
            fs = sorted((f for f in p["fields"] if f["mem"] == mem), key=lambda f: f["addr"])
            if not fs:
                continue
            out += [f"### {mem.upper()}", "",
                    "| Address | Dec | Name | Unit | Scale | Values | Access | Status | Write certainty | Sources | Notes |",
                    "|---|---|---|---|---|---|---|---|---|---|---|"]
            for f in fs:
                out.append("| " + " | ".join(_cell(x) for x in (
                    _addr(f), f["addr"], f["name"], f.get("unit"), _scale(f), _values(f),
                    f.get("access", "r"), f["status"], f["write_status"],
                    ", ".join(f.get("sources", [])), f.get("notes"))) + " |")
            out.append("")
        out += ["### Claim-specific evidence", "",
                "Source credit distinguishes address, representation and interpretation. "
                "A third-party address is not evidence of Lara applicability. Legacy sources without "
                "structured claims remain unclassified.", ""]

        def evidence_rows(field, path=""):
            identity = path + field["id"]
            for record in field.get("evidence", []):
                yield f"- `{identity}`: **{record['origin']} / {record['method']}**; supports " \
                      f"{', '.join(record['supports'])}; `{record['source']}` — {record['claim']}"
            for child in field.get("members", []):
                yield from evidence_rows(child, identity + ".")

        for f in p["fields"] + p.get("unlocated", []):
            out.extend(evidence_rows(f))
        if p.get("unlocated"):
            out += ["", "### Unlocated parameters", "",
                    "Inventory only: no address, no generated entity, no assumed storage or encoding.", "",
                    "| Parameter | Memory to investigate | Category | Notes |", "|---|---|---|---|"]
            for f in p["unlocated"]:
                out.append("| " + " | ".join(_cell(v) for v in (
                    f["name"], f["memory_hint"], f.get("category"), f.get("notes"))) + " |")
        out += ["Sources:", ""] + [f"- `{k}`: {v}" for k, v in p["sources"].items()]
    return "\n".join(out).rstrip() + "\n"


def _q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def gen_device_map(name: str, field_ids: list[str] | None = None, interval_ms: int = 15000) -> str:
    """Compact read-only dashboard JSON, independent of compiled ESPHome entities."""
    from .memory_html import region

    if type(interval_ms) is not int or not 100 <= interval_ms <= 86400000:
        raise ValueError("interval_ms must be 100..86400000")
    profile = load(name)
    fields = []

    def leaves(field, prefix=""):
        identity = prefix + field["id"]
        if field["members"]:
            for child in field["members"]:
                yield from leaves(child, identity + ".")
        else:
            yield {**field, "id": identity}

    available = [leaf for field in profile["fields"] for leaf in leaves(region(field))]
    if field_ids:
        missing = set(field_ids) - {field["id"] for field in available}
        if missing:
            raise ValueError(f"Unknown or unlocated fields: {', '.join(sorted(missing))}")
    for field in available:
        if field_ids and field["id"] not in field_ids:
            continue
        if not field_ids and field["status"] not in ("observed", "confirmed"):
            continue
        if field.get("encoding", "uint8") not in (
            "uint8", "int8", "bcd", "uint16_le", "uint16_be", "int16_le", "int16_be"
        ):
            raise ValueError(f"Unsupported device encoding: {field['id']}")
        if field["width"] not in (1, 2) or (field["width"] == 2 and "16" not in field.get("encoding", "")):
            if field_ids:
                raise ValueError(f"Field needs scalar members or a supported encoding: {field['id']}")
            continue
        if not all(type(field.get(key, default)) in (int, float) and
                   math.isfinite(field.get(key, default)) for key, default in (("scale", 1), ("offset", 0))):
            raise ValueError(f"Invalid numeric conversion: {field['id']}")
        fields.append({key: field[key] for key in (
            "id", "name", "mem", "addr", "width", "encoding", "scale", "offset", "unit", "values", "status"
        ) if key in field})
    if not fields or len(fields) > 48:
        raise ValueError("Select 1..48 located scalar fields with --field")
    if len({(field["mem"], field["addr"] + offset) for field in fields for offset in range(field["width"])}) > 64:
        raise ValueError("Selected fields exceed 64 unique bytes")
    text = json.dumps({"format": 1, "maps": [{
        "id": profile["profile"], "name": profile.get("title", profile["profile"]),
        "interval_ms": interval_ms, "fields": fields,
    }]}, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n"
    if len(text.encode()) > 8192:
        raise ValueError("Map exceeds 8192 bytes; select fewer fields with --field")
    return text


def gen_esphome(name: str, statuses=("confirmed", "observed", "hypothesis"), hub: str = "stove") -> str:
    """ESPHome package with one entity per field. Hypotheses are created disabled by default."""
    p = load(name)
    blocks: dict[str, list[str]] = {"sensor": [], "text_sensor": [], "number": []}
    names = Counter(f["name"] for f in p["fields"])
    fields = list(p["fields"])

    def members(parent):
        for member in parent.get("members", []):
            child = {
                "mem": parent["mem"], "status": parent["status"], "access": "r",
                "sources": parent.get("sources", []), "interval": "300s",
                **member, "addr": parent["addr"] + member["byte_offset"],
                "id": f"{parent['id']}_{member['id']}",
                "name": f"{parent['id'].replace('_', ' ')}: {member.get('name', member['id'])}",
            }
            if child.get("members"):
                yield from members(child)
            else:
                yield _norm(child)

    for parent in p["fields"]:
        fields.extend(members(parent))
    for f in sorted(fields, key=lambda f: (f["mem"], f["addr"])):
        if f["status"] not in statuses or f.get("count", 1) > 1:
            continue
        hyp = f["status"] == "hypothesis"
        label = f["name"].replace(" / ", ", ").replace("/", " or ")
        if names[f["name"]] > 1:
            label += f" {f['mem']} 0x{f['addr']:02X}"
        e = [f"  - platform: palazzetti", f"    palazzetti_id: {hub}", f"    id: {f['id']}",
             f"    name: {_q(label + (' (?)' if hyp else ''))}"]
        if f["mem"] == EEPROM:
            e.append("    memory: eeprom")
        e.append(f"    address: 0x{f['addr']:02X}")
        if f.get("encoding"):
            e.append(f"    encoding: {f['encoding']}")
        if hyp:
            e.append("    disabled_by_default: true")
        e.append(f"    update_interval: {f.get('interval', '60s' if f['mem'] == EEPROM else '15s')}")
        if f.get("access") == "rw" and f["write_status"] == "confirmed":
            scale, offset = f.get("scale", 1), f.get("offset", 0)
            low, high = sorted((f["raw_min"] * scale + offset, f["raw_max"] * scale + offset))
            e += ["    entity_category: config", f"    min_value: {f.get('min', low)}",
                  f"    max_value: {f.get('max', high)}"]
            if f.get("unit"):
                e.append(f"    unit_of_measurement: {_q(f['unit'])}")
            e += [f"    step: {scale}", f"    multiply: {scale}", f"    offset: {offset}"]
            blocks["number"] += e
        elif f.get("values"):
            e.append("    map:")
            e += [f"      0x{k:02X}: {_q(v)}" for k, v in f["values"].items()]
            blocks["text_sensor"] += e
        else:
            if f.get("unit"):
                e.append(f"    unit_of_measurement: {_q(f['unit'])}")
            if f.get("unit") == "°C":
                e += ["    device_class: temperature", "    state_class: measurement"]
            if f.get("scale", 1) != 1 or f.get("offset"):
                e.append("    filters:")
                if f.get("scale", 1) != 1:
                    e.append(f"      - multiply: {f['scale']}")
                if f.get("offset"):
                    e.append(f"      - offset: {f['offset']}")
            blocks["sensor"] += e
    out = [f"# Generated by `plz gen-esphome {name}` from maps/{name}.yaml: do not edit.",
           f"# Statuses included: {', '.join(statuses)} (hypotheses are disabled by default).",
           "# Write controls require separate confirmed write evidence; runtime write modes start off.",
           "palazzetti:", f"  id: {hub}"]
    rules = [field for field in p["fields"] if field["write_status"] == "confirmed" and field["status"] in statuses]
    if not rules:
        out.append("  write_allowlist: []")
    else:
        out.append("  write_allowlist:")
        for field in rules:
            bounds = [(field["raw_min"], field["raw_max"])]
            if field.get("values"):
                bounds = [(value, value) for value in field["values"] if field["raw_min"] <= value <= field["raw_max"]]
            for low, high in bounds:
                out += [f"    - memory: {field['mem']}", f"      address: 0x{field['addr']:02X}",
                        f"      min_value: {low}", f"      max_value: {high}",
                        f"      evidence: {_q(', '.join(field['write_sources']))}"]
    for k, lines in blocks.items():
        if lines:
            out += ["", f"{k}:"] + lines
    return "\n".join(out) + "\n"
