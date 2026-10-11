#pragma once

#include <deque>
#include <functional>
#include <vector>

#include "esphome/components/uart/uart.h"
#include "esphome/core/automation.h"
#include "esphome/core/component.h"
#include "micronova.h"
#include "write_policy.h"
#include "polling_plan.h"
#include "read_cache.h"

namespace esphome::palazzetti {

using micronova::Memory;

enum class EchoMode : uint8_t { AUTO, ON, OFF };
enum class Kind : uint8_t { READ, WRITE, RAW };

static const size_t MAX_FRAME = 8;
static const size_t MAX_REPLY = 16;

struct Result {
  bool ok{false};
  bool timeout{false};
  micronova::ReplyCheck check{micronova::ReplyCheck::BAD_CHECKSUM};
  uint8_t value{0};
  uint8_t reply[MAX_REPLY]{};
  uint8_t reply_len{0};
  uint32_t elapsed_ms{0};
  uint8_t attempts{0};
  const char *error{nullptr};
};

using Callback = std::function<void(const Result &)>;

struct PollSample {
  uint32_t sequence;
  uint32_t uptime_ms;
  uint32_t revision;
  Memory memory;
  uint16_t address;
  Result result;
};

struct Request {
  Kind kind{Kind::READ};
  Memory mem{Memory::RAM};
  uint16_t addr{0};
  uint8_t frame[MAX_FRAME]{};
  uint8_t frame_len{0};
  uint8_t reply_len{micronova::REPLY_LEN};
  uint8_t retries{0};
  bool polling{false};
  Callback cb;
};

// Anything that wants to be told about every value seen on the bus for a given address
// (entities, lab monitor). Values are pushed whatever the origin of the request.
class Listener {
 public:
  virtual void on_value(Memory mem, uint16_t addr, uint8_t value) = 0;
};

class Palazzetti : public Component, public uart::UARTDevice {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::DATA; }

  void set_echo_mode(EchoMode m) { this->echo_mode_ = m; }
  void set_reply_timeout(uint32_t ms) { this->reply_timeout_ = ms; }
  void set_frame_gap(uint32_t ms) { this->frame_gap_ = ms; }
  void set_max_retries(uint8_t n) { this->max_retries_ = n; }
  void set_max_queue(uint8_t n) { this->max_queue_ = n; }
  void add_write_rule(Memory mem, uint16_t addr, uint8_t minimum, uint8_t maximum) {
    this->write_policy_.add_rule(mem, addr, minimum, maximum);
  }
  void set_write_enabled(bool enabled) { this->write_policy_.set_enabled(enabled); }
  void set_eeprom_write_enabled(bool enabled) { this->write_policy_.set_eeprom_enabled(enabled); }
  bool is_write_enabled() const { return this->write_policy_.enabled(); }
  bool is_eeprom_write_enabled() const { return this->write_policy_.eeprom_enabled(); }
  size_t write_rule_count() const { return this->write_policy_.rule_count(); }
  bool can_write(Memory mem, uint16_t addr, uint8_t value) const { return this->write_policy_.allows(mem, addr, value); }

  // Polling read issued by entities: deduplicated, dropped while polling is paused.
  void poll(Memory mem, uint16_t addr);
  bool read(Memory mem, uint16_t addr, Callback cb);
  bool read_pending(Memory mem, uint16_t addr) const;
  const ReadCache &read_cache() const { return this->read_cache_; }
  bool write(Memory mem, uint16_t addr, uint8_t value, Callback cb = nullptr);
  bool raw(const uint8_t *frame, size_t len, size_t reply_len, Callback cb);

  void add_listener(Memory mem, uint16_t addr, Listener *l);
  void set_trace(std::function<void(const Request &, const Result &)> t) { this->trace_ = std::move(t); }

  void set_polling_paused(bool p) { this->polling_paused_ = p; }
  bool is_polling_paused() const { return this->polling_paused_; }
  size_t queue_size() const { return this->queue_.size(); }
  size_t queue_capacity() const { return this->max_queue_; }
  const char *echo_state() const;
  uint32_t n_ok() const { return this->n_ok_; }
  uint32_t n_timeout() const { return this->n_timeout_; }
  uint32_t n_bad() const { return this->n_bad_; }
  uint32_t n_dropped() const { return this->n_dropped_; }
  PollingPlan &polling_plan() { return this->polling_plan_; }
  const std::deque<PollSample> &poll_samples() const { return this->poll_samples_; }
  uint32_t poll_sequence() const { return this->poll_sequence_; }
  uint32_t boot_id() const { return this->boot_id_; }
  static constexpr size_t POLL_HISTORY = 32;

 protected:
  enum class State : uint8_t { IDLE, WAIT };
  bool enqueue_(Request &&r, bool front);
  void send_(uint32_t now);
  void receive_(uint32_t now);
  void finish_(bool timeout, uint32_t now);
  void notify_(Memory mem, uint16_t addr, uint8_t value);
  void poll_plan_(uint32_t now);

  EchoMode echo_mode_{EchoMode::AUTO};
  int8_t echo_latched_{-1};  // AUTO only: -1 undecided, 0 no echo, 1 echo
  uint32_t reply_timeout_{300};
  uint32_t frame_gap_{30};
  uint8_t max_retries_{2};
  uint8_t max_queue_{48};
  bool polling_paused_{false};
  WritePolicy write_policy_;
  ReadCache read_cache_;
  PollingPlan polling_plan_;
  std::deque<PollSample> poll_samples_;
  bool plan_pending_{false};
  uint32_t poll_sequence_{0};
  uint32_t boot_id_{0};

  std::deque<Request> queue_;
  Request current_;
  State state_{State::IDLE};
  uint32_t sent_at_{0};
  uint32_t last_activity_{0};
  uint8_t rx_[MAX_FRAME + MAX_REPLY]{};
  uint8_t rx_len_{0};
  bool echo_done_{false};

  struct Registration {
    Memory mem;
    uint16_t addr;
    Listener *listener;
  };
  std::vector<Registration> listeners_;
  std::function<void(const Request &, const Result &)> trace_;

  uint32_t n_ok_{0}, n_timeout_{0}, n_bad_{0}, n_dropped_{0};
};

template<typename... Ts> class WriteAction : public Action<Ts...>, public Parented<Palazzetti> {
 public:
  TEMPLATABLE_VALUE(uint8_t, value)
  void set_memory(Memory m) { this->mem_ = m; }
  void set_address(uint16_t a) { this->addr_ = a; }
  void play(const Ts &...x) override { this->parent_->write(this->mem_, this->addr_, this->value_.value(x...)); }

 protected:
  Memory mem_{Memory::RAM};
  uint16_t addr_{0};
};

}  // namespace esphome::palazzetti
