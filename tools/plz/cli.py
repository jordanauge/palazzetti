"""plz: reverse-engineering lab for Palazzetti/Micronova stoves. See docs/reverse-engineering.md."""

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

from . import analyze, maps
from .client import LabClient
from .codec import parse_mem, parse_num, parse_target
from .session import Session, events, resolve, samples


def default_session() -> str:
    return os.environ.get("PLZ_SESSION") or f"lab-{dt.date.today():%Y-%m-%d}"


def _client(a) -> LabClient:
    return LabClient(a.host, a.port)


def _ts(t: float) -> str:
    return dt.datetime.fromtimestamp(t).strftime("%H:%M:%S")


def cmd_info(a):
    with _client(a) as c:
        print(c.greeting)
        for k, v in c.info().items():
            print(f"{k}={v}")


def cmd_send(a):
    with _client(a) as c:
        print("\n".join(c.command(" ".join(a.line))))


def cmd_read(a):
    mem, addr = parse_mem(a.mem), parse_num(a.addr)
    with _client(a) as c, Session(a.session) as s:
        v = c.read(mem, addr)
        s.read(mem, addr, v)
        print(f"{mem} 0x{addr:03X} = 0x{v:02X} ({v})")


def cmd_inspect(a):
    with _client(a) as client, Session(a.session) as log:
        result = client.inspect(parse_mem(a.mem), parse_num(a.addr))
        log.log("read" if result["valid"] else "read_failed", **result)
        print(json.dumps(result, sort_keys=True))


def cmd_write(a):
    mem, addr, val = parse_mem(a.mem), parse_num(a.addr), parse_num(a.value)
    with _client(a) as c, Session(a.session) as s:
        before = c.read(mem, addr)
        reply = c.write(mem, addr, val)
        after = c.read(mem, addr)
        s.mark(f"write {mem} 0x{addr:03X}: {before} -> {val}" + (f" ({a.note})" if a.note else ""))
        s.write(mem, addr, val, reply)
        s.read(mem, addr, after)
        print(f"{mem} 0x{addr:03X}: {before} -> {val}, read back {after}; {reply}")
        if after != val:
            sys.exit(2)


def cmd_raw(a):
    with _client(a) as c:
        print(c.raw(bytes.fromhex(a.frame), a.reply_len).hex(" ").upper())


def _scan(c: LabClient, s: Session, targets) -> dict:
    snap = {}
    for mem, lo, hi in targets:
        t = time.time()
        vals = [None] * (hi - lo + 1)
        for addr, v in c.dump(mem, lo, hi):
            vals[addr - lo] = v
            if v is not None:
                snap[mem, addr] = v
        s.scan(mem, lo, vals, t=t)
    return snap


def cmd_dump(a):
    targets = [parse_target(t) for t in a.targets]
    with _client(a) as c, Session(a.session) as s:
        snap = _scan(c, s, targets)
    for mem, lo, hi in targets:
        for row in range(lo - lo % 16, hi + 1, 16):
            cells = [f"{snap[mem, x]:02X}" if (mem, x) in snap else ("--" if lo <= x <= hi else "  ")
                     for x in range(row, row + 16)]
            print(f"{mem:6} 0x{row:03X}: " + " ".join(cells))


def cmd_watch(a):
    targets = [parse_target(t) for t in a.targets]
    ignore = {(m, x) for t in a.ignore for m, lo, hi in [parse_target(t)] for x in range(lo, hi + 1)}
    end = time.time() + a.duration if a.duration else None
    prev: dict = {}
    print(f"session {resolve(a.session)}; Ctrl-C to stop", file=sys.stderr)
    with _client(a) as c, Session(a.session) as s:
        try:
            while end is None or time.time() < end:
                t0 = time.time()
                snap = _scan(c, s, targets)
                for k, v in snap.items():
                    if prev and k not in ignore and prev.get(k) != v:
                        print(f"{_ts(t0)} {k[0]} 0x{k[1]:03X}: {prev.get(k)} -> {v}", flush=True)
                prev = snap
                time.sleep(max(0.0, a.interval - (time.time() - t0)))
        except KeyboardInterrupt:
            pass


