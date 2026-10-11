import pytest

from plz import codec


def test_read_frames():
    assert codec.build_read("ram", 0x21) == bytes([0x00, 0x21])
    assert codec.build_read("eeprom", 0x7D) == bytes([0x20, 0x7D])
    assert codec.build_read("ram", 0x1F9) == bytes([0x01, 0xF9])


def test_write_frames_match_stufapellet_on_off():
    assert codec.build_write("ram", 0x21, 0x01).hex() == "802101a2"
    assert codec.build_write("ram", 0x21, 0x06).hex() == "802106a7"
    assert codec.build_write("eeprom", 0x7D, 0x14)[0] == 0xA0


def test_checksum_is_masked_to_8_bits():
    frame = codec.build_read("ram", 0xF9)
    reply = codec.read_reply(frame, 0x1A)
    assert reply == bytes([(0xF9 + 0x1A) & 0xFF, 0x1A])
    assert codec.check_read_reply(frame, reply) == "ok"
    assert codec.check_read_reply(frame, bytes([0x00, 0x1A])) == "bad-checksum"


def test_eeprom_reply_checksum_includes_header():
    frame = codec.build_read("eeprom", 0x10)
    assert codec.read_reply(frame, 0x05)[0] == 0x20 + 0x10 + 0x05


def test_bcd():
    assert codec.bcd_to_int(0x59) == 59
    assert codec.int_to_bcd(23) == 0x23


def test_parse_target():
    assert codec.parse_target("ram:0x00-0xFF") == ("ram", 0, 255)
    assert codec.parse_target("e:0x7D") == ("eeprom", 0x7D, 0x7D)
    with pytest.raises(ValueError):
        codec.parse_target("0x21")
    with pytest.raises(ValueError):
        codec.parse_mem("flash")
