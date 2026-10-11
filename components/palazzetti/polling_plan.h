#pragma once

#include <cstdint>
#include <vector>

#include "micronova.h"

namespace esphome::palazzetti {

struct PollRule {
  micronova::Memory memory;
  uint16_t start;
  uint16_t end;
  uint32_t interval_ms;
  uint16_t cursor;
  uint32_t due;
  uint32_t next_cycle;
};

class PollingPlan {
 public:
  static constexpr size_t CAPACITY = 32;
  static constexpr uint32_t MIN_INTERVAL = 100;
  static constexpr uint32_t MAX_INTERVAL = 86400000;

  bool set(micronova::Memory memory, uint16_t start, uint16_t end, uint32_t interval, uint32_t now) {
    if (start > end || end > micronova::MAX_ADDRESS || interval < MIN_INTERVAL || interval > MAX_INTERVAL)
      return false;
    for (auto &rule : this->rules_) {
      if (rule.memory == memory && rule.start == start && rule.end == end) {
        rule = {memory, start, end, interval, start, now, now};
        this->revision_++;
        return true;
      }
      if (rule.memory == memory && start <= rule.end && end >= rule.start)
        return false;
    }
    if (this->rules_.size() >= CAPACITY)
      return false;
    this->rules_.push_back({memory, start, end, interval, start, now, now});
    this->revision_++;
    return true;
  }
  bool remove(micronova::Memory memory, uint16_t start, uint16_t end) {
    for (auto it = this->rules_.begin(); it != this->rules_.end(); ++it)
      if (it->memory == memory && it->start == start && it->end == end) {
        this->rules_.erase(it);
        this->revision_++;
        return true;
      }
    return false;
  }
  void clear() {
    this->rules_.clear();
    this->revision_++;
  }
  void set_running(bool running) { this->running_ = running; }
  bool running() const { return this->running_; }
  uint32_t revision() const { return this->revision_; }
  const std::vector<PollRule> &rules() const { return this->rules_; }

  bool next(uint32_t now, micronova::Memory &memory, uint16_t &address) {
    if (!this->running_ || this->rules_.empty())
      return false;
    for (size_t n = 0; n < this->rules_.size(); n++) {
      size_t index = (this->next_rule_ + n) % this->rules_.size();
      auto &rule = this->rules_[index];
      if (static_cast<int32_t>(now - rule.due) < 0)
        continue;
      memory = rule.memory;
      address = rule.cursor;
      if (rule.cursor == rule.start)
        rule.next_cycle = now + rule.interval_ms;
      if (rule.cursor == rule.end) {
        rule.cursor = rule.start;
        rule.due = rule.next_cycle;
      } else {
        rule.cursor++;
        rule.due = now;
      }
      this->next_rule_ = (index + 1) % this->rules_.size();
      return true;
    }
    return false;
  }

 protected:
  std::vector<PollRule> rules_;
  size_t next_rule_{0};
  uint32_t revision_{0};
  bool running_{false};
};

}  // namespace esphome::palazzetti
