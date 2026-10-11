import hashlib
import json
import time
from types import SimpleNamespace

import pytest

from plz import acquisition, session
from plz.cli import main
from plz.client import LabClient, LabError
from plz.emulator import Emulator


@pytest.fixture
def logs(tmp_path, monkeypatch):
    monkeypatch.setenv("PLZ_SESSIONS", str(tmp_path / "sessions"))
    return tmp_path


def test_poll_plan_live_edits_and_autonomous_results(logs):
    emu = Emulator({("ram", 249): 26})
    port = emu.start_in_thread()
    with LabClient("127.0.0.1", port) as client:
        assert client.poll_list()["rules"] == []
        client.poll_set("ram", 249, 249, 100)
        with pytest.raises(LabError, match="overlapping"):
            client.poll_set("ram", 248, 249, 100)
        with pytest.raises(LabError, match="interval"):
            client.poll_set("ram", 249, 249, 99)
        client.poll_control("start")
    # The ESP/emulator keeps reading with no CLI connection.
    deadline = time.monotonic() + 2
    while not emu.poll_history and time.monotonic() < deadline:
        time.sleep(0.02)
    assert emu.poll_history
    with LabClient("127.0.0.1", port) as client:
        batch = client.poll_events()
        assert batch["samples"][0]["value"] == 26
        assert batch["samples"][0]["tx"] == "00F9"
        client.poll_set("ram", 249, 249, 1000)
        assert client.poll_list()["rules"][0]["interval_ms"] == 1000
        client.poll_control("stop")
        client.poll_remove("ram", 249, 249)
        assert not client.poll_list()["rules"]


def test_retention_reports_gaps_and_failed_samples():
    emu = Emulator(fail_rate=1)
    emu.handle("poll set ram 0 40 100")
    emu.handle("poll start")
    now = time.monotonic()
    for i in range(40):
        emu._poll_tick(now + i * 0.02)
    assert len(emu.poll_history) == 32
    port = emu.start_in_thread()
    with LabClient("127.0.0.1", port) as client:
        client.poll_control("stop")
        batch = client.poll_events()
        assert batch["lost"] >= 8
        assert len(batch["samples"]) == 32
        assert all(not result["valid"] and result["value"] is None for result in batch["samples"])
        assert client.poll_events(batch["latest"])["samples"] == []


def test_plan_cli_save_load_record(logs, capsys):
    emu = Emulator()
    port = emu.start_in_thread()
    args = ["--host", "127.0.0.1", "--port", str(port), "--session", "live"]
    main(args + ["poll", "set", "ram:0xF9", "--interval-ms", "100"])
    plan_file = logs / "plan.json"
    main(args + ["poll", "save", str(plan_file)])
    main(args + ["poll", "clear"])
    main(args + ["poll", "load", str(plan_file), "--start"])
    main(args + ["poll", "record", "-i", "0.05", "-d", "0.3"])
    logged = list(session.events("live"))
    assert any(event["ev"] == "read" and event["addr"] == 249 for event in logged)
    assert emu.poll_running
    assert len(emu.poll_rules) == 1
    capsys.readouterr()


def test_backup_passes_complete_and_recoverable(logs):
    emu = Emulator({("eeprom", 0): 255, ("ram", 0): 26})
    port = emu.start_in_thread()
    destination = logs / "backup"
    with LabClient("127.0.0.1", port) as client, session.Session("backup") as log:
        client.poll_set("ram", 0xF9, 0xF9, 100)
        client.poll_control("start")
        result = acquisition.backup(client, log, [("eeprom", 0, 1), ("ram", 0, 0)], 3, 0, destination)
        assert client.poll_list()["running"] == 1
    assert result["complete"] and result["consistent"]
    assert len(result["bytes"]) == 3
    assert result["bytes"][0]["values"] == [255, 255, 255]
    for item in result["files"]:
        file = destination / item["path"]
        assert hashlib.sha256(file.read_bytes()).hexdigest() == item["sha256"]
        assert len(file.read_text().splitlines()) == 3
    assert json.loads((destination / "manifest.json").read_text())["consistent"]
    assert len(list(session.samples(session.events("backup")))) == 9


def test_backup_failed_reads_not_invented(logs, capsys):
    port = Emulator(fail_rate=1).start_in_thread()
    with pytest.raises(SystemExit) as failure:
        main(["--host", "127.0.0.1", "--port", str(port), "--session", "failed", "backup",
              "eeprom:0", "--gap", "0", "-o", str(logs / "failed")])
    assert failure.value.code == 2
    result = json.loads((logs / "failed" / "manifest.json").read_text())
    assert result["passes_finished"] and not result["complete"] and not result["consistent"]
    assert result["bytes"][0]["values"] == [None, None, None]
    assert not result["bytes"][0]["complete"]
    assert list(session.samples(session.events("failed"))) == []
    capsys.readouterr()


