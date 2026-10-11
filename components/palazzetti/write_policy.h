#pragma once

#include <vector>

#include "micronova.h"

namespace esphome::palazzetti {

struct WriteRule {
  micronova::Memory memory;
  uint16_t address;
  uint8_t minimum;
  uint8_t maximum;
};

class WritePolicy {
 public:
  void add_rule(micronova::Memory memory, uint16_t address, uint8_t minimum, uint8_t maximum) {
    this->rules_.push_back({memory, address, minimum, maximum});
  }
  void set_enabled(bool enabled) {
    this->enabled_ = enabled;
    if (!enabled)
      this->eeprom_enabled_ = false;
  }
  void set_eeprom_enabled(bool enabled) { this->eeprom_enabled_ = enabled && this->enabled_; }
  bool enabled() const { return this->enabled_; }
  bool eeprom_enabled() const { return this->eeprom_enabled_; }
  size_t rule_count() const { return this->rules_.size(); }
  bool allows(micronova::Memory memory, uint16_t address, uint8_t value) const {
    if (!this->enabled_ || (memory == micronova::Memory::EEPROM && !this->eeprom_enabled_))
      return false;
    for (const auto &rule : this->rules_)
      if (rule.memory == memory && rule.address == address && value >= rule.minimum && value <= rule.maximum)
        return true;
    return false;
  }

 protected:
  bool enabled_{false};
  bool eeprom_enabled_{false};
  std::vector<WriteRule> rules_;
};

}  // namespace esphome::palazzetti
