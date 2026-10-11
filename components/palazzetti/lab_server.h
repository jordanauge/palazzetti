#pragma once

#include "esphome/core/defines.h"
#ifdef USE_PALAZZETTI_LAB

#include <memory>
#include <string>

#include "esphome/components/socket/socket.h"
#include "esphome/core/component.h"
#include "palazzetti.h"

namespace esphome::palazzetti {

// Line-oriented TCP service for reverse engineering (see docs/reverse-engineering.md).
// One client, one command in flight; replies start with "ok"/"err", streamed lines
// with "v" (dump values) or "m" (monitor of all bus traffic).
class LabServer : public Component, public Parented<Palazzetti> {
 public:
  void set_port(uint16_t p) { this->port_ = p; }
  void set_allow_write(bool a) { this->allow_write_ = a; }
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

 protected:
  void accept_();
  void read_client_();
  void flush_();
  void close_client_();
  void handle_(char *line);
  void dump_next_();
  void send_(const char *fmt, ...) __attribute__((format(printf, 2, 3)));
  void done_() { this->busy_ = false; }

  uint16_t port_{6638};
  bool allow_write_{false};
  bool monitor_{false};
  bool busy_{false};
  socket::ListenSocket *server_{nullptr};
  std::unique_ptr<socket::Socket> client_;
  std::string in_;
  std::string out_;

  Memory dump_mem_{Memory::RAM};
  uint16_t dump_cur_{0};
  uint16_t dump_end_{0};
  bool dumping_{false};
};

}  // namespace esphome::palazzetti

#endif
