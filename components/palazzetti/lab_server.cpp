#include "lab_server.h"
#ifdef USE_PALAZZETTI_LAB

#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "esphome/core/log.h"

namespace esphome::palazzetti {

static const char *const TAG = "palazzetti.lab";
static const size_t MAX_OUT = 8192;
static const size_t MAX_LINE = 128;

static const char *const HELP =
    "# r <ram|eeprom> <addr>        read one byte\n"
    "# i <ram|eeprom> <addr>        inspect read: checked raw reply, attempts, latency\n"
    "# d <ram|eeprom> <start> <end> dump a range (streams 'v mem addr value|--')\n"
    "# w <ram|eeprom> <addr> <val>  write one byte (allow_write)\n"
    "# x <hex frame> 2              checked raw READ only (no write bypass)\n"
    "# info                         bus statistics\n"
    "# pause | resume               stop/restart entity polling\n"
    "# monitor <on|off>             stream every value seen on the bus ('m mem addr value')\n"
    "ok help\n";

static const char *mem_str(Memory m) { return m == Memory::EEPROM ? "eeprom" : "ram"; }

static bool parse_mem(const char *s, Memory *m) {
  if (s == nullptr)
    return false;
  if (!strcmp(s, "ram") || !strcmp(s, "r")) {
    *m = Memory::RAM;
    return true;
  }
  if (!strcmp(s, "eeprom") || !strcmp(s, "e")) {
    *m = Memory::EEPROM;
    return true;
  }
  return false;
}

static bool parse_num(const char *s, long max, long *out) {
  if (s == nullptr)
    return false;
  char *end;
  long v = strtol(s, &end, 0);
  if (end == s || *end != '\0' || v < 0 || v > max)
    return false;
  *out = v;
  return true;
}

void LabServer::setup() {
  this->server_ = socket::socket_ip_loop_monitored(SOCK_STREAM, 0).release();
  if (this->server_ == nullptr) {
    this->mark_failed();
    return;
  }
  int enable = 1;
  this->server_->setsockopt(SOL_SOCKET, SO_REUSEADDR, &enable, sizeof(enable));
  this->server_->setblocking(false);
  struct sockaddr_storage addr;
  socklen_t sl = socket::set_sockaddr_any((struct sockaddr *) &addr, sizeof(addr), this->port_);
  if (sl == 0 || this->server_->bind((struct sockaddr *) &addr, sl) != 0 || this->server_->listen(1) != 0) {
    ESP_LOGE(TAG, "Cannot listen on port %u", this->port_);
    this->mark_failed();
    return;
  }
  this->parent_->set_trace([this](const Request &req, const Result &res) {
    if (this->monitor_ && this->client_ && res.ok && req.kind != Kind::RAW)
      this->send_("m %s 0x%03X 0x%02X\n", mem_str(req.mem), req.addr, res.value);
  });
}

void LabServer::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Palazzetti lab server:\n"
                "  Port: %u\n"
                "  Writes allowed: %s",
                this->port_, YESNO(this->allow_write_));
}

void LabServer::loop() {
  if (!this->client_)
    this->accept_();
  if (!this->client_)
    return;
  this->read_client_();
  if (!this->client_)
    return;
  if (!this->busy_) {
    size_t nl = this->in_.find('\n');
    if (nl != std::string::npos) {
      std::string line = this->in_.substr(0, nl);
      this->in_.erase(0, nl + 1);
      if (!line.empty() && line.back() == '\r')
        line.pop_back();
      if (!line.empty())
        this->handle_(&line[0]);
    }
  }
  this->flush_();
}

void LabServer::accept_() {
  // A request from a previous client may still be in flight: let it drain first.
  if (this->busy_ || !this->server_->ready())
    return;
  struct sockaddr_storage addr;
  socklen_t len = sizeof(addr);
  this->client_ = this->server_->accept_loop_monitored((struct sockaddr *) &addr, &len);
  if (!this->client_)
    return;
  this->client_->setblocking(false);
  this->in_.clear();
  this->out_.clear();
  ESP_LOGI(TAG, "Client connected");
  this->send_("ok palazzetti lab, writes %s; type 'help'\n", this->allow_write_ ? "allowed" : "disabled");
}

void LabServer::close_client_() {
  ESP_LOGI(TAG, "Client disconnected");
  this->client_.reset();
  this->monitor_ = false;
  this->dumping_ = false;
  this->parent_->set_polling_paused(false);
}

