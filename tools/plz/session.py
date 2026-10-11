"""Lab sessions: append-only JSONL logs of everything observed on a stove.

One event per line, `t` is a unix timestamp:
  {"t":..., "ev":"scan",  "mem":"ram", "start":0, "values":[26, null, ...]}   range dump
  {"t":..., "ev":"read",  "mem":"ram", "addr":249, "value":26}               single read / monitor
  {"t":..., "ev":"write", "mem":"eeprom", "addr":78, "value":22, "reply":"..."}
  {"t":..., "ev":"mark",  "text":"switched on from the panel"}                 human/agent annotation

Files may be compressed (.jsonl.xz / .jsonl.gz). Default directory: $PLZ_SESSIONS or ./sessions.
"""

import gzip
import json
import lzma
import os
import time
from collections.abc import Iterator
from pathlib import Path


def sessions_dir() -> Path:
    return Path(os.environ.get("PLZ_SESSIONS", "sessions"))


def resolve(name: str) -> Path:
    p = Path(name)
    if p.suffix or p.parent != Path("."):
        return p
    plain = sessions_dir() / f"{name}.jsonl"
    xz = plain.with_suffix(".jsonl.xz")
    return xz if xz.exists() and not plain.exists() else plain


def _open(path: Path, mode: str):
    if path.suffix == ".xz":
        return lzma.open(path, mode + "t", encoding="utf-8")
    if path.suffix == ".gz":
        return gzip.open(path, mode + "t", encoding="utf-8")
    return open(path, mode, encoding="utf-8")


class Session:
    def __init__(self, name: str):
        self.path = resolve(name)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = _open(self.path, "a")

    def close(self):
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def log(self, ev: str, t: float | None = None, **fields):
        rec = {"t": round(t if t is not None else time.time(), 3), "ev": ev, **fields}
        self._f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self._f.flush()
        return rec

    def scan(self, mem: str, start: int, values: list[int | None], t: float | None = None):
        return self.log("scan", t, mem=mem, start=start, values=values)

    def read(self, mem: str, addr: int, value: int, t: float | None = None):
        return self.log("read", t, mem=mem, addr=addr, value=value)

    def write(self, mem: str, addr: int, value: int, reply: str = "", t: float | None = None):
        return self.log("write", t, mem=mem, addr=addr, value=value, reply=reply)

    def mark(self, text: str, t: float | None = None):
        return self.log("mark", t, text=text)


def events(name: str) -> Iterator[dict]:
    with _open(resolve(name), "r") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def samples(evs) -> Iterator[tuple[float, str, int, int]]:
    """Flatten scans/reads/writes into (t, mem, addr, value) samples, skipping failed reads."""
    for e in evs:
        ev = e["ev"]
        if ev == "scan":
            for i, v in enumerate(e["values"]):
                if v is not None:
                    yield e["t"], e["mem"], e["start"] + i, v
        elif ev in ("read", "write"):
            yield e["t"], e["mem"], e["addr"], e["value"]
