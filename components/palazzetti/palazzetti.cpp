#include "palazzetti.h"

#include <cstring>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace esphome::palazzetti {

static const char *const TAG = "palazzetti";

static const char *mem_str(Memory m) { return m == Memory::EEPROM ? "eeprom" : "ram"; }

void Palazzetti::setup() {
  uint8_t b;
  while (this->available())
    this->read_byte(&b);
}

void Palazzetti::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Palazzetti / Micronova bus:\n"
                "  Echo: %s\n"
                "  Reply timeout: %u ms\n"
                "  Frame gap: %u ms\n"
                "  Retries: %u\n"
                "  Listeners: %u",
                this->echo_state(), (unsigned) this->reply_timeout_, (unsigned) this->frame_gap_,
                this->max_retries_, (unsigned) this->listeners_.size());
  this->check_uart_settings(1200, 2, uart::UART_CONFIG_PARITY_NONE, 8);
}

const char *Palazzetti::echo_state() const {
  switch (this->echo_mode_) {
    case EchoMode::ON:
      return "on";
    case EchoMode::OFF:
      return "off";
    default:
      return this->echo_latched_ < 0 ? "auto-undecided" : (this->echo_latched_ ? "auto-echo" : "auto-no-echo");
  }
}

bool Palazzetti::enqueue_(Request &&r, bool front) {
  if (this->queue_.size() >= this->max_queue_) {
    this->n_dropped_++;
    ESP_LOGW(TAG, "Queue full, dropping %s 0x%03X", mem_str(r.mem), r.addr);
    return false;
  }
  if (front)
    this->queue_.push_front(std::move(r));
  else
    this->queue_.push_back(std::move(r));
  return true;
}

void Palazzetti::poll(Memory mem, uint16_t addr) {
  if (this->polling_paused_)
    return;
  for (auto &q : this->queue_)
    if (q.polling && q.mem == mem && q.addr == addr)
      return;
  Request r;
  r.mem = mem;
  r.addr = addr;
  r.polling = true;
  r.frame_len = micronova::build_read(r.frame, mem, addr);
  this->enqueue_(std::move(r), false);
}

bool Palazzetti::read(Memory mem, uint16_t addr, Callback cb) {
  Request r;
  r.mem = mem;
  r.addr = addr;
  r.cb = std::move(cb);
  r.frame_len = micronova::build_read(r.frame, mem, addr);
  return this->enqueue_(std::move(r), false);
}

bool Palazzetti::write(Memory mem, uint16_t addr, uint8_t value, Callback cb) {
  if (!this->can_write(mem, addr, value)) {
    ESP_LOGW(TAG, "Write denied: %s 0x%03X = 0x%02X (mode, EEPROM gate or allowlist)", mem_str(mem), addr, value);
    return false;
  }
  ESP_LOGI(TAG, "Write %s 0x%03X = 0x%02X", mem_str(mem), addr, value);
  Request r;
  r.kind = Kind::WRITE;
  r.mem = mem;
  r.addr = addr;
  r.cb = std::move(cb);
  r.frame_len = micronova::build_write(r.frame, mem, addr, value);
  return this->enqueue_(std::move(r), true);
}

bool Palazzetti::raw(const uint8_t *frame, size_t len, size_t reply_len, Callback cb) {
  if (len != micronova::READ_FRAME_LEN || reply_len != micronova::REPLY_LEN || (frame[0] & 0xC0) != 0) {
    ESP_LOGW(TAG, "Raw frame denied: only two-byte Micronova reads are allowed");
    return false;
  }
  Memory mem = frame[0] & 0x20 ? Memory::EEPROM : Memory::RAM;
  uint16_t addr = ((frame[0] & 0x1F) << 8) | frame[1];
  return this->read(mem, addr, std::move(cb));
}

void Palazzetti::add_listener(Memory mem, uint16_t addr, Listener *l) {
  this->listeners_.push_back({mem, addr, l});
}

void Palazzetti::notify_(Memory mem, uint16_t addr, uint8_t value) {
  for (auto &reg : this->listeners_)
    if (reg.mem == mem && reg.addr == addr)
      reg.listener->on_value(mem, addr, value);
}

void Palazzetti::loop() {
  uint32_t now = millis();
  if (this->state_ == State::IDLE) {
    if (!this->queue_.empty() && now - this->last_activity_ >= this->frame_gap_)
      this->send_(now);
    return;
  }
  this->receive_(now);
}