def test_backup_variations_retained_not_majority_vote(logs):
    emu = Emulator()
    original = emu.get

    def varying(mem, addr):
        emu.image[mem, addr] = emu.image.get((mem, addr), 0) + 1
        return original(mem, addr)

    emu.get = varying
    port = emu.start_in_thread()
    with LabClient("127.0.0.1", port) as client, session.Session("changes") as log:
        result = acquisition.backup(client, log, [("ram", 0, 0)], 3, 0, logs / "varying")
    assert result["bytes"][0]["values"] == [1, 2, 3]
    assert result["bytes"][0]["complete"] and not result["bytes"][0]["stable"]
    assert not result["consistent"]


def test_unknown_selection_keeps_uncertain_members(monkeypatch):
    monkeypatch.setattr(acquisition.maps, "load", lambda _: {"fields": [
        {"mem": "ram", "addr": 2, "status": "observed"},
        {"mem": "ram", "addr": 4, "status": "hypothesis", "count": 2},
        {"mem": "ram", "addr": 6, "status": "observed", "members": [
            {"byte_offset": 0}, {"byte_offset": 1, "status": "unknown"}]},
    ]})
    assert acquisition.unknown_ranges("fixture", [("ram", 0, 8)]) == [
        ("ram", 0, 1), ("ram", 3, 5), ("ram", 7, 8)]


@pytest.mark.parametrize("spec", ["ram:-1", "ram:3-2", "ram:0-0x2000", "flash:0"])
def test_invalid_backup_targets(spec):
    with pytest.raises(ValueError):
        acquisition.targets([spec])


def test_invalid_saved_plan():
    with pytest.raises(ValueError):
        acquisition.validate_plan({"rules": [{"mem": "ram", "start": 0, "end": 1, "interval_ms": 99}]})
    with pytest.raises(ValueError):
        acquisition.targets(["ram:0-2", "ram:2"])


def test_interrupted_backup_preserves_partial_pass_and_restores_polling(logs):
    emu = Emulator()
    port = emu.start_in_thread()
    with LabClient("127.0.0.1", port) as client, session.Session("partial") as log:
        client.poll_control("start")
        inspect = client.inspect

        def interrupted(mem, addr):
            if addr == 1:
                raise LabError("test transport failure")
            return inspect(mem, addr)

        client.inspect = interrupted
        with pytest.raises(LabError, match="transport"):
            acquisition.backup(client, log, [("ram", 0, 1)], 3, 0, logs / "partial")
        assert client.poll_list()["running"]
        assert client.info()["paused"] == "0"
    result = json.loads((logs / "partial" / "manifest.json").read_text())
    assert not result["passes_finished"] and not result["complete"]
    assert result["bytes"][0]["values"] == [0]
    assert result["bytes"][1]["values"] == []
    assert len(result["files"]) == 1


def test_poll_recorder_reports_gaps_and_reboots(logs, monkeypatch, capsys):
    from plz import cli

    ticks = iter([0, 0, 0.05, 0.2])
    monkeypatch.setattr(cli, "time", SimpleNamespace(
        monotonic=lambda: next(ticks), sleep=lambda _: None, time=time.time))
    batches = iter([
        {"boot": 1, "latest": 40, "lost": 8, "uptime_ms": 1000, "samples": [
            {"seq": 40, "uptime_ms": 900, "revision": 1, "mem": "ram", "addr": 249,
             "valid": True, "value": 26, "check": "ok", "tx": "00F9", "rx": "131A"}]},
        {"boot": 2, "latest": 1, "lost": 0, "uptime_ms": 100, "samples": [
            {"seq": 1, "uptime_ms": 50, "revision": 0, "mem": "ram", "addr": 249,
             "valid": False, "value": None, "check": "timeout", "tx": "00F9", "rx": ""}]},
    ])

    class FakeClient:
        def __enter__(self):
            self.batch = next(batches)
            return self

        def __exit__(self, *args):
            pass

        def poll_list(self):
            return {"boot": self.batch["boot"], "rules": []}

        def poll_events(self, cursor):
            assert cursor == 0  # reset after reboot, not previous boot's sequence 40
            return self.batch

    monkeypatch.setattr(cli, "_client", lambda _: FakeClient())
    main(["--session", "reboots", "poll", "record", "-d", "0.1"])
    records = list(session.events("reboots"))
    assert [record["ev"] for record in records] == ["poll_boot", "poll_gap", "read", "poll_boot", "read_failed"]
    assert records[1]["lost"] == 8
    assert records[2]["clock"] == "host-estimated"
    assert records[4]["boot"] == 2 and records[4]["value"] is None
    assert len(list(session.samples(records))) == 1
    assert "overwritten" in capsys.readouterr().err
