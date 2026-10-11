"""Micronova frame codec, mirror of components/palazzetti/micronova.h (see docs/protocol.md)."""

RAM, EEPROM = "ram", "eeprom"
MEMORIES = (RAM, EEPROM)
MAX_ADDRESS = 0x1FFF


def parse_mem(s: str) -> str:
    s = s.lower()
    if s in ("ram", "r"):
        return RAM
    if s in ("eeprom", "e"):
        return EEPROM
    raise ValueError(f"unknown memory {s!r} (ram|eeprom)")


def header(mem: str, write: bool, addr: int) -> int:
    base = (0x80 if write else 0x00) | (0x20 if mem == EEPROM else 0x00)
    return base | ((addr >> 8) & 0x1F)


def checksum(*parts: int) -> int:
    return sum(parts) & 0xFF


def build_read(mem: str, addr: int) -> bytes:
    return bytes([header(mem, False, addr), addr & 0xFF])


def build_write(mem: str, addr: int, value: int) -> bytes:
    h = header(mem, True, addr)
    return bytes([h, addr & 0xFF, value, checksum(h, addr & 0xFF, value)])


def read_reply(frame: bytes, value: int) -> bytes:
    """Reply a stove sends to a read frame."""
    return bytes([checksum(frame[0], frame[1], value), value])


def check_read_reply(frame: bytes, reply: bytes) -> str:
    if reply[0] == checksum(frame[0], frame[1], reply[1]):
        return "ok"
    if reply[0] == checksum(frame[1], reply[1]):
        return "ok-noheader"
    return "bad-checksum"


def bcd_to_int(v: int) -> int:
    return (v >> 4) * 10 + (v & 0x0F)


def int_to_bcd(v: int) -> int:
    return ((v // 10) << 4) | (v % 10)


def parse_num(s: str | int) -> int:
    return s if isinstance(s, int) else int(s, 0)


def parse_range(s: str) -> tuple[int, int]:
    """'0x00-0xFF' or '0x21' -> inclusive range."""
    lo, _, hi = s.partition("-")
    lo = parse_num(lo)
    return lo, parse_num(hi) if hi else lo


def parse_target(s: str) -> tuple[str, int, int]:
    """'ram:0x00-0xFF' -> ('ram', 0, 255)."""
    mem, _, rng = s.partition(":")
    if not rng:
        raise ValueError(f"expected mem:range, got {s!r}")
    return (parse_mem(mem), *parse_range(rng))
