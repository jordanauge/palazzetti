"""Import of the legacy Arduino dumps (legacy/arduino, 2020).

Line format: `<unix ts> <success 0|1> <addr> <value>`, one full RAM scan after another.
The legacy decoder did not mask its checksum to 8 bits (legacy/arduino/src/rwms.cc, RCSUM),
so every reply with addr + value >= 256 was flagged as failed although it was valid.
The flag is therefore ignored: a value is kept unless it is negative/out of range.
"""

import lzma
from pathlib import Path

from .session import Session


def _open(path: Path):
    return lzma.open(path, "rt") if path.suffix == ".xz" else open(path)


def import_dump(path: str | Path, session: Session, mem: str = "ram") -> tuple[int, int]:
    """Group consecutive addresses into scan events. Returns (scans, values)."""
    path = Path(path)
    n_scans = n_values = 0
    cur: list[int | None] = []
    t0 = start = None

    def flush():
        nonlocal cur, n_scans
        if cur:
            session.scan(mem, start, cur, t=t0)
            n_scans += 1
        cur = []

    with _open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) != 4:
                continue
            t, _flag, addr, value = float(parts[0]), parts[1], int(parts[2], 0), int(parts[3], 0)
            if not cur or addr != start + len(cur):
                flush()
                t0, start = t, addr
            cur.append(value if 0 <= value <= 0xFF else None)
            n_values += 1
    flush()
    return n_scans, n_values
