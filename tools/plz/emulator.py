"""Fake lab server over a memory image: lets the tooling (and an agent) be exercised offline."""

import asyncio
from collections import deque
import random
import time

from .codec import EEPROM, RAM, MAX_ADDRESS, build_read, parse_mem, parse_num, read_reply

Image = dict[tuple[str, int], int]


class Emulator:
    def __init__(self, image: Image | None = None, allow_write: bool = True, fail_rate: float = 0.0):
        self.image: Image = dict(image or {})
        self.allow_write = allow_write
        self.fail_rate = fail_rate
        self.stats = {"ok": 0, "timeout": 0}
        self.poll_rules = []
        self.poll_running = False
        self.poll_revision = 0
        self.poll_boot = random.getrandbits(32)
        self.poll_sequence = 0
        self.poll_history = deque(maxlen=32)
        self.poll_next = 0
        self.paused = False
        self.started = time.monotonic()

    def _poll_tick(self, now: float | None = None):
        now = time.monotonic() if now is None else now
        if not self.poll_running or self.paused or not self.poll_rules:
            return
        for offset in range(len(self.poll_rules)):
            index = (self.poll_next + offset) % len(self.poll_rules)
            rule = self.poll_rules[index]
            if now < rule["due"]:
                continue
            addr, mem = rule["cursor"], rule["mem"]
            if addr == rule["start"]:
                rule["next_cycle"] = now + rule["interval_ms"] / 1000
            rule["cursor"] = addr + 1 if addr < rule["end"] else rule["start"]
            rule["due"] = now if addr < rule["end"] else rule["next_cycle"]
            self.poll_next = (index + 1) % len(self.poll_rules)
            self.poll_sequence += 1
            self.poll_history.append({"seq": self.poll_sequence,
                                      "uptime_ms": int((now - self.started) * 1000),
                                      "revision": self.poll_revision, "mem": mem, "addr": addr,
                                      "value": self.get(mem, addr)})
            return

    def _read_fields(self, mem, addr, value):
        frame = build_read(mem, addr)
        reply = read_reply(frame, value) if value is not None else b""
        return (f"mem={mem} addr=0x{addr:03X} valid={int(value is not None)} "
                f"value=0x{(value if value is not None else 0):02X} "
                f"check={'ok' if value is not None else 'timeout'} "
                f"tx={frame.hex().upper()} rx={reply.hex().upper()} attempts=1 ms=0")

    def _poll_command(self, args):
        action = args[0]
        if action == "list" and len(args) == 1:
            rules = [f"p mem={r['mem']} start=0x{r['start']:03X} end=0x{r['end']:03X} "
                     f"interval_ms={r['interval_ms']}" for r in self.poll_rules]
            return rules + [f"ok poll running={int(self.poll_running)} revision={self.poll_revision} "
                            f"boot={self.poll_boot} seq={self.poll_sequence} capacity=32 history=32"]
        if action in ("start", "stop", "clear") and len(args) == 1:
            self.poll_running = action == "start"
            if action == "clear":
                self.poll_rules.clear()
                self.poll_revision += 1
            return [f"ok poll {action}"]
        if action in ("set", "remove") and len(args) == (5 if action == "set" else 4):
            mem, start, end = parse_mem(args[1]), parse_num(args[2]), parse_num(args[3])
            if not 0 <= start <= end <= MAX_ADDRESS:
                return ["err poll invalid range"]
            matching = next((r for r in self.poll_rules if
                             (r["mem"], r["start"], r["end"]) == (mem, start, end)), None)
            if action == "remove":
                if matching is None:
                    return ["err poll remove"]
                self.poll_rules.remove(matching)
            else:
                interval = parse_num(args[4])
                if not 100 <= interval <= 86400000:
                    return ["err poll invalid interval"]
                if matching is None:
                    if len(self.poll_rules) >= 32 or any(
                            r["mem"] == mem and start <= r["end"] and end >= r["start"] for r in self.poll_rules):
                        return ["err poll overlapping rule or plan full"]
                    matching = {}
                    self.poll_rules.append(matching)
                now = time.monotonic()
                matching.update(mem=mem, start=start, end=end, interval_ms=interval,
                                cursor=start, due=now, next_cycle=now)
            self.poll_revision += 1
            return [f"ok poll {action}"]
        if action == "events" and len(args) == 2:
            since = parse_num(args[1])
            if not 0 <= since <= 0xFFFFFFFF:
                return ["err poll invalid sequence"]
            oldest = self.poll_history[0]["seq"] if self.poll_history else self.poll_sequence + 1
            lines = [f"s seq={s['seq']} uptime_ms={s['uptime_ms']} revision={s['revision']} " +
                     self._read_fields(s["mem"], s["addr"], s["value"])
                     for s in self.poll_history if s["seq"] > since]
            return lines + [f"ok events boot={self.poll_boot} latest={self.poll_sequence} "
                            f"oldest={oldest} lost={max(0, oldest - 1 - since)} "
                            f"uptime_ms={int((time.monotonic() - self.started) * 1000)}"]
        return ["err malformed poll command"]

    async def _poll_loop(self):
        while True:
            self._poll_tick()
            await asyncio.sleep(0.02)

    def get(self, mem: str, addr: int) -> int | None:
        if self.fail_rate and random.random() < self.fail_rate:
            self.stats["timeout"] += 1
            return None
        self.stats["ok"] += 1
        return self.image.get((mem, addr), 0)

    def handle(self, line: str) -> list[str]:
        argv = line.split()
        if not argv:
            return []
        cmd, args = argv[0], argv[1:]
        try:
            if cmd == "poll":
                return self._poll_command(args)
            if cmd == "help":
                return ["# emulator: r i d w x info pause resume monitor", "ok help"]
            if cmd == "info":
                return [f"ok info queue=0 ok={self.stats['ok']} timeout={self.stats['timeout']} bad=0 dropped=0 "
                        f"paused={int(self.paused)} echo=emulated write={int(self.allow_write)} monitor=0"]
            if cmd in ("pause", "resume"):
                self.paused = cmd == "pause"
                return [f"ok {cmd}"]
            if cmd == "monitor":
                return [f"ok monitor {args[0]}"]
            if cmd in ("r", "i"):
                mem, addr = parse_mem(args[0]), parse_num(args[1])
                v = self.get(mem, addr)
                if cmd == "i":
                    return ["ok i " + self._read_fields(mem, addr, v)]
                if v is None:
                    return [f"err r {mem} 0x{addr:03X} timeout"]
                return [f"ok r {mem} 0x{addr:03X} 0x{v:02X} ok"]
            if cmd == "d":
                mem, lo, hi = parse_mem(args[0]), parse_num(args[1]), parse_num(args[2])
                out = []
                for a in range(lo, hi + 1):
                    v = self.get(mem, a)
                    out.append(f"v {mem} 0x{a:03X} " + ("--" if v is None else f"0x{v:02X}"))
                return out + [f"ok d {mem} done"]
            if cmd == "w":
                if not self.allow_write:
                    return ["err writes disabled (lab_server.allow_write)"]
                mem, addr, val = parse_mem(args[0]), parse_num(args[1]), parse_num(args[2])
                self.image[mem, addr] = val
                return [f"ok w {mem} 0x{addr:03X} 0x{val:02X} reply={addr & 0xFF:02X}{val:02X} ok"]
            if cmd == "x":
                frame = bytes.fromhex(args[0])
                if len(frame) != 2 or int(args[1]) != 2:
                    return ["err raw read refused (invalid read frame)"]
                mem = EEPROM if frame[0] & 0x20 else RAM
                addr = ((frame[0] & 0x1F) << 8) | frame[1]
                if frame == build_read(mem, addr):
                    value = self.get(mem, addr)
                    if value is None:
                        return ["err x reply= len=0 timeout"]
                    reply = read_reply(frame, value)
                    return [f"ok x reply={reply.hex().upper()} len={len(reply)}"]
                return ["err raw read refused (invalid read frame)"]
        except (IndexError, ValueError):
            pass
        return ["err unknown or malformed command; type 'help'"]

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        writer.write(f"ok palazzetti lab emulator, writes {'allowed' if self.allow_write else 'disabled'}\n".encode())
        while line := await reader.readline():
            for out in self.handle(line.decode("ascii", "replace").strip()):
                writer.write(out.encode() + b"\n")
            await writer.drain()
        writer.close()

    async def serve(self, host: str = "127.0.0.1", port: int = 6638):
        server = await asyncio.start_server(self._client, host, port)
        async with asyncio.TaskGroup() as group:
            group.create_task(self._poll_loop())
            async with server:
                await server.serve_forever()

    def start_in_thread(self, host: str = "127.0.0.1", port: int = 0) -> int:
        """Start in a daemon thread (tests). Returns the bound port."""
        import threading

        ready = threading.Event()
        bound = {}

        def run():
            async def main():
                server = await asyncio.start_server(self._client, host, port)
                bound["port"] = server.sockets[0].getsockname()[1]
                ready.set()
                async with asyncio.TaskGroup() as group:
                    group.create_task(self._poll_loop())
                    async with server:
                        await server.serve_forever()

            asyncio.run(main())

        threading.Thread(target=run, daemon=True).start()
        ready.wait(5)
        return bound["port"]