void LabServer::read_client_() {
  char buf[64];
  while (true) {
    ssize_t n = this->client_->read(buf, sizeof(buf));
    if (n > 0) {
      this->in_.append(buf, n);
      if (this->in_.size() > 4 * MAX_LINE) {
        this->in_.clear();
        this->send_("err line too long\n");
      }
      continue;
    }
    if (n == 0 || (errno != EWOULDBLOCK && errno != EAGAIN))
      this->close_client_();
    return;
  }
}

void LabServer::flush_() {
  if (!this->client_ || this->out_.empty())
    return;
  ssize_t n = this->client_->write(this->out_.data(), this->out_.size());
  if (n > 0)
    this->out_.erase(0, n);
  else if (n < 0 && errno != EWOULDBLOCK && errno != EAGAIN)
    this->close_client_();
}

void LabServer::send_(const char *fmt, ...) {
  if (!this->client_)
    return;
  char buf[512];
  va_list args;
  va_start(args, fmt);
  int n = vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  if (n <= 0 || n >= (int) sizeof(buf)) {
    ESP_LOGW(TAG, "Invalid or truncated lab response, disconnecting");
    this->close_client_();
    return;
  }
  if (this->out_.size() + n > MAX_OUT) {
    ESP_LOGW(TAG, "Output buffer full, disconnecting to prevent incomplete captures");
    this->close_client_();
    return;
  }
  this->out_.append(buf, n);
}

