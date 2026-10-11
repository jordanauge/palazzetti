import yaml
import pytest

from plz import maps


def test_all_profiles_load():
    names = maps.profiles()
    assert "palazzetti-ecofire-lara" in names
    for name in names:
        p = maps.load(name)
        ids = [f["id"] for f in p["fields"]]
        assert len(ids) == len(set(ids)), name
        for f in p["fields"]:
            assert f["status"] in maps.STATUSES
            for k, v in (f.get("values") or {}).items():
                assert isinstance(v, str), f"{name}:{f['id']} value {k} is {v!r} (quote YAML on/off)"


def test_extends_merges_by_id():
    common = maps.by_key(maps.load("micronova-common"))
    p937 = maps.load("micronova-p937")
    ids = {f["id"] for f in p937["fields"]}
    assert {f["id"] for f in common.values()} <= ids


def test_lara_state_register():
    lara = maps.by_key(maps.load("palazzetti-ecofire-lara"))
    state = lara["ram", 0xF9]
    assert state["values"][0x1A] == "off"
    assert lara["ram", 0x21]["status"] == "refuted"


def test_render_markdown():
    md = maps.render_markdown(maps.profiles())
    assert "0x0F9" in md or "0xF9" in md
    assert "False" not in md


def test_gen_esphome_is_valid_yaml():
    out = yaml.safe_load(maps.gen_esphome("palazzetti-ecofire-lara"))
    entities = [e for name, platform in out.items() if name != "palazzetti" for e in platform]
    assert entities
    assert all(e["palazzetti_id"] == "stove" for e in entities)
    assert out["palazzetti"]["write_allowlist"] == []
    assert "number" not in out
    assert any(e["id"] == "chrono_programs_program_1_start" for e in entities)
    assert all("/" not in e["name"] for e in entities)


@pytest.mark.parametrize("override", [
    {"write_sources": []}, {"status": "hypothesis"}, {"status": "reported"},
    {"raw_min": -1}, {"raw_max": 256}, {"raw_min": 6, "raw_max": 5},
    {"count": 2}, {"encoding": "uint16_le"}, {"encoding": "bcd"}, {"scale": 0},
    {"access": "r"}, {"write_status": "likely"}, {"raw_min": 1.5}, {"raw_min": True},
    {"values": {9: "outside range"}},
])
def test_confirmed_writes_require_separate_evidence_and_byte_bounds(override):
    field = {"id": "power", "addr": 0x76, "mem": "eeprom", "access": "rw",
             "status": "observed", "write_status": "confirmed", "write_sources": ["panel-trace"],
             "raw_min": 1, "raw_max": 5}
    with pytest.raises(ValueError):
        maps._norm({**field, **override})


def test_confirmed_write_generation(monkeypatch):
    field = maps._norm({"id": "target", "addr": 0x76, "mem": "eeprom", "access": "rw",
                        "status": "observed", "write_status": "confirmed", "write_sources": ["bench"],
                        "raw_min": 10, "raw_max": 50, "scale": 0.5, "offset": 2})
    monkeypatch.setattr(maps, "load", lambda _: {"fields": [field]})
    out = yaml.safe_load(maps.gen_esphome("fixture"))
    assert out["palazzetti"]["write_allowlist"] == [
        {"memory": "eeprom", "address": 0x76, "min_value": 10, "max_value": 50, "evidence": "bench"}]
    entity = out["number"][0]
    assert (entity["min_value"], entity["max_value"], entity["multiply"], entity["offset"]) == (7, 27, 0.5, 2)
    field["values"] = {10: "low", 30: "medium", 50: "high"}
    out = yaml.safe_load(maps.gen_esphome("fixture"))
    assert [(rule["min_value"], rule["max_value"]) for rule in out["palazzetti"]["write_allowlist"]] == [
        (10, 10), (30, 30), (50, 50)]
