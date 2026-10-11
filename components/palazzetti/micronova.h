#pragma once
// Micronova serial protocol, used by older Palazzetti stoves (incl. the Ecofire Lara) and many other brands.
// Newer Palazzetti stoves with a Fumis board use a different protocol, not implemented (see docs/boards.md).
// Pure functions, no ESPHome dependency: compiled on the host by tests/test_micronova.cpp.
// See docs/protocol.md.

#include <cstddef>
#include <cstdint>

namespace micronova {

enum class Memory : uint8_t { RAM = 0, EEPROM = 1 };

static const uint8_t READ_RAM = 0x00;
static const uint8_t READ_EEPROM = 0x20;
static const uint8_t WRITE_RAM = 0x80;
static const uint8_t WRITE_EEPROM = 0xA0;
static const uint16_t MAX_ADDRESS = 0x1FFF;  // 5 high bits are carried in the header

static const size_t READ_FRAME_LEN = 2;
static const size_t WRITE_FRAME_LEN = 4;
static const size_t REPLY_LEN = 2;

enum class ReplyCheck : uint8_t {
  OK,              // checksum == header + addr + value
  OK_NO_HEADER,    // checksum == addr + value (only distinguishable when header != 0)
  BAD_CHECKSUM,
  VALUE_MISMATCH,  // write reply does not carry the written value
};

inline uint8_t header(Memory mem, bool write, uint16_t addr) {
  uint8_t base = write ? (mem == Memory::EEPROM ? WRITE_EEPROM : WRITE_RAM)
                       : (mem == Memory::EEPROM ? READ_EEPROM : READ_RAM);
  return base | static_cast<uint8_t>((addr >> 8) & 0x1F);
}

inline uint8_t checksum(uint8_t hdr, uint8_t addr_lo, uint8_t value) {
  return static_cast<uint8_t>(hdr + addr_lo + value);
}

inline size_t build_read(uint8_t *out, Memory mem, uint16_t addr) {
  out[0] = header(mem, false, addr);
  out[1] = static_cast<uint8_t>(addr & 0xFF);
  return READ_FRAME_LEN;
}

inline size_t build_write(uint8_t *out, Memory mem, uint16_t addr, uint8_t value) {
  out[0] = header(mem, true, addr);
  out[1] = static_cast<uint8_t>(addr & 0xFF);
  out[2] = value;
  out[3] = checksum(out[0], out[1], value);
  return WRITE_FRAME_LEN;
}

// Read reply is [checksum, value].
inline ReplyCheck check_read_reply(const uint8_t *frame, const uint8_t *reply) {
  if (reply[0] == checksum(frame[0], frame[1], reply[1]))
    return ReplyCheck::OK;
  if (reply[0] == checksum(0, frame[1], reply[1]))
    return ReplyCheck::OK_NO_HEADER;
  return ReplyCheck::BAD_CHECKSUM;
}

// Write reply has been reported both as [addr, value] and [checksum, value]: accept either.
inline ReplyCheck check_write_reply(const uint8_t *frame, const uint8_t *reply) {
  if (reply[1] != frame[2])
    return ReplyCheck::VALUE_MISMATCH;
  if (reply[0] == frame[1] || reply[0] == frame[3])
    return ReplyCheck::OK;
  if (reply[0] == checksum(0, frame[1], frame[2]))
    return ReplyCheck::OK_NO_HEADER;
  return ReplyCheck::BAD_CHECKSUM;
}

inline bool reply_ok(ReplyCheck c) { return c == ReplyCheck::OK || c == ReplyCheck::OK_NO_HEADER; }

inline const char *reply_check_str(ReplyCheck c) {
  switch (c) {
    case ReplyCheck::OK:
      return "ok";
    case ReplyCheck::OK_NO_HEADER:
      return "ok-noheader";
    case ReplyCheck::BAD_CHECKSUM:
      return "bad-checksum";
    default:
      return "value-mismatch";
  }
}

inline uint8_t bcd_to_int(uint8_t v) { return static_cast<uint8_t>((v >> 4) * 10 + (v & 0x0F)); }
inline uint8_t int_to_bcd(uint8_t v) { return static_cast<uint8_t>(((v / 10) << 4) | (v % 10)); }

}  // namespace micronova
