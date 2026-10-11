"""Read-only polling plan selection and independently checked backup passes."""

import datetime as dt
import hashlib
import json
import math
import time
from pathlib import Path

from . import maps
from .codec import MAX_ADDRESS, parse_mem, parse_target
from .session import Session


def targets(specs: list[str]) -> list[tuple[str, int, int]]:
    if not specs:
        raise ValueError("at least one explicit memory range is required")
    ranges = [parse_target(spec) for spec in specs]
    seen = set()
    for mem, start, end in ranges:
        if not 0 <= start <= end <= MAX_ADDRESS:
            raise ValueError(f"invalid target {mem}:{start:#x}-{end:#x}")
        keys = {(mem, addr) for addr in range(start, end + 1)}
        if seen & keys:
            raise ValueError("overlapping targets are not allowed")
        seen.update(keys)
    return ranges


def unknown_ranges(profile: str, selected: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    known = set()

    def visit(field, mem, base, inherited):
        status = field.get("status", inherited)
        start = base + field.get("byte_offset", 0)
        if not field.get("members") and status in ("confirmed", "observed"):
            known.update((mem, addr) for addr in range(start, start + field.get("count", 1)))
        for member in field.get("members", []):
            visit(member, mem, start, status)

    for field in maps.load(profile)["fields"]:
        visit(field, field["mem"], field["addr"], field["status"])
    out = []
    for mem, lo, hi in selected:
        start = None
        for addr in range(lo, hi + 2):
            unknown = addr <= hi and (mem, addr) not in known
            if unknown and start is None:
                start = addr
            if not unknown and start is not None:
                out.append((mem, start, addr - 1))
                start = None
    return out


def validate_plan(plan: dict) -> list[dict]:
    rules = plan["rules"]
    if not isinstance(rules, list) or len(rules) > 32:
        raise ValueError("poll plan requires a list of at most 32 ranges")
    normalized = []
    for rule in rules:
        mem = parse_mem(rule["mem"])
        start, end, interval = rule["start"], rule["end"], rule["interval_ms"]
        if any(type(value) is not int for value in (start, end, interval)):
            raise ValueError("plan addresses and interval_ms must be integers")
        if not 0 <= start <= end <= MAX_ADDRESS or not 100 <= interval <= 86400000:
            raise ValueError("plan address/interval out of bounds")
        normalized.append({"mem": mem, "start": start, "end": end, "interval_ms": interval})
    if normalized:
        targets([f"{r['mem']}:{r['start']}-{r['end']}" for r in normalized])
    return normalized


def backup(client, log: Session, selected, passes: int, gap: float, output: Path) -> dict:
    if passes < 2 or not math.isfinite(gap) or gap < 0:
        raise ValueError("backup requires at least two passes and a finite nonnegative gap")
    selected = targets([f"{mem}:{start}-{end}" for mem, start, end in selected])
    state = client.poll_list()
    paused = client.info().get("paused") == "1"
    output.mkdir(parents=True, exist_ok=False)
    summary = {"format": 1, "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "passes": passes, "targets": selected, "passes_finished": False, "complete": False, "consistent": False,
               "bytes": [], "files": [], "note": "Sequential checked reads, not an atomic RAM snapshot."}
    readings = {(mem, addr): [] for mem, start, end in selected for addr in range(start, end + 1)}
    summary["device"] = {"boot": state["boot"], "polling": state}
    try:
        client.poll_control("stop")
        client.pause()
        for index in range(passes):
            log.log("backup_pass", index=index + 1, phase="start")
            with (output / f"pass-{index + 1:02d}.jsonl").open("x", encoding="utf-8") as file:
                for (mem, addr), values in readings.items():
                    requested_at = time.time()
                    result = client.inspect(mem, addr)
                    record = log.log("read" if result["valid"] else "read_failed",
                                     **result, backup_pass=index + 1, requested_at=requested_at)
                    file.write(json.dumps(record) + "\n")
                    file.flush()
                    values.append(result["value"])
            log.log("backup_pass", index=index + 1, phase="end")
            if index + 1 < passes:
                time.sleep(gap)
        summary["passes_finished"] = True
    finally:
        for path in sorted(output.glob("pass-*.jsonl")):
            summary["files"].append({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for (mem, addr), values in readings.items():
            valid = [value for value in values if value is not None]
            complete = len(values) == passes and len(valid) == passes
            summary["bytes"].append({"mem": mem, "addr": addr, "values": values,
                                     "complete": complete,
                                     "stable": complete and len(set(valid)) == 1})
        summary["complete"] = summary["passes_finished"] and all(row["complete"] for row in summary["bytes"])
        summary["consistent"] = summary["complete"] and all(row["stable"] for row in summary["bytes"])
        summary["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        (output / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
        log.log("backup_summary", output=str(output), complete=summary["complete"],
                consistent=summary["consistent"])
        if not paused:
            client.resume()
        if state["running"]:
            client.poll_control("start")
    return summary