void LabServer::handle_(char *line) {
  char *argv[5] = {};
  int argc = 0;
  for (char *tok = strtok(line, " \t"); tok && argc < 5; tok = strtok(nullptr, " \t"))
    argv[argc++] = tok;
  const char *cmd = argv[0];
  if (cmd == nullptr)
    return;
  Memory mem;
  long addr, val, end;
  auto *bus = this->parent_;

  if (!strcmp(cmd, "help")) {
    this->out_ += HELP;
  } else if (!strcmp(cmd, "info")) {
    this->send_("ok info queue=%u ok=%u timeout=%u bad=%u dropped=%u paused=%d echo=%s write=%d monitor=%d eeprom=%d rules=%u\n",
                (unsigned) bus->queue_size(), (unsigned) bus->n_ok(), (unsigned) bus->n_timeout(),
                (unsigned) bus->n_bad(), (unsigned) bus->n_dropped(), bus->is_polling_paused(), bus->echo_state(),
                this->allow_write_ && bus->is_write_enabled(), this->monitor_,
                bus->is_eeprom_write_enabled(), (unsigned) bus->write_rule_count());
  } else if (!strcmp(cmd, "pause") || !strcmp(cmd, "resume")) {
    bus->set_polling_paused(cmd[0] == 'p');
    this->send_("ok %s\n", cmd);
  } else if (!strcmp(cmd, "monitor") && argc == 2 && (!strcmp(argv[1], "on") || !strcmp(argv[1], "off"))) {
    this->monitor_ = !strcmp(argv[1], "on");
    this->send_("ok monitor %s\n", this->monitor_ ? "on" : "off");
  } else if ((!strcmp(cmd, "r") || !strcmp(cmd, "i")) && argc == 3 && parse_mem(argv[1], &mem) &&
             parse_num(argv[2], micronova::MAX_ADDRESS, &addr)) {
    bool inspect = cmd[0] == 'i';
    this->busy_ = true;
    bool queued = bus->read(mem, addr, [this, mem, addr, inspect](const Result &res) {
      if (inspect) {
        uint8_t frame[2];
        micronova::build_read(frame, mem, addr);
        char reply[2 * MAX_REPLY + 1] = {};
        for (uint8_t i = 0; i < res.reply_len; i++)
          snprintf(reply + 2 * i, 3, "%02X", res.reply[i]);
        this->send_("ok i mem=%s addr=0x%03X valid=%d value=0x%02X check=%s tx=%02X%02X rx=%s attempts=%u ms=%u\n",
                    mem_str(mem), (unsigned) addr, res.ok, res.value,
                    res.timeout ? "timeout" : micronova::reply_check_str(res.check),
                    frame[0], frame[1], reply, res.attempts, (unsigned) res.elapsed_ms);
      } else if (res.ok)
        this->send_("ok r %s 0x%03X 0x%02X %s\n", mem_str(mem), (unsigned) addr, res.value,
                    micronova::reply_check_str(res.check));
      else
        this->send_("err r %s 0x%03X %s\n", mem_str(mem), (unsigned) addr,
                    res.timeout ? "timeout" : micronova::reply_check_str(res.check));
      this->done_();
    });
    if (!queued) {
      this->send_("err queue full\n");
      this->done_();
    }
  } else if (!strcmp(cmd, "d") && argc == 4 && parse_mem(argv[1], &mem) &&
             parse_num(argv[2], micronova::MAX_ADDRESS, &addr) &&
             parse_num(argv[3], micronova::MAX_ADDRESS, &end) && end >= addr) {
    this->busy_ = true;
    this->dumping_ = true;
    this->dump_mem_ = mem;
    this->dump_cur_ = addr;
    this->dump_end_ = end;
    this->dump_next_();
  } else if (!strcmp(cmd, "w") && argc == 4 && parse_mem(argv[1], &mem) &&
             parse_num(argv[2], micronova::MAX_ADDRESS, &addr) && parse_num(argv[3], 0xFF, &val)) {
    if (!this->allow_write_) {
      this->send_("err writes disabled (lab_server.allow_write)\n");
      return;
    }
    if (!bus->can_write(mem, addr, val)) {
      this->send_("err write denied (write mode, EEPROM gate or confirmed allowlist)\n");
      return;
    }
    this->busy_ = true;
    bool queued = bus->write(mem, addr, val, [this, mem, addr, val](const Result &res) {
      this->send_("%s w %s 0x%03X 0x%02X reply=%02X%02X %s\n", res.ok ? "ok" : "err", mem_str(mem), (unsigned) addr,
                  (unsigned) val, res.reply[0], res.reply[1],
                  res.error ? res.error : (res.timeout ? "timeout" : micronova::reply_check_str(res.check)));
      this->done_();
    });
    if (!queued) {
      this->send_("err queue full\n");
      this->done_();
    }
  } else if (!strcmp(cmd, "x") && argc == 3 && parse_num(argv[2], MAX_REPLY, &val)) {
    uint8_t frame[MAX_FRAME];
    size_t hex_len = strlen(argv[1]);
    if (hex_len == 0 || hex_len % 2 || hex_len / 2 > MAX_FRAME) {
      this->send_("err bad frame\n");
      return;
    }
    for (size_t i = 0; i < hex_len / 2; i++) {
      char byte[3] = {argv[1][2 * i], argv[1][2 * i + 1], 0};
      char *end_hex;
      long value = strtol(byte, &end_hex, 16);
      if (end_hex != byte + 2 || value < 0 || value > 255) {
        this->send_("err bad frame hex\n");
        return;
      }
      frame[i] = value;
    }
    this->busy_ = true;
    bool queued = bus->raw(frame, hex_len / 2, val, [this](const Result &res) {
      char hex[2 * MAX_REPLY + 1] = {};
      for (uint8_t i = 0; i < res.reply_len; i++)
        snprintf(hex + 2 * i, 3, "%02X", res.reply[i]);
      this->send_("%s x reply=%s len=%u %s\n", res.ok ? "ok" : "err", hex, res.reply_len,
                  res.timeout ? "timeout" : micronova::reply_check_str(res.check));
      this->done_();
    });
    if (!queued) {
      this->send_("err raw read refused (invalid read frame or queue full)\n");
      this->done_();
    }
  } else {
    this->send_("err unknown or malformed command; type 'help'\n");
  }
}

void LabServer::dump_next_() {
  if (!this->dumping_ || !this->client_) {
    this->done_();
    return;
  }
  if (this->dump_cur_ > this->dump_end_) {
    this->dumping_ = false;
    this->send_("ok d %s done\n", mem_str(this->dump_mem_));
    this->done_();
    return;
  }
  uint16_t a = this->dump_cur_++;
  bool queued = this->parent_->read(this->dump_mem_, a, [this, a](const Result &res) {
    if (res.ok)
      this->send_("v %s 0x%03X 0x%02X\n", mem_str(this->dump_mem_), a, res.value);
    else
      this->send_("v %s 0x%03X --\n", mem_str(this->dump_mem_), a);
    this->dump_next_();
  });
  if (!queued) {
    this->dumping_ = false;
    this->send_("err queue full\n");
    this->done_();
  }
}

}  // namespace esphome::palazzetti

#endif
