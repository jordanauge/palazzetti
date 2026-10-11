#pragma once

#include <vector>
#include "micronova.h"

namespace esphome::palazzetti {

struct CachedByte {
  micronova::Memory memory;
  uint16_t address;
  uint32_t updated_ms;
  bool valid;
  uint8_t value;
  const char *error;
};

class ReadCache {
 public:
  static constexpr size_t CAPACITY = 128;
  const CachedByte *find(micronova::Memory memory, uint16_t address) const {
    for (const auto &entry : this->entries_)
      if (entry.memory == memory && entry.address == address)
        return &entry;
    return nullptr;
  }
  void put(micronova::Memory memory, uint16_t address, uint32_t now, bool valid, uint8_t value,
           const char *error = nullptr) {
    for (auto &entry : this->entries_)
      if (entry.memory == memory && entry.address == address) {
        entry = {memory, address, now, valid, value, error};
        return;
      }
    if (this->entries_.size() == CAPACITY) {
      this->entries_[this->victim_] = {memory, address, now, valid, value, error};
      this->victim_ = (this->victim_ + 1) % CAPACITY;
    } else {
      this->entries_.push_back({memory, address, now, valid, value, error});
    }
  }

 protected:
  std::vector<CachedByte> entries_;
  size_t victim_{0};
};

}  // namespace esphome::palazzetti