def cmd_monitor(a):
    with _client(a) as c, Session(a.session) as s:
        try:
            for mem, addr, v in c.monitor():
                s.read(mem, addr, v)
                print(f"{_ts(time.time())} {mem} 0x{addr:03X} {v}", flush=True)
        except KeyboardInterrupt:
            pass


def cmd_mark(a):
    with Session(a.session) as s:
        rec = s.mark(" ".join(a.text))
    print(f"{_ts(rec['t'])} marked in {resolve(a.session)}")


def cmd_marks(a):
    for e in events(a.session):
        if e["ev"] == "mark":
            print(f"{e['t']:.0f} {dt.datetime.fromtimestamp(e['t']):%Y-%m-%d %H:%M:%S} {e['text']}")


def _when(evs, spec: str) -> float:
    if spec == "start":
        return evs[0]["t"]
    if spec == "end":
        return evs[-1]["t"]
    try:
        return float(spec)
    except ValueError:
        for e in evs:
            if e["ev"] == "mark" and spec in e["text"]:
                return e["t"]
    raise SystemExit(f"no mark matching {spec!r}")


def cmd_diff(a):
    evs = list(events(a.session))
    t1, t2 = _when(evs, a.frm), _when(evs, a.to)
    labels = _labels(a.profile)
    for k, x, y in analyze.diff(analyze.snapshot_at(evs, t1), analyze.snapshot_at(evs, t2 + a.after)):
        print(f"{k[0]} 0x{k[1]:03X} {labels.get(k, ''):30} {x} -> {y}")


def _labels(profile: str | None) -> dict:
    if not profile:
        return {}
    return {k: f"{f['name']} [{f['status']}]" for k, f in maps.by_key(maps.load(profile)).items()}


def cmd_analyze(a):
    key, names = None, {}
    if a.state:
        mem, addr, _ = parse_target(a.state)
        key = (mem, addr)
        if a.profile:
            names = {int(k): v for k, v in maps.by_key(maps.load(a.profile)).get(key, {}).get("values", {}).items()}
    text = analyze.report(events(a.session), key, _labels(a.profile), names, a.window)
    if a.output:
        Path(a.output).write_text(text)
    else:
        print(text)


def cmd_import_legacy(a):
    from .legacy import import_dump

    with Session(a.session) as s:
        n, v = import_dump(a.file, s, parse_mem(a.mem))
    print(f"{n} scans, {v} values -> {resolve(a.session)}")


def cmd_gen_docs(a):
    text = maps.render_markdown(a.profiles or maps.profiles())
    Path(a.output).write_text(text) if a.output else print(text)


def cmd_gen_esphome(a):
    text = maps.gen_esphome(a.profile)
    Path(a.output).write_text(text) if a.output else print(text)


def cmd_gen_html(a):
    from .memory_html import generate

    for path in generate(a.output, a.profiles or maps.profiles(), a.capture,
                         a.legacy_dir, a.evidence_profile):
        print(path)


def cmd_emulate(a):
    import asyncio

    from .emulator import Emulator

    image = {}
    if a.seed:
        for _t, mem, addr, v in samples(events(a.seed)):
            image[mem, addr] = v
    emu = Emulator(image, allow_write=not a.read_only, fail_rate=a.fail_rate)
    port = a.port or 6638
    print(f"emulating {len(image)} bytes on {a.listen}:{port}", file=sys.stderr)
    asyncio.run(emu.serve(a.listen, port))


