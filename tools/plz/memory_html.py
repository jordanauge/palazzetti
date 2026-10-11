"""Self-contained hex maps with profile fields and optional capture evidence."""

import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from . import maps
from .analyze import AddrStats
from .codec import EEPROM, MAX_ADDRESS, RAM
from .session import events, samples


def address_events(directory: str | Path):
    """Read timestamped addr-XX logs; failed replies contain a lost-value sentinel."""
    directory = Path(directory)
    files = sorted(directory.glob("addr-*"))
    if not files:
        raise ValueError(f"No addr-XX files in {directory}")
    records = []
    for file in files:
        addr = int(file.name.removeprefix("addr-"), 16)
        if not 0 <= addr <= MAX_ADDRESS:
            raise ValueError(f"Address outside Micronova space: {file}")
        for line_number, line in enumerate(file.read_text().splitlines(), 1):
            parts = line.split()
            if len(parts) != 3:
                raise ValueError(f"{file}:{line_number}: expected timestamp, true/false, hex value")
            stamp, flag, raw = parts
            timestamp, value = float(stamp), int(raw, 16)
            if flag not in ("true", "false") or not math.isfinite(timestamp) or not 0 <= value <= 255:
                raise ValueError(f"{file}:{line_number}: invalid sample")
            records.append({
                "t": timestamp, "ev": "scan", "mem": RAM, "start": addr,
                "values": [value if flag == "true" else None],
            })
    yield from sorted(records, key=lambda record: record["t"])


def capture(name: str, records, profile: str) -> dict:
    stats: dict[tuple[str, int], AddrStats] = defaultdict(AddrStats)
    rejected = Counter()
    history = defaultdict(list)
    first = last = None
    previous = -math.inf
    for event in records:
        timestamp = event["t"]
        if not math.isfinite(timestamp) or timestamp < previous:
            raise ValueError(f"Capture {name}: timestamps must be finite and chronological")
        previous = timestamp
        first = timestamp if first is None else first
        last = timestamp
        if event["ev"] == "scan":
            for index, value in enumerate(event["values"]):
                if value is None:
                    rejected[event["mem"], event["start"] + index] += 1
        # A requested write is not independent evidence of what memory contains.
        if event["ev"] not in ("scan", "read"):
            continue
        for timestamp, memory, addr, value in samples([event]):
            if memory not in (RAM, EEPROM) or not 0 <= addr <= MAX_ADDRESS or not 0 <= value <= 255:
                raise ValueError(f"Capture {name}: invalid memory sample")
            key = memory, addr
            stats[key].add(timestamp, value)
            history[key].append([timestamp, value])
            if len(history[key]) > 256:
                history[key] = history[key][::2]
    result = {"name": name, "profile": profile, "first": first, "last": last, "bytes": {}}
    for key in sorted(stats.keys() | rejected.keys()):
        memory, addr = key
        stat = stats.get(key)
        record = {"rejected": rejected[key], "n": stat.n if stat else 0}
        if stat:
            points = history[key]
            if points[-1][0] != stat.last_t:
                points.append([stat.last_t, stat.last])
            record.update({
                "last": stat.last, "min": min(stat.values), "max": max(stat.values),
                "changes": stat.changes, "distinct": len(stat.values),
                "first_t": stat.first_t, "last_t": stat.last_t,
                "histogram": sorted(stat.values.items()), "points": points,
            })
        result["bytes"][f"{memory}:{addr}"] = record
    return result


def field_width(field: dict) -> int:
    width = field.get("count", 2 if "16" in field.get("encoding", "") else 1)
    if not isinstance(width, int) or width < 1:
        raise ValueError(f"Invalid field width: {field}")
    return width


def region(field: dict, base: int = 0, inherited: dict | None = None) -> dict:
    field = {**(inherited or {}), **field}
    addr = base + field["byte_offset"] if inherited is not None else field["addr"]
    width = field_width(field)
    if "16" in field.get("encoding", "") and width != 2:
        raise ValueError(f"16-bit field must span two bytes: {field['id']}")
    if field.get("status", "unknown") not in maps.STATUSES:
        raise ValueError(f"Unknown evidence status: {field['id']}")
    if addr < 0 or addr + width - 1 > MAX_ADDRESS:
        raise ValueError(f"Field outside Micronova space: {field['id']}")
    result = {**field, "addr": addr, "width": width, "members": []}
    for member in field.get("members", []):
        child = region(member, addr, {
            "status": field["status"], "sources": field.get("sources", []),
            "mem": field["mem"], "access": field.get("access", "r"),
        })
        if child["addr"] < addr or child["addr"] + child["width"] > addr + width:
            raise ValueError(f"Member {child['id']} outside {field['id']}")
        result["members"].append(child)
    return result


def render(memory: str, names: list[str], captures: list[dict] | None = None) -> str:
    if memory not in (RAM, EEPROM):
        raise ValueError(f"Unknown memory: {memory}")
    if not names:
        raise ValueError("At least one profile is required")
    profiles = []
    for name in names:
        profile = maps.load(name)
        profiles.append({
            "id": profile["profile"], "title": profile["title"], "sources": profile["sources"],
            "fields": [region(field) for field in profile["fields"] if field["mem"] == memory],
        })
    memory_captures = [
        {**record, "bytes": {key: value for key, value in record["bytes"].items()
                            if key.startswith(f"{memory}:")}}
        for record in captures or []
        if any(key.startswith(f"{memory}:") for key in record["bytes"])
    ]
    payload = json.dumps({
        "memory": memory, "profiles": profiles, "captures": memory_captures,
        "statuses": maps.STATUS_HELP,
    }, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = Path(__file__).with_name("memory_html.html").read_text()
    return template.replace("__TITLE__", html.escape(f"{memory.upper()} hex map")).replace("__DATA__", payload)


def generate(directory: str | Path, names: list[str], session_names: list[str],
             legacy_dirs: list[str], evidence_profile: str) -> tuple[Path, Path]:
    captures = [capture(Path(name).name, events(name), evidence_profile) for name in session_names]
    for name in legacy_dirs:
        record = capture(Path(name).name, address_events(name), evidence_profile)
        record["notes"] = ("Historical firmware callbacks, not revalidated raw replies. "
                           "Zero checksums were accepted; failed reads lost the byte value.")
        captures.append(record)
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    paths = tuple(output / f"memory-{memory}.html" for memory in (RAM, EEPROM))
    for memory, path in zip((RAM, EEPROM), paths):
        path.write_text(render(memory, names, captures), encoding="utf-8")
    return paths
