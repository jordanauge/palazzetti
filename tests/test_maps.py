import yaml
import json
import pytest
from pathlib import Path

from plz import maps

REFERENCES = Path(__file__).resolve().parents[1] / "docs/reference-mappings"


def reference(name):
    return maps.load(str(REFERENCES / f"{name}.yaml"))


def test_bridge_reference_corrections_do_not_promote_lara_addresses():
    bridge = {field["id"]: field for field in reference("palazzetti-connbox")["fields"]}
    assert bridge["board_model"]["addr"] == 0x6E
    assert bridge["feeder"]["addr"] == 0x0D
    assert bridge["feeder"]["scale"] == 0.1
    assert bridge["parameters"]["addr"] == 0
    assert bridge["parameters"]["count"] == 47
    lara = {field["id"]: field for field in maps.load("palazzetti-ecofire-lara")["fields"]}
    assert lara["board_model"]["addr"] == 0x0D
    assert lara["board_model"]["status"] == "unknown"
    assert lara["power_state"]["addr"] == 0xF9
    deployed = json.loads(maps.gen_device_map("palazzetti-ecofire-lara"))["maps"][0]["fields"]
    assert not any(field["id"] in ("board_model", "feeder", "parameters") for field in deployed)


def test_device_map_is_bounded_and_read_only():
    text = maps.gen_device_map("palazzetti-ecofire-lara")
    assert len(text.encode()) <= 8192
    data = json.loads(text)
    assert data["format"] == 1
    profile = data["maps"][0]
    assert profile["interval_ms"] == 15000
    assert 1 <= len(profile["fields"]) <= 48
    state = next(field for field in profile["fields"] if field["id"] == "power_state")
    assert state["addr"] == 0xF9 and state["values"]["26"] == "off"
    assert all(field["status"] in ("observed", "confirmed") for field in profile["fields"])
    assert not any(key in field for field in profile["fields"] for key in ("access", "write_status", "write_sources"))


def test_device_map_explicit_hypothesis_and_structure_members():
    data = json.loads(maps.gen_device_map("palazzetti-ecofire-lara",
                                        ["chrono_programs.program_1.start", "phase_step"], 300000))
    fields = data["maps"][0]["fields"]
    assert {field["id"] for field in fields} == {"chrono_programs.program_1.start", "phase_step"}
    assert all(field["status"] == "hypothesis" for field in fields)
    assert next(field for field in fields if field["id"].endswith(".start"))["addr"] == 0x3B


@pytest.mark.parametrize("interval", [0, 99, 86400001, True, 100.5])
def test_device_map_invalid_interval(interval):
    with pytest.raises(ValueError, match="interval"):
        maps.gen_device_map("palazzetti-ecofire-lara", interval_ms=interval)


def test_device_map_refuses_unlocated_and_raw_structures():
    with pytest.raises(ValueError, match="Unknown or unlocated"):
        maps.gen_device_map("palazzetti-ecofire-lara", ["service_ignition_time"])
    with pytest.raises(ValueError, match="Unknown or unlocated"):
        maps.gen_device_map("palazzetti-ecofire-lara", ["chrono_programs"])


@pytest.mark.parametrize("override", [{"encoding": "ascii"}, {"scale": True}, {"offset": float("inf")}])
def test_device_map_refuses_invalid_conversions(monkeypatch, override):
    monkeypatch.setattr(maps, "load", lambda _: {
        "profile": "fixture", "fields": [
            {"id": "field", "name": "Field", "mem": "ram", "addr": 0, "status": "observed", **override}
        ],
    })
    with pytest.raises(ValueError):
        maps.gen_device_map("fixture")


def test_all_profiles_load():
    names = maps.profiles()
    assert names == ["palazzetti-ecofire-lara"]
    for name in names:
        p = maps.load(name)
        ids = [f["id"] for f in p["fields"]]
        assert len(ids) == len(set(ids)), name
        for f in p["fields"]:
            assert f["status"] in maps.STATUSES
            for k, v in (f.get("values") or {}).items():
                assert isinstance(v, str), f"{name}:{f['id']} value {k} is {v!r} (quote YAML on/off)"


