import json
import re
from pathlib import Path

import pytest

from plz import maps, memory_html


def payload(page):
    return json.loads(re.search(r'<script id="map-data" type="application/json">(.*?)</script>',
                                page, re.S).group(1))


def test_render_lara_only_and_overlapping_fields():
    for memory in ("ram", "eeprom"):
        result = payload(memory_html.render(memory, maps.profiles()))
        assert result["memory"] == memory
        assert [p["id"] for p in result["profiles"]] == ["palazzetti-ecofire-lara"]
        assert 'id="profile"' not in memory_html.render(memory, maps.profiles())
    lara = payload(memory_html.render("ram", ["palazzetti-ecofire-lara"]))["profiles"][0]
    assert len([f for f in lara["fields"] if f["addr"] == 0x5A]) == 2


def test_atlas_rejects_multiple_maps_and_reference_notes():
    with pytest.raises(ValueError, match="exactly one"):
        memory_html.render("ram", maps.profiles() * 2)
    references = Path(__file__).resolve().parents[1] / "docs/reference-mappings"
    for path in references.glob("*.yaml"):
        with pytest.raises(ValueError, match="reference-only"):
            memory_html.render("ram", [str(path)])


def test_nested_members_and_distinct_conversion_offset():
    field = memory_html.region({
        "id": "program", "addr": 59, "count": 3, "mem": "eeprom",
        "status": "hypothesis", "sources": ["notes"], "category": "Clock & scheduling",
        "members": [{"id": "stop", "byte_offset": 1, "offset": 30, "scale": 10}],
    })
    member = field["members"][0]
    assert member["addr"] == 60
    assert member["offset"] == 30
    assert member["sources"] == ["notes"]
    assert member["status"] == "hypothesis"
    assert member["category"] == "Clock & scheduling"
    assert memory_html.field_width({"encoding": "uint16_le"}) == 2
    with pytest.raises(ValueError, match="outside"):
        memory_html.region({**field, "members": [{"id": "bad", "byte_offset": 3}]})
    with pytest.raises(ValueError, match="outside"):
        memory_html.region({"id": "bad", "addr": 0x1FFF, "count": 2})


def test_address_import_discards_failed_sentinel(tmp_path):
    (tmp_path / "addr-f9").write_text("2 false ff\n3 true 1a\n")
    (tmp_path / "addr-42").write_text("1 true 19\n")
    records = list(memory_html.address_events(tmp_path))
    assert [r["t"] for r in records] == [1, 2, 3]
    assert records[1]["values"] == [None]
    result = memory_html.capture("capture", records, "lara")
    assert result["bytes"]["ram:249"]["last"] == 0x1A
    assert result["bytes"]["ram:249"]["rejected"] == 1
    assert result["bytes"]["ram:249"]["n"] == 1
    (tmp_path / "addr-f9").write_text("ff\n")
    with pytest.raises(ValueError, match="expected timestamp"):
        list(memory_html.address_events(tmp_path))


def test_capture_statistics_history_and_no_write_evidence():
    records = [{"t": i, "ev": "scan", "mem": "ram", "start": 1, "values": [i % 2, None]}
               for i in range(1000)]
    records += [{"t": 1001, "ev": "write", "mem": "ram", "addr": 1, "value": 255}]
    result = memory_html.capture("capture", records, "lara")
    stat = result["bytes"]["ram:1"]
    assert (stat["n"], stat["changes"], stat["distinct"]) == (1000, 999, 2)
    assert stat["histogram"] == [(0, 500), (1, 500)]
    assert len(stat["points"]) <= 257
    assert stat["points"][-1] == [999, 1]
    assert result["bytes"]["ram:2"] == {"n": 0, "rejected": 1000}
    with pytest.raises(ValueError, match="chronological"):
        memory_html.capture("bad", reversed(records), "lara")


def test_embedded_data_cannot_close_script(monkeypatch):
    monkeypatch.setattr(maps, "load", lambda _: {
        "profile": "test", "title": "</script><script>alert(1)</script>",
        "sources": {}, "fields": [],
    })
    page = memory_html.render("ram", ["test"])
    assert "</script><script>alert(1)" not in page
    assert payload(page)["profiles"][0]["title"].startswith("</script>")


