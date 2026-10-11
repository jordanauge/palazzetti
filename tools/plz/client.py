"""Client of the ESPHome lab server (components/palazzetti/lab_server.cpp)."""

import os
import socket
from collections.abc import Iterator

from .codec import parse_mem

DEFAULT_PORT = 6638


class LabError(RuntimeError):
    pass


class LabClient:
    def __init__(self, host: str | None = None, port: int | None = None, timeout: float = 30.0):
        self.host = host or os.environ.get("PLZ_HOST", "palazzetti.local")
        self.port = port or int(os.environ.get("PLZ_PORT", DEFAULT_PORT))
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self.file = self.sock.makefile("r", encoding="ascii", newline="\n")
        self.greeting = self._line()

    def close(self):
        self.file.close()
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _line(self) -> str:
        line = self.file.readline()
        if not line:
            raise LabError("connection closed")
        return line.rstrip("\r\n")

    def _send(self, cmd: str):
        self.sock.sendall(cmd.encode("ascii") + b"\n")

    def command(self, cmd: str) -> list[str]:
        """Send a command, return all lines up to and including the final ok/err line."""
        self._send(cmd)
        lines = []
        while True:
            line = self._line()
            lines.append(line)
            if line.startswith("ok") or line.startswith("err"):
                return lines

    def _ok(self, cmd: str) -> list[str]:
        lines = self.command(cmd)
        if lines[-1].startswith("err"):
            raise LabError(lines[-1])
        return lines

    def info(self) -> dict[str, str]:
        line = self._ok("info")[-1]
        return dict(tok.split("=", 1) for tok in line.split()[2:])

    def pause(self):
        self._ok("pause")

    def resume(self):
        self._ok("resume")

    def read(self, mem: str, addr: int) -> int:
        line = self._ok(f"r {parse_mem(mem)} {addr:#x}")[-1]
        return int(line.split()[4], 16)

    def inspect(self, mem: str, addr: int) -> dict:
        line = self._ok(f"i {parse_mem(mem)} {addr:#x}")[-1]
        fields = dict(token.split("=", 1) for token in line.split()[2:])
        return self._read_result(fields)

    @staticmethod
    def _read_result(fields: dict[str, str]) -> dict:
        return {
            "mem": fields["mem"], "addr": int(fields["addr"], 0),
            "valid": fields["valid"] == "1", "value": int(fields["value"], 0) if fields["valid"] == "1" else None,
            "check": fields["check"], "tx": fields["tx"], "rx": fields["rx"],
            "attempts": int(fields["attempts"]), "elapsed_ms": int(fields["ms"]),
        }

    def poll_list(self) -> dict:
        lines = self._ok("poll list")
        status = {key: int(value) for key, value in
                  (token.split("=", 1) for token in lines[-1].split()[2:])}
        rules = []
        for line in lines[:-1]:
            if line.startswith("p "):
                fields = dict(token.split("=", 1) for token in line.split()[1:])
                rules.append({"mem": fields["mem"], "start": int(fields["start"], 0),
                              "end": int(fields["end"], 0), "interval_ms": int(fields["interval_ms"])})
        return {**status, "rules": rules}

    def poll_set(self, mem: str, start: int, end: int, interval_ms: int):
        self._ok(f"poll set {parse_mem(mem)} {start:#x} {end:#x} {interval_ms}")

    def poll_remove(self, mem: str, start: int, end: int):
        self._ok(f"poll remove {parse_mem(mem)} {start:#x} {end:#x}")

    def poll_control(self, action: str):
        if action not in ("start", "stop", "clear"):
            raise ValueError("poll control must be start, stop or clear")
        self._ok(f"poll {action}")

    def poll_events(self, after: int = 0) -> dict:
        lines = self._ok(f"poll events {after}")
        status = {key: int(value) for key, value in
                  (token.split("=", 1) for token in lines[-1].split()[2:])}
        results = []
        for line in lines[:-1]:
            if line.startswith("s "):
                fields = dict(token.split("=", 1) for token in line.split()[1:])
                results.append({**self._read_result(fields), "seq": int(fields["seq"]),
                                "uptime_ms": int(fields["uptime_ms"]), "revision": int(fields["revision"])})
        return {**status, "samples": results}

    def write(self, mem: str, addr: int, value: int) -> str:
        return self._ok(f"w {parse_mem(mem)} {addr:#x} {value:#x}")[-1]

    def raw(self, frame: bytes, reply_len: int) -> bytes:
        line = self._ok(f"x {frame.hex().upper()} {reply_len}")[-1]
        hexs = line.split()[2].removeprefix("reply=")
        return bytes.fromhex(hexs)

    def dump(self, mem: str, start: int, end: int) -> Iterator[tuple[int, int | None]]:
        """Yield (addr, value or None on failure) for each address."""
        self._send(f"d {parse_mem(mem)} {start:#x} {end:#x}")
        while True:
            line = self._line()
            if line.startswith("v "):
                _, _, a, v = line.split()
                yield int(a, 16), None if v == "--" else int(v, 16)
            elif line.startswith("ok"):
                return
            elif line.startswith("err"):
                raise LabError(line)

    def monitor(self) -> Iterator[tuple[str, int, int]]:
        """Stream (mem, addr, value) of every successful transaction on the bus. Blocks."""
        self._ok("monitor on")
        self.sock.settimeout(None)
        while True:
            line = self._line()
            if line.startswith("m "):
                _, mem, a, v = line.split()
                yield mem, int(a, 16), int(v, 16)
