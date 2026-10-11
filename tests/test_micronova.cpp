// Host test of the Micronova codec: make test-cpp
#include "micronova.h"
#include "write_policy.h"

#include <cstdio>

using namespace micronova;

static int failures = 0;
#define CHECK(c)                                              \
  do {                                                        \
    if (!(c)) {                                               \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); \
      failures++;                                             \
    }                                                         \
  } while (0)

int main() {
  uint8_t f[4];

  CHECK(build_read(f, Memory::RAM, 0x21) == 2 && f[0] == 0x00 && f[1] == 0x21);
  CHECK(build_read(f, Memory::EEPROM, 0x17D) == 2 && f[0] == 0x21 && f[1] == 0x7D);

  // StufaPellet on/off frames
  build_write(f, Memory::RAM, 0x21, 0x01);
  CHECK(f[0] == 0x80 && f[1] == 0x21 && f[2] == 0x01 && f[3] == 0xA2);
  build_write(f, Memory::RAM, 0x21, 0x06);
  CHECK(f[3] == 0xA7);
  build_write(f, Memory::EEPROM, 0x7D, 0x14);
  CHECK(f[0] == 0xA0);

  // Checksum wraps at 8 bits (the legacy RCSUM bug did not)
  build_read(f, Memory::RAM, 0xF9);
  const uint8_t ok[2] = {0x13, 0x1A};
  CHECK(check_read_reply(f, ok) == ReplyCheck::OK);
  const uint8_t bad[2] = {0x00, 0x1A};
  CHECK(check_read_reply(f, bad) == ReplyCheck::BAD_CHECKSUM);

  build_read(f, Memory::EEPROM, 0x10);
  const uint8_t noheader[2] = {0x15, 0x05};
  CHECK(check_read_reply(f, noheader) == ReplyCheck::OK_NO_HEADER);

  build_write(f, Memory::RAM, 0x30, 0x55);
  const uint8_t echo_addr[2] = {0x30, 0x55}, echo_csum[2] = {f[3], 0x55}, wrong[2] = {0x30, 0x54};
  CHECK(check_write_reply(f, echo_addr) == ReplyCheck::OK);
  CHECK(check_write_reply(f, echo_csum) == ReplyCheck::OK);
  CHECK(check_write_reply(f, wrong) == ReplyCheck::VALUE_MISMATCH);

  CHECK(bcd_to_int(0x59) == 59 && int_to_bcd(23) == 0x23);

  esphome::palazzetti::WritePolicy policy;
  policy.add_rule(Memory::RAM, 0x65, 0, 4);
  policy.add_rule(Memory::EEPROM, 78, 10, 30);
  CHECK(!policy.allows(Memory::RAM, 0x65, 3));
  policy.set_eeprom_enabled(true);
  CHECK(!policy.eeprom_enabled());
  policy.set_enabled(true);
  CHECK(policy.allows(Memory::RAM, 0x65, 3));
  CHECK(!policy.allows(Memory::RAM, 0x65, 5));
  CHECK(!policy.allows(Memory::RAM, 0x66, 3));
  CHECK(!policy.allows(Memory::EEPROM, 78, 26));
  policy.set_eeprom_enabled(true);
  CHECK(policy.allows(Memory::EEPROM, 78, 26));
  CHECK(!policy.allows(Memory::EEPROM, 78, 31));
  CHECK(!policy.allows(Memory::RAM, 78, 26));
  policy.set_enabled(false);
  CHECK(!policy.eeprom_enabled());
  CHECK(!policy.allows(Memory::RAM, 0x65, 3));
  policy.set_enabled(true);
  CHECK(!policy.allows(Memory::EEPROM, 78, 26));

  std::printf(failures ? "%d failure(s)\n" : "all micronova tests passed\n", failures);
  return failures ? 1 : 0;
}