void Palazzetti::send_(uint32_t now) {
  this->current_ = std::move(this->queue_.front());
  this->queue_.pop_front();
  if (this->current_.kind == Kind::WRITE &&
      !this->can_write(this->current_.mem, this->current_.addr, this->current_.frame[2])) {
    ESP_LOGW(TAG, "Queued write cancelled: permission revoked");
    Result result;
    result.error = "write-permission-revoked";
    this->n_dropped_++;
    if (this->current_.cb)
      this->current_.cb(result);
    return;
  }
  uint8_t b;
  while (this->available())
    this->read_byte(&b);
  this->write_array(this->current_.frame, this->current_.frame_len);
  this->rx_len_ = 0;
  this->echo_done_ = this->echo_mode_ == EchoMode::OFF || (this->echo_mode_ == EchoMode::AUTO && this->echo_latched_ == 0);
  this->sent_at_ = now;
  this->state_ = State::WAIT;
}

void Palazzetti::receive_(uint32_t now) {
  const uint8_t flen = this->current_.frame_len;
  while (this->available() && this->rx_len_ < sizeof(this->rx_))
    this->read_byte(&this->rx_[this->rx_len_++]);

  if (!this->echo_done_) {
    bool strip = false;
    if (this->echo_mode_ == EchoMode::ON || this->echo_latched_ == 1) {
      strip = this->rx_len_ >= flen;
    } else {
      // AUTO undecided: echo iff the bytes received so far are a prefix of the frame
      // and more bytes keep coming after a full copy of it.
      size_t n = this->rx_len_ < flen ? this->rx_len_ : flen;
      if (memcmp(this->rx_, this->current_.frame, n) != 0) {
        this->echo_latched_ = 0;
        this->echo_done_ = true;
        ESP_LOGI(TAG, "Echo auto-detection: no echo");
      } else if (this->rx_len_ > flen) {
        this->echo_latched_ = 1;
        strip = true;
        ESP_LOGI(TAG, "Echo auto-detection: echo present");
      }
    }
    if (strip) {
      memmove(this->rx_, this->rx_ + flen, this->rx_len_ - flen);
      this->rx_len_ -= flen;
      this->echo_done_ = true;
    }
  }

  if (this->echo_done_ && this->rx_len_ >= this->current_.reply_len) {
    this->finish_(false, now);
  } else if (now - this->sent_at_ > this->reply_timeout_) {
    // AUTO undecided and the only bytes received equal the frame: they were the reply.
    if (!this->echo_done_ && this->rx_len_ == this->current_.reply_len)
      this->finish_(false, now);
    else
      this->finish_(true, now);
  }
}

void Palazzetti::finish_(bool timeout, uint32_t now) {
  Request &req = this->current_;
  Result res;
  res.timeout = timeout;
  res.elapsed_ms = now - this->sent_at_;
  res.attempts = req.retries + 1;
  res.reply_len = this->rx_len_ < MAX_REPLY ? this->rx_len_ : MAX_REPLY;
  memcpy(res.reply, this->rx_, res.reply_len);

  if (!timeout) {
    switch (req.kind) {
      case Kind::READ:
        res.check = micronova::check_read_reply(req.frame, res.reply);
        res.value = res.reply[1];
        res.ok = micronova::reply_ok(res.check);
        break;
      case Kind::WRITE:
        res.check = micronova::check_write_reply(req.frame, res.reply);
        res.value = req.frame[2];
        res.ok = micronova::reply_ok(res.check);
        break;
      case Kind::RAW:
        res.check = micronova::ReplyCheck::OK;
        res.ok = true;
        break;
    }
  }

  this->state_ = State::IDLE;
  this->last_activity_ = now;

  if (!res.ok && req.kind != Kind::RAW && req.retries < this->max_retries_) {
    req.retries++;
    ESP_LOGD(TAG, "Retry %u %s 0x%03X (%s)", req.retries, mem_str(req.mem), req.addr,
             timeout ? "timeout" : micronova::reply_check_str(res.check));
    this->queue_.push_front(std::move(req));
    return;
  }

  if (res.ok) {
    this->n_ok_++;
    if (req.kind != Kind::RAW)
      this->notify_(req.mem, req.addr, res.value);
  } else if (timeout) {
    this->n_timeout_++;
    ESP_LOGW(TAG, "Timeout on %s 0x%03X (%u bytes received)", mem_str(req.mem), req.addr, this->rx_len_);
  } else {
    this->n_bad_++;
    ESP_LOGW(TAG, "%s on %s 0x%03X: %02X %02X", micronova::reply_check_str(res.check), mem_str(req.mem), req.addr,
             res.reply[0], res.reply[1]);
  }
  if (this->trace_)
    this->trace_(req, res);
  if (req.cb)
    req.cb(res);
}

}  // namespace esphome::palazzetti