def test_generate_both_files(tmp_path):
    paths = memory_html.generate(tmp_path, ["palazzetti-ecofire-lara"], [], [],
                                 "palazzetti-ecofire-lara")
    assert [p.name for p in paths] == ["memory-ram.html", "memory-eeprom.html"]
    assert all(p.is_file() and 'id="field-list"' in p.read_text()
               and "<code>??</code>" not in p.read_text() for p in paths)
    eeprom = payload(paths[1].read_text())["profiles"][0]["fields"]
    chrono = next(f for f in eeprom if f["id"] == "chrono_programs")
    assert len(chrono["members"]) == 6
    assert chrono["members"][5]["addr"] == 74
    assert chrono["members"][0]["members"][2]["addr"] == 61


def test_recovered_members_keep_addresses_conversions_and_evidence():
    forum = maps.load(str(Path(__file__).resolve().parents[1] /
                          "docs/reference-mappings/micronova-forum.yaml"))
    fields = [memory_html.region(f) for f in forum["fields"] if f["mem"] == "eeprom"]
    technical = next(f for f in fields if f["id"] == "technical_parameters")
    assert len(technical["members"]) == 37
    assert 16 not in {f["addr"] for f in technical["members"]}
    pg05 = next(f for f in technical["members"] if f["id"] == "pg05")
    assert (pg05["addr"], pg05["scale"], pg05["offset"], pg05["status"]) == (5, 10, 250, "reported")
    assert pg05["category"] == "Service parameters"
    chrono = next(f for f in fields if f["id"] == "chrono")
    programs = [f for f in chrono["members"] if f["members"]]
    assert [p["addr"] for p in programs] == [77, 87, 97, 107]
    assert programs[-1]["members"][-1]["addr"] == 115
    assert programs[0]["members"][0]["unit"] == "min"
    lara = payload(memory_html.render("ram", ["palazzetti-ecofire-lara"]))["profiles"][0]
    by_id = {f["id"]: f for f in lara["fields"]}
    assert by_id["power_setting_ram_aux"]["addr"] == 0x47
    assert by_id["fan_setting_ram_aux"]["addr"] == 0x46
    assert by_id["board_model"]["status"] == "unknown"
    assert by_id["board_model"]["addr"] == 0x0D
    assert "connbox-69055a28" in by_id["board_model"]["sources"]
    assert by_id["midnight_0x61"]["status"] == "unknown"
    constants = by_id["constants_0x23"]
    assert len(constants["members"]) == 13
    assert all(f["status"] == "unknown" for f in constants["members"])


def test_public_atlas_excludes_private_captures(tmp_path):
    paths = memory_html.generate(tmp_path, maps.profiles(), [], [], "palazzetti-ecofire-lara")
    for path in paths:
        assert payload(path.read_text())["captures"] == []
    records = [{"t": 1, "ev": "read", "mem": "ram", "addr": 1, "value": 26}]
    sample = memory_html.capture("test", records, "palazzetti-ecofire-lara")
    assert payload(memory_html.render("eeprom", maps.profiles(), [sample]))["captures"] == []


def test_unlocated_inventory_is_separate_from_addressed_regions():
    p = payload(memory_html.render("eeprom", ["palazzetti-ecofire-lara"]))["profiles"][0]
    assert len([f for f in p["unlocated"] if f["id"].startswith("service_")]) == 35
    assert not {f["id"] for f in p["unlocated"]}.intersection(f["id"] for f in p["fields"])
    assert all("addr" not in f for f in p["unlocated"])
    assert next(f for f in p["fields"] if f["id"] == "target_temperature")["evidence"]


def test_pages_workflow_packages_only_public_html():
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[1]
    workflow = yaml.load((root / ".github/workflows/pages.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"push", "workflow_dispatch", "public"}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["deploy"]["if"] == "github.event.repository.private == false"
    build = workflow["jobs"]["build"]["steps"]
    generate = next(step["run"] for step in build if step.get("name") == "Generate public atlas without private captures")
    assert "--capture" not in generate and "--legacy-dir" not in generate
    assert "gen-html palazzetti-ecofire-lara -o docs" in generate
    assert "micronova-" not in generate and "palazzetti-connbox" not in generate
    assert "cp docs/index.html docs/memory-ram.html docs/memory-eeprom.html _site/" in generate
    assert "cp -r" not in generate
