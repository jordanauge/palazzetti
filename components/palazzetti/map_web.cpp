#include "map_web.h"
#ifdef USE_PALAZZETTI_MAP_WEB
#include <algorithm>
#include <cmath>
#include <memory>
#include <LittleFS.h>
#include "esphome/components/json/json_util.h"
#include "esphome/core/log.h"

namespace esphome::palazzetti {

static const char *const TAG = "palazzetti.map";
static constexpr size_t MAX_DOCUMENT = 8192;
static constexpr size_t MAX_BYTES = 64;
static const char *const MAP_PATH = "/palazzetti-map.json";

void MapWeb::setup() {
  LittleFS.setConfig(LittleFSConfig().setAutoFormat(false));
  this->mounted_ = LittleFS.begin();
  if (this->mounted_ && LittleFS.exists(MAP_PATH)) {
    auto file = LittleFS.open(MAP_PATH, "r");
    if (file && file.size() <= MAX_DOCUMENT) {
      std::string error;
      std::vector<MapByte> bytes;
      if (this->validate_(file, bytes, error))
        this->bytes_ = std::move(bytes);
      else
        ESP_LOGE(TAG, "Stored map rejected: %s", error.c_str());
    } else {
      ESP_LOGE(TAG, "Stored map unreadable or oversized");
    }
  }
  if (!this->mounted_)
    ESP_LOGW(TAG, "Filesystem not mounted; explicitly initialize it from /memory before uploading maps");
  web_server_base::global_web_server_base->add_handler(this);
}

bool MapWeb::validate_(Stream &body, std::vector<MapByte> &bytes, std::string &error) {
  JsonDocument filter;
  filter["format"] = true;
  filter["maps"][0]["id"] = true;
  filter["maps"][0]["interval_ms"] = true;
  auto field_filter = filter["maps"][0]["fields"][0].to<JsonObject>();
  for (const char *key : {"id", "mem", "addr", "width", "encoding", "interval_ms", "scale", "offset"})
    field_filter[key] = true;
  JsonDocument doc;
  if (deserializeJson(doc, body, DeserializationOption::NestingLimit(8), DeserializationOption::Filter(filter))) {
    error = "Invalid JSON, excessive nesting or insufficient parsing heap";
    return false;
  }
  auto maps = doc["maps"].as<JsonArray>();
  if (!doc["format"].is<uint8_t>() || doc["format"].as<int>() != 1 ||
      maps.isNull() || maps.size() == 0 || maps.size() > 4) {
    error = "Expected format 1 and 1..4 maps";
    return false;
  }
  std::vector<std::string> ids;
  size_t fields = 0;
  for (JsonObject map : maps) {
    std::string id = map["id"] | "";
    if (id.empty() || id.size() > 80 || std::find(ids.begin(), ids.end(), id) != ids.end() ||
        !map["interval_ms"].is<uint32_t>()) {
      error = "Map IDs must be unique; interval_ms must be an integer";
      return false;
    }
    ids.push_back(id);
    uint32_t interval = map["interval_ms"];
    auto entries = map["fields"].as<JsonArray>();
    if (interval < 100 || interval > 86400000 || entries.isNull() || entries.size() == 0) {
      error = "Invalid map interval or empty fields";
      return false;
    }
    std::vector<std::string> field_ids;
    for (JsonObject field : entries) {
      std::string identity = field["id"] | "";
      const char *mem = field["mem"] | "";
      if (++fields > 48 || identity.empty() || identity.size() > 80 ||
          std::find(field_ids.begin(), field_ids.end(), identity) != field_ids.end() ||
          (strcmp(mem, "ram") && strcmp(mem, "eeprom")) || !field["addr"].is<uint16_t>()) {
        error = "Invalid field, duplicate ID or more than 48 fields";
        return false;
      }
      field_ids.push_back(identity);
      uint16_t address = field["addr"];
      uint8_t width = 1;
      if (!field["width"].isNull()) {
        if (!field["width"].is<uint8_t>()) {
          error = "Field width must be an integer";
          return false;
        }
        width = field["width"];
      }
      if (!field["interval_ms"].isNull()) {
        if (!field["interval_ms"].is<uint32_t>()) {
          error = "Field interval must be an integer";
          return false;
        }
        interval = field["interval_ms"];
      } else {
        interval = map["interval_ms"];
      }
      const char *encoding = field["encoding"] | "uint8";
      bool word = !strcmp(encoding, "uint16_le") || !strcmp(encoding, "uint16_be") ||
                  !strcmp(encoding, "int16_le") || !strcmp(encoding, "int16_be");
      if ((width != 1 && width != 2) || address + width - 1 > micronova::MAX_ADDRESS ||
          interval < 100 || interval > 86400000 ||
          (!word && strcmp(encoding, "uint8") && strcmp(encoding, "int8") && strcmp(encoding, "bcd")) ||
          (word != (width == 2)) ||
          (!field["encoding"].isNull() && !field["encoding"].is<const char *>()) ||
          (!field["scale"].isNull() && !field["scale"].is<double>()) ||
          (!field["offset"].isNull() && !field["offset"].is<double>()) ||
          (!field["scale"].isNull() && !std::isfinite(field["scale"].as<double>())) ||
          (!field["offset"].isNull() && !std::isfinite(field["offset"].as<double>()))) {
        error = "Invalid bounds, encoding, conversion or interval";
        return false;
      }
      Memory memory = !strcmp(mem, "ram") ? Memory::RAM : Memory::EEPROM;
      for (uint16_t addr = address; addr < address + width; addr++) {
        auto it = std::find_if(bytes.begin(), bytes.end(), [memory, addr](const MapByte &byte) {
          return byte.memory == memory && byte.address == addr;
        });
        if (it != bytes.end())
          it->interval = std::min(it->interval, interval);
        else if (bytes.size() < MAX_BYTES)
          bytes.push_back({memory, addr, interval});
        else {
          error = "More than 64 unique mapped bytes";
          return false;
        }
      }
    }
  }
  return true;
}

void MapWeb::error_(AsyncWebServerRequest *request, int status, const char *message) {
  ESP_LOGW(TAG, "%s", message);
  request->send(status, "text/plain", message);
}

bool MapWeb::canHandle(AsyncWebServerRequest *request) const {
  auto url = request->url();
  return url == "/memory" || url == "/memory/map" || url == "/memory/cache" ||
         url == "/memory/override" || url == "/memory/initialize";
}

void MapWeb::handleBody(AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
  if (request->url() != "/memory/map" || request->method() != HTTP_POST)
    return;
  if (total > MAX_DOCUMENT || total == 0 || !this->mounted_)
    return;
  if (index == 0) {
    if (this->upload_request_ != nullptr)
      return;
    this->upload_request_ = request;
    this->upload_received_ = 0;
    this->upload_total_ = total;
    this->upload_error_ = nullptr;
    request->_tempFile = LittleFS.open("/palazzetti-map.pending", "w");
    if (!request->_tempFile)
      this->upload_error_ = "Cannot open map staging file";
    request->onDisconnect([this, request]() {
      if (this->upload_request_ == request)
        this->upload_request_ = nullptr;
    });
  }
  if (this->upload_request_ == request && this->upload_received_ == index &&
      index + len <= this->upload_total_) {
    if (!this->upload_error_ && request->_tempFile.write(data, len) != len)
      this->upload_error_ = "Cannot write map staging file";
    this->upload_received_ += len;
  }
}

void MapWeb::handleRequest(AsyncWebServerRequest *request) {
  auto url = request->url();
  if (url == "/memory" && request->method() == HTTP_GET) {
    request->send_P(200, "text/html", this->page_);
    return;
  }
  if (url == "/memory/initialize" && request->method() == HTTP_POST) {
    if (this->mounted_) {
      this->error_(request, 409, "Filesystem already mounted; initialization refused");
      return;
    }
    if (!request->hasParam("confirm", true) || request->getParam("confirm", true)->value() != "INITIALIZE") {
      this->error_(request, 400, "Explicit INITIALIZE confirmation required");
      return;
    }
    this->mounted_ = LittleFS.format() && LittleFS.begin();
    if (!this->mounted_) {
      this->error_(request, 500, "Filesystem initialization failed");
      return;
    }
    request->send(200, "text/plain", "Filesystem initialized");
    return;
  }
  if (url == "/memory/map" && request->method() == HTTP_GET) {
    if (!this->mounted_ || !LittleFS.exists(MAP_PATH)) {
      this->error_(request, 404, "No stored map; initialize storage and upload a JSON map");
      return;
    }
    request->send(LittleFS, MAP_PATH, "application/json");
    return;
  }
  if (url == "/memory/map" && request->method() == HTTP_POST) {
    if (!this->mounted_) {
      this->error_(request, 503, "Filesystem not mounted; initialize explicitly");
      return;
    }
    if (this->upload_request_ != request || this->upload_received_ != this->upload_total_) {
      this->error_(request, 413, "Body missing, incomplete, too large or upload busy");
      return;
    }
    request->_tempFile.close();
    this->upload_request_ = nullptr;
    if (this->upload_error_) {
      this->error_(request, 500, this->upload_error_);
      return;
    }
    std::vector<MapByte> bytes;
    std::string error;
    auto file = LittleFS.open("/palazzetti-map.pending", "r");
    if (!file) {
      this->error_(request, 500, "Cannot reopen staged map");
      return;
    }
    if (!this->validate_(file, bytes, error)) {
      this->error_(request, 400, error.c_str());
      return;
    }
    file.close();
    if (!LittleFS.rename("/palazzetti-map.pending", MAP_PATH)) {
      this->error_(request, 500, "Map persistence failed; active map unchanged");
      return;
    }
    this->bytes_ = std::move(bytes);
    this->cursor_ = 0;
    request->send(200, "text/plain", "Map stored and activated; overrides reset");
    return;
  }
  if (url == "/memory/override" && request->method() == HTTP_POST) {
    if (!request->hasParam("mem", true) || !request->hasParam("addr", true) ||
        !request->hasParam("interval_ms", true)) {
      this->error_(request, 400, "mem, addr and interval_ms required");
      return;
    }
    auto mem = request->getParam("mem", true)->value();
    auto raw_addr = request->getParam("addr", true)->value();
    auto raw_interval = request->getParam("interval_ms", true)->value();
    char *end;
    auto address = strtoul(raw_addr.c_str(), &end, 10);
    bool valid = raw_addr.length() && *end == 0 && address <= micronova::MAX_ADDRESS;
    auto interval = strtoul(raw_interval.c_str(), &end, 10);
    valid = valid && raw_interval.length() && *end == 0 &&
            (interval == 0 || (interval >= 100 && interval <= 86400000)) && (mem == "ram" || mem == "eeprom");
    if (valid)
      for (auto &byte : this->bytes_)
        if (byte.address == address && byte.memory == (mem == "ram" ? Memory::RAM : Memory::EEPROM)) {
          byte.override_interval = interval;
          request->send(200, "text/plain", "Volatile interval updated; zero restores map interval");
          return;
        }
    this->error_(request, 400, "Invalid override or byte not in active map");
    return;
  }
  if (url == "/memory/cache" && request->method() == HTTP_GET) {
    if (ESP.getFreeHeap() < 6000 + this->bytes_.size() * 40) {
      this->error_(request, 503, "Insufficient heap for cache snapshot; retry or reduce concurrent clients");
      return;
    }
    uint32_t now = millis();
    struct Snapshot {
      MapByte byte;
      CachedByte cached{};
      bool present;
      bool pending;
    };
    struct ResponseState {
      std::vector<Snapshot> samples;
      std::string fragment;
      size_t offset{0};
      size_t cursor{0};
      bool closed{false};
    };
    auto state = std::make_shared<ResponseState>();
    state->samples.reserve(this->bytes_.size());
    char header[192];
    snprintf(header, sizeof(header),
             "{\"boot\":%u,\"uptime_ms\":%u,\"filesystem\":%s,\"paused\":%s,\"free_heap\":%u,\"bytes\":[",
             this->parent_->boot_id(), now, this->mounted_ ? "true" : "false",
             this->parent_->is_polling_paused() ? "true" : "false", ESP.getFreeHeap());
    state->fragment = header;
    for (const auto &byte : this->bytes_) {
      const auto *cached = this->parent_->read_cache().find(byte.memory, byte.address);
      state->samples.push_back({byte, cached ? *cached : CachedByte{}, cached != nullptr,
                                this->parent_->read_pending(byte.memory, byte.address)});
    }
    request->send(request->beginChunkedResponse("application/json", [state, now](uint8_t *buffer, size_t length,
                                                                               size_t index) -> size_t {
      size_t written = 0;
      while (written < length) {
        if (state->offset == state->fragment.size()) {
          state->fragment.clear();
          state->offset = 0;
          if (state->cursor < state->samples.size()) {
            const auto &sample = state->samples[state->cursor];
            uint32_t interval = sample.byte.override_interval ? sample.byte.override_interval : sample.byte.interval;
            JsonDocument doc;
            doc["mem"] = sample.byte.memory == Memory::RAM ? "ram" : "eeprom";
            doc["addr"] = sample.byte.address;
            doc["interval_ms"] = interval;
            doc["override"] = sample.byte.override_interval != 0;
            doc["valid"] = sample.present && sample.cached.valid;
            doc["error"] = sample.present ? sample.cached.error : "not-read";
            doc["pending"] = sample.pending;
            doc["stale"] = !sample.present || !sample.cached.valid || now - sample.cached.updated_ms >= interval;
            if (sample.present)
              doc["age_ms"] = now - sample.cached.updated_ms;
            else
              doc["age_ms"] = nullptr;
            if (sample.present && sample.cached.valid)
              doc["value"] = sample.cached.value;
            else
              doc["value"] = nullptr;
            serializeJson(doc, state->fragment);
            if (state->cursor++ != 0)
              state->fragment.insert(0, ",");
          } else if (!state->closed) {
            state->fragment = "]}";
            state->closed = true;
          } else {
            break;
          }
        }
        size_t count = std::min(length - written, state->fragment.size() - state->offset);
        memcpy(buffer + written, state->fragment.data() + state->offset, count);
        state->offset += count;
        written += count;
      }
      return written;
    }));
    return;
  }
  this->error_(request, 405, "Method not allowed");
}

void MapWeb::loop() {
  uint32_t now = millis();
  if (this->pending_ || this->bytes_.empty() || this->parent_->is_polling_paused())
    return;
  if (this->retry_backoff_ && static_cast<int32_t>(now - this->next_attempt_) < 0)
    return;
  this->retry_backoff_ = false;
  for (size_t n = 0; n < this->bytes_.size(); n++) {
    auto &byte = this->bytes_[this->cursor_++ % this->bytes_.size()];
    auto *cached = this->parent_->read_cache().find(byte.memory, byte.address);
    uint32_t interval = byte.override_interval ? byte.override_interval : byte.interval;
    if (cached && now - cached->updated_ms < interval)
      continue;
    if (this->parent_->read_pending(byte.memory, byte.address))
      continue;
    this->pending_ = true;
    if (!this->parent_->read(byte.memory, byte.address, [this](const Result &) { this->pending_ = false; })) {
      this->pending_ = false;
      this->next_attempt_ = now + 100;
      this->retry_backoff_ = true;
      ESP_LOGW(TAG, "Map read rejected: queue full");
    }
    return;
  }
}

}  // namespace esphome::palazzetti
#endif
