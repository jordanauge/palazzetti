"""Fake lab server over a memory image: lets the tooling (and an agent) be exercised offline."""

import asyncio
import random

from .codec import EEPROM, RAM, build_read, parse_mem, parse_num, read_reply

Image = dict[tuple[str, int], int]


class Emulator:
    def __init__(self, image: Image | None = None, allow_write: bool = True, fail_rate: float = 0.0):
        self.image: Image = dict(image or {})
        self.allow_write = allow_write
        self.fail_rate = fail_rate
        self.stats = {"ok": 0, "timeout": 0}

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
            if cmd == "help":
                return ["# emulator: r i d w x info pause resume monitor", "ok help"]
            if cmd == "info":
                return [f"ok info queue=0 ok={self.stats['ok']} timeout={self.stats['timeout']} bad=0 dropped=0 "
                        f"paused=0 echo=emulated write={int(self.allow_write)} monitor=0"]
            if cmd in ("pause", "resume"):
                return [f"ok {cmd}"]
            if cmd == "monitor":
                return [f"ok monitor {args[0]}"]
            if cmd in ("r", "i"):
                mem, addr = parse_mem(args[0]), parse_num(args[1])
                v = self.get(mem, addr)
                if cmd == "i":
                    frame = build_read(mem, addr)
                    reply = read_reply(frame, v) if v is not None else b""
                    return [f"ok i mem={mem} addr=0x{addr:03X} valid={int(v is not None)} "
                            f"value=0x{(v if v is not None else 0):02X} check={'ok' if v is not None else 'timeout'} "
                            f"tx={frame.hex().upper()} rx={reply.hex().upper()} attempts=1 ms=0"]
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
                async with server:
                    await server.serve_forever()

            asyncio.run(main())

        threading.Thread(target=run, daemon=True).start()
        ready.wait(5)
        return bound["port"]
