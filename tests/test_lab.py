import lzma

import pytest

from plz import analyze, legacy, session
from plz.client import LabClient, LabError
from plz.emulator import Emulator


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("PLZ_SESSIONS", str(tmp_path))
    return tmp_path


def test_session_roundtrip(sessions):
    with session.Session("s") as s:
        s.scan("ram", 0x10, [1, None, 3], t=1)
        s.mark("stove on", t=2)
        s.write("ram", 0x11, 7, t=3)
    evs = list(session.events("s"))
    assert [e["ev"] for e in evs] == ["scan", "mark", "write"]
    assert list(session.samples(evs)) == [(1, "ram", 0x10, 1), (1, "ram", 0x12, 3), (3, "ram", 0x11, 7)]


def test_inspect_retains_raw_evidence_and_excludes_failed_value(sessions):
    emulator = Emulator({("ram", 0xF9): 0x1A}, allow_write=False)
    port = emulator.start_in_thread()
    with LabClient("127.0.0.1", port) as client:
        result = client.inspect("ram", 0xF9)
        assert result == {
            "mem": "ram", "addr": 0xF9, "value": 0x1A, "valid": True,
            "check": "ok", "tx": "00F9", "rx": "131A", "attempts": 1, "elapsed_ms": 0,
        }
        assert client.raw(bytes.fromhex("00F9"), 2) == bytes.fromhex("131A")
        with pytest.raises(LabError, match="refused"):
            client.raw(bytes.fromhex("802101A2"), 2)
        emulator.fail_rate = 1.0
        failed = client.inspect("ram", 0xF9)
        assert failed["value"] is None
        assert failed["valid"] is False and failed["check"] == "timeout"
        assert failed["rx"] == ""
        with pytest.raises(LabError, match="timeout"):
            client.raw(bytes.fromhex("00F9"), 2)
    with session.Session("inspect") as log:
        log.log("read", **result)
        log.log("read_failed", **failed)
    observed = list(session.samples(session.events("inspect")))
    assert len(observed) == 1
    assert observed[0][1:] == ("ram", 249, 26)


def test_inspect_cli_logs_failed_reads(sessions, capsys):
    from plz.cli import main

    port = Emulator(fail_rate=1).start_in_thread()
    main(["--host", "127.0.0.1", "--port", str(port), "--session", "cli", "inspect", "ram", "0xF9"])
    assert '"valid": false' in capsys.readouterr().out
    events = list(session.events("cli"))
    assert events[0]["ev"] == "read_failed" and events[0]["value"] is None
    assert list(session.samples(events)) == []


def test_legacy_import_ignores_flag(sessions, tmp_path):
    dump = tmp_path / "d.txt.xz"
    with lzma.open(dump, "wt") as f:
        f.write("100 1 0 5\n100 0 1 255\n101 1 0 6\n101 1 1 254\n")
    with session.Session("imp") as s:
        assert legacy.import_dump(dump, s) == (2, 4)
    scans = [e["values"] for e in session.events("imp")]
    assert scans == [[5, 255], [6, 254]]


def _states(sessions):
    # 0xF9 is the state, 0x42 follows it, 0x50 is constant, 0x60 is noise
    with session.Session("a") as s:
        for i in range(40):
            on = i >= 20
            if i == 20:
                s.mark("switched on", t=i + 0.5)
            s.scan("ram", 0x42, [200 if on else 20], t=i)
            s.scan("ram", 0x50, [9], t=i)
            s.scan("ram", 0x60, [i % 7], t=i)
            s.scan("ram", 0xF9, [0x4B if on else 0x1A], t=i)
    return list(session.events("a"))


def test_analyze(sessions):
    evs = _states(sessions)
    st = analyze.stats(evs)
    assert st["ram", 0x50].kind == "constant"
    assert st["ram", 0xF9].kind == "binary"
    assert st["ram", 0x60].kind == "noisy"
    assert analyze.timeline(evs, ("ram", 0xF9)) == [(0, 0x1A), (20, 0x4B)]
    top = analyze.correlated(evs, ("ram", 0xF9))
    assert top[0][0] == ("ram", 0x42) and top[0][1] > 0.9
    assert all(k != ("ram", 0x50) for k, *_ in top)
    report = analyze.report(evs, ("ram", 0xF9))
    assert "switched on" in report


def test_emulator_client_roundtrip():
    emu = Emulator({("ram", 0xF9): 0x1A, ("eeprom", 0x7D): 20})
    port = emu.start_in_thread()
    with LabClient("127.0.0.1", port, timeout=5) as c:
        assert c.read("ram", 0xF9) == 0x1A
        assert c.read("e", 0x7D) == 20
        c.write("ram", 0x30, 0x55)
        assert c.read("ram", 0x30) == 0x55
        assert list(c.dump("ram", 0xF8, 0xF9)) == [(0xF8, 0), (0xF9, 0x1A)]
        assert c.raw(bytes([0x00, 0xF9]), 2) == bytes([0x13, 0x1A])
        assert c.info()["write"] == "1"
        assert c.command("help")[-1] == "ok help"


def test_emulator_read_only():
    port = Emulator(allow_write=False).start_in_thread()
    with LabClient("127.0.0.1", port, timeout=5) as c:
        with pytest.raises(LabError):
            c.write("ram", 0x21, 1)
