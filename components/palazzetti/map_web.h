#pragma once

#include "esphome/core/defines.h"
#ifdef USE_PALAZZETTI_MAP_WEB
#include "palazzetti.h"
#include "esphome/components/web_server_base/web_server_base.h"

namespace esphome::palazzetti {

struct MapByte {
  Memory memory;
  uint16_t address;
  uint32_t interval;
  uint32_t override_interval{0};
};

class MapWeb : public Component, public Parented<Palazzetti>, public AsyncWebHandler {
 public:
  void setup() override;
  void loop() override;
  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }
  bool canHandle(AsyncWebServerRequest *request) const override;
  bool isRequestHandlerTrivial() const override { return false; }
  void handleRequest(AsyncWebServerRequest *request) override;
  void handleBody(AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) override;
  void set_page(const char *page) { this->page_ = page; }

 protected:
  bool validate_(Stream &body, std::vector<MapByte> &bytes, std::string &error);
  void error_(AsyncWebServerRequest *request, int status, const char *message);
  std::vector<MapByte> bytes_;
  size_t cursor_{0};
  bool pending_{false};
  bool mounted_{false};
  const char *page_{nullptr};
  uint32_t next_attempt_{0};
  bool retry_backoff_{false};
  AsyncWebServerRequest *upload_request_{nullptr};
  size_t upload_received_{0};
  size_t upload_total_{0};
  const char *upload_error_{nullptr};
};

}  // namespace esphome::palazzetti
#endif
