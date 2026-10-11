"""Offline analysis of lab sessions: statistics, state correlation, changes around marks."""

import datetime as dt
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .session import samples

Key = tuple[str, int]


@dataclass
class AddrStats:
    n: int = 0
    values: Counter = field(default_factory=Counter)
    changes: int = 0
    last: int | None = None
    first_t: float = 0.0
    last_t: float = 0.0

    def add(self, t: float, v: int):
        if self.n == 0:
            self.first_t = t
        elif v != self.last:
            self.changes += 1
        self.n += 1
        self.values[v] += 1
        self.last = v
        self.last_t = t

    @property
    def kind(self) -> str:
        d = len(self.values)
        if d == 1:
            return "constant"
        if d == 2:
            return "binary"
        if self.changes > 0.5 * self.n:
            return "noisy"
        return "varying"

    def summary(self, top: int = 4) -> str:
        common = ", ".join(f"{v}×{c}" for v, c in self.values.most_common(top))
        return f"{min(self.values)}–{max(self.values)}; {len(self.values)} values; {common}"


def stats(evs) -> dict[Key, AddrStats]:
    out: dict[Key, AddrStats] = defaultdict(AddrStats)
    for t, mem, addr, v in samples(evs):
        out[mem, addr].add(t, v)
    return dict(sorted(out.items()))


def timeline(evs, key: Key) -> list[tuple[float, int]]:
    """Transitions (t, new value) of one address."""
    out, last = [], None
    for t, mem, addr, v in samples(evs):
        if (mem, addr) == key and v != last:
            out.append((t, v))
            last = v
    return out


def by_state(evs, key: Key) -> dict[Key, dict[int, Counter]]:
    """For each address, the value distribution while `key` holds each of its values."""
    out: dict[Key, dict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
    state = None
    for _t, mem, addr, v in samples(evs):
        if (mem, addr) == key:
            state = v
        elif state is not None:
            out[mem, addr][state][v] += 1
    return out


def eta_squared(per_state: dict[int, Counter]) -> float:
    """Share of the value variance explained by the state (0: unrelated, 1: fully determined)."""
    n = sum(sum(c.values()) for c in per_state.values())
    if n == 0:
        return 0.0
    mean = sum(v * k for c in per_state.values() for v, k in c.items()) / n
    total = sum(k * (v - mean) ** 2 for c in per_state.values() for v, k in c.items())
    if total == 0:
        return 0.0
    between = 0.0
    for c in per_state.values():
        m = sum(c.values())
        if m:
            between += m * (sum(v * k for v, k in c.items()) / m - mean) ** 2
    return between / total


def correlated(evs, key: Key, threshold: float = 0.5) -> list[tuple[Key, float, dict[int, Counter]]]:
    res = [(k, eta_squared(ps), ps) for k, ps in by_state(evs, key).items()]
    return sorted((r for r in res if r[1] >= threshold), key=lambda r: -r[1])


def snapshot_at(evs, t: float) -> dict[Key, int]:
    snap: dict[Key, int] = {}
    for ts, mem, addr, v in samples(evs):
        if ts > t:
            break
        snap[mem, addr] = v
    return snap


def diff(a: dict[Key, int], b: dict[Key, int]) -> list[tuple[Key, int | None, int | None]]:
    return [(k, a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


def around_marks(evs, window: float = 120.0, ignore: set[Key] | None = None):
    """For each mark, addresses whose value changed between the mark and mark + window."""
    evs = list(evs)
    ignore = ignore or set()
    for e in evs:
        if e["ev"] != "mark":
            continue
        before = snapshot_at(evs, e["t"])
        after = snapshot_at(evs, e["t"] + window)
        yield e, [d for d in diff(before, after) if d[0] not in ignore]


def noisy(st: dict[Key, AddrStats]) -> set[Key]:
    return {k for k, s in st.items() if s.kind == "noisy"}


def fmt_key(k: Key) -> str:
    return f"{k[0]} 0x{k[1]:03X}"


def fmt_dist(c: Counter, top: int = 3) -> str:
    return f"{min(c)}–{max(c)} (" + ", ".join(f"{v}×{n}" for v, n in c.most_common(top)) + ")"


def report(evs, key: Key | None = None, labels: dict[Key, str] | None = None,
           state_names: dict[int, str] | None = None, window: float = 120.0) -> str:
    evs = list(evs)
    labels = labels or {}
    state_names = state_names or {}
    st = stats(evs)
    lines = ["# Session analysis", ""]
    ts = [e["t"] for e in evs]
    if ts:
        lines += [f"{len(evs)} events, {(max(ts) - min(ts)) / 3600:.1f} h, {len(st)} addresses.", ""]

    lines += ["## Addresses", "", "| Address | Known as | Kind | Changes | Values |", "|---|---|---|---|---|"]
    for k, s in st.items():
        lines.append(f"| {fmt_key(k)} | {labels.get(k, '')} | {s.kind} | {s.changes} | {s.summary()} |")

    def name(v: int) -> str:
        return state_names.get(v, f"0x{v:02X}")

    if key:
        lines += ["", f"## Timeline of {fmt_key(key)}", ""]
        for t, v in timeline(evs, key):
            lines.append(f"- {dt.datetime.fromtimestamp(t):%Y-%m-%d %H:%M:%S} → {name(v)}")
        lines += ["", f"## Addresses explained by {fmt_key(key)} (η² ≥ 0.5)", "",
                  "| Address | Known as | η² | Per state |", "|---|---|---|---|"]
        for k, eta, ps in correlated(evs, key):
            per = "; ".join(f"{name(s)}: {fmt_dist(c)}" for s, c in sorted(ps.items()))
            lines.append(f"| {fmt_key(k)} | {labels.get(k, '')} | {eta:.2f} | {per} |")

    marks = list(around_marks(evs, window, ignore=noisy(st)))
    if marks:
        lines += ["", f"## Changes within {window:.0f} s after each mark (noisy addresses ignored)", ""]
        for e, changes in marks:
            lines.append(f"### {dt.datetime.fromtimestamp(e['t']):%Y-%m-%d %H:%M:%S} — {e['text']}")
            lines.append("")
            for k, a, b in changes:
                lines.append(f"- {fmt_key(k)} {labels.get(k, '')}: {a} → {b}")
            if not changes:
                lines.append("- no change")
            lines.append("")
    return "\n".join(lines) + "\n"