def main(argv=None):
    p = argparse.ArgumentParser(prog="plz", description=__doc__)
    p.add_argument("--host", help="lab server host (env PLZ_HOST, default palazzetti.local)")
    p.add_argument("--port", type=int, help="lab server port (env PLZ_PORT, default 6638)")
    p.add_argument("-s", "--session", default=default_session(),
                   help="session name or path (env PLZ_SESSION, default lab-<date>; dir env PLZ_SESSIONS)")
    sub = p.add_subparsers(required=True, metavar="command")

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.set_defaults(fn=fn)
        return sp

    add("info", cmd_info, "bus statistics of the device")
    add("send", cmd_send, "send a raw lab command line").add_argument("line", nargs="+")
    sp = add("read", cmd_read, "read one byte")
    sp.add_argument("mem"), sp.add_argument("addr")
    sp = add("inspect", cmd_inspect, "read one byte with raw reply, checksum status, attempts and latency")
    sp.add_argument("mem"), sp.add_argument("addr")
    sp = add("write", cmd_write, "write one byte, read it back, log a mark (needs allow_write)")
    sp.add_argument("mem"), sp.add_argument("addr"), sp.add_argument("value")
    sp.add_argument("-n", "--note", default="")
    sp = add("raw", cmd_raw, "send a checked two-byte raw READ frame (writes rejected)")
    sp.add_argument("frame"), sp.add_argument("reply_len", type=int)
    add("dump", cmd_dump, "dump ranges, e.g. ram:0-0xFF eeprom:0-0x7F").add_argument("targets", nargs="+")
    sp = add("watch", cmd_watch, "scan ranges periodically, print and log changes")
    sp.add_argument("targets", nargs="+")
    sp.add_argument("-i", "--interval", type=float, default=10.0, help="seconds between scans")
    sp.add_argument("-d", "--duration", type=float, default=0, help="seconds (0: forever)")
    sp.add_argument("-x", "--ignore", action="append", default=[], help="mem:range not to print")
    add("monitor", cmd_monitor, "log every value the device polls (passive)")
    add("mark", cmd_mark, "annotate the session (what you just did or saw)").add_argument("text", nargs="+")
    add("marks", cmd_marks, "list marks of the session")
    sp = add("diff", cmd_diff, "values that differ between two points (mark text, unix time, start, end)")
    sp.add_argument("frm", metavar="from"), sp.add_argument("to")
    sp.add_argument("-a", "--after", type=float, default=0, help="extra seconds after 'to'")
    sp.add_argument("-p", "--profile")
    sp = add("analyze", cmd_analyze, "markdown report: stats, state correlation, changes after marks")
    sp.add_argument("--state", help="state register, e.g. ram:0xF9")
    sp.add_argument("-p", "--profile", help="map profile used for labels")
    sp.add_argument("-w", "--window", type=float, default=120.0, help="seconds after each mark")
    sp.add_argument("-o", "--output")
    sp = add("import-legacy", cmd_import_legacy, "import a legacy Arduino dump (.txt or .txt.xz)")
    sp.add_argument("file"), sp.add_argument("--mem", default="ram")
    sp = add("gen-docs", cmd_gen_docs, "render docs/memory-map.md from maps/")
    sp.add_argument("profiles", nargs="*"), sp.add_argument("-o", "--output")
    sp = add("gen-esphome", cmd_gen_esphome, "ESPHome entities package from a map profile")
    sp.add_argument("profile"), sp.add_argument("-o", "--output")
    sp = add("gen-html", cmd_gen_html, "self-contained RAM and EEPROM hex maps with hover details")
    sp.add_argument("profiles", nargs="*")
    sp.add_argument("-o", "--output", default="docs")
    sp.add_argument("--capture", action="append", default=[], help="JSONL session (repeatable)")
    sp.add_argument("--legacy-dir", action="append", default=[], help="timestamped addr-XX directory (repeatable)")
    sp.add_argument("--evidence-profile", default="palazzetti-ecofire-lara",
                    help="board profile that the selected captures belong to")
    sp = add("emulate", cmd_emulate, "fake lab server, optionally seeded from a session")
    sp.add_argument("--listen", default="127.0.0.1"), sp.add_argument("--read-only", action="store_true")
    sp.add_argument("--fail-rate", type=float, default=0.0)
    sp.add_argument("--seed", metavar="SESSION", help="memory image = last values seen in this session")
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