def test_extends_merges_by_id():
    common = maps.by_key(reference("micronova-common"))
    p937 = reference("micronova-p937")
    ids = {f["id"] for f in p937["fields"]}
    assert {f["id"] for f in common.values()} <= ids


def test_reference_notes_are_valid_but_not_deployable():
    paths = sorted(REFERENCES.glob("*.yaml"))
    assert len(paths) == 6
    for path in paths:
        assert maps.load(str(path))["reference_only"] is True
        for generator in (maps.gen_device_map, maps.gen_esphome):
            with pytest.raises(ValueError, match="reference-only"):
                generator(str(path))
        with pytest.raises(ValueError, match="reference-only"):
            maps.render_markdown([str(path)])


def test_unlocated_settings_never_generate_guessed_entities():
    p = maps.load("palazzetti-ecofire-lara")
    service = [f for f in p["unlocated"] if f["id"].startswith("service_")]
    assert len(service) == 35
    assert all("addr" not in f and f["memory_hint"] == "eeprom" for f in service)
    out = yaml.safe_load(maps.gen_esphome("palazzetti-ecofire-lara"))
    ids = {e["id"] for platform, entities in out.items() if platform != "palazzetti" for e in entities}
    assert not ids.intersection(f["id"] for f in p["unlocated"])
    assert out["palazzetti"]["write_allowlist"] == []
    f = next(f for f in p["fields"] if f["id"] == "target_temperature")
    assert f["evidence"][0]["method"] == "panel_change"
    assert "encoding" in f["evidence"][0]["supports"]


@pytest.mark.parametrize("override", [
    {"source": "missing"}, {"origin": "guessed"}, {"method": "correlated-ish"},
    {"supports": ["write_permission"]}, {"supports": []}, {"claim": ""},
])
def test_evidence_claims_are_validated(override):
    record = {"source": "source", "origin": "own", "method": "variation",
              "supports": ["meaning"], "claim": "Observed evolution, not proof."}
    with pytest.raises(ValueError):
        maps._validate_evidence({"id": "test", "evidence": [{**record, **override}]}, {"source": "fixture"})


def test_profile_override_does_not_inherit_inapplicable_evidence(tmp_path):
    parent = tmp_path / "parent.yaml"
    child = tmp_path / "child.yaml"
    parent.write_text(yaml.safe_dump({
        "profile": "parent", "sources": {"source": "fixture"},
        "fields": [{"id": "field", "addr": 1, "evidence": [{
            "source": "source", "origin": "external", "method": "source_table",
            "supports": ["address"], "claim": "Parent-board address only.",
        }]}],
    }))
    child.write_text(yaml.safe_dump({"profile": "child", "extends": str(parent),
                                    "fields": [{"id": "field", "addr": 2}]}))
    assert "evidence" not in maps.load(str(child))["fields"][0]


def test_reference_conflicts_and_representation_only_lara_credit():
    ridiculous = {f["id"]: f for f in reference("micronova-ridiculouslab")["fields"]}
    common = {f["id"]: f for f in reference("micronova-common")["fields"]}
    assert ridiculous["water_temperature"].get("scale", 1) == 1
    assert common["water_temperature"]["scale"] == 0.5
    assert not any(f["mem"] == "eeprom" for f in ridiculous.values())
    marina = reference("micronova-marina")
    assert len([f for f in marina["fields"] if f["addr"] == 0x7B]) == 2
    lara = maps.load("palazzetti-ecofire-lara")
    fumes = next(f for f in lara["fields"] if f["id"] == "fumes_temperature")
    external = [r for r in fumes["evidence"] if r["origin"] == "external"]
    assert external and all("address" not in r["supports"] for r in external)


def test_lara_state_register():
    lara = maps.by_key(maps.load("palazzetti-ecofire-lara"))
    state = lara["ram", 0xF9]
    assert state["values"][0x1A] == "off"
    assert lara["ram", 0x21]["status"] == "refuted"


def test_render_markdown():
    md = maps.render_markdown(maps.profiles())
    assert "0x0F9" in md or "0xF9" in md
    assert "False" not in md
    assert "Same parameter, different address" not in md
    assert "## Micronova" not in md


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
