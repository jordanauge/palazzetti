#pragma once

#include <map>
#include <string>
#include <vector>

#include "esphome/core/defines.h"
#include "palazzetti.h"

#ifdef USE_SENSOR
#include "esphome/components/sensor/sensor.h"
#endif
#ifdef USE_NUMBER
#include "esphome/components/number/number.h"
#endif
#ifdef USE_SWITCH
#include "esphome/components/switch/switch.h"
#endif
#ifdef USE_TEXT_SENSOR
#include "esphome/components/text_sensor/text_sensor.h"
#endif

namespace esphome::palazzetti {

enum class Encoding : uint8_t { UINT8, INT8, BCD, UINT16_BE, UINT16_LE, INT16_BE, INT16_LE };

// Common part of every bus-backed entity: a (memory, address, encoding) slot polled at
// update_interval. A value is published once every byte of the slot has been seen.
class BusEntity : public PollingComponent, public Listener, public Parented<Palazzetti> {
 public:
  void set_memory(Memory m) { this->mem_ = m; }
  void set_address(uint16_t a) { this->addr_ = a; }
  void set_encoding(Encoding e) { this->enc_ = e; }

  void setup() override;
  void update() override;
  void on_value(Memory mem, uint16_t addr, uint8_t value) override;
  float get_setup_priority() const override { return setup_priority::DATA; }

 protected:
  uint8_t length_() const { return this->enc_ >= Encoding::UINT16_BE ? 2 : 1; }
  int32_t decode_() const;
  void encode_write_(int32_t v);
  virtual void publish_raw_(int32_t v) = 0;

  Memory mem_{Memory::RAM};
  uint16_t addr_{0};
  Encoding enc_{Encoding::UINT8};
  uint8_t bytes_[2]{};
  uint8_t seen_{0};
};

#ifdef USE_SENSOR
class BusSensor : public BusEntity, public sensor::Sensor {
 protected:
  void publish_raw_(int32_t v) override { this->publish_state(v); }
};
#endif

#ifdef USE_NUMBER
class BusNumber : public BusEntity, public number::Number {
 public:
  void set_multiply(float m) { this->multiply_ = m; }
  void set_offset(float o) { this->offset_ = o; }

 protected:
  void publish_raw_(int32_t v) override { this->publish_state(v * this->multiply_ + this->offset_); }
  void control(float value) override;
  float multiply_{1.0f};
  float offset_{0.0f};
};
#endif

#ifdef USE_SWITCH
class BusSwitch : public BusEntity, public switch_::Switch {
 public:
  void set_on_value(uint8_t v) { this->on_value_ = v; }
  void set_off_value(uint8_t v) { this->off_value_ = v; }
  void set_off_states(std::vector<int32_t> s) { this->off_states_ = std::move(s); }

 protected:
  void publish_raw_(int32_t v) override;
  void write_state(bool state) override;
  uint8_t on_value_{1};
  uint8_t off_value_{0};
  std::vector<int32_t> off_states_;
};
#endif

#ifdef USE_TEXT_SENSOR
class BusTextSensor : public BusEntity, public text_sensor::TextSensor {
 public:
  void add_mapping(int32_t raw, const char *text) { this->map_[raw] = text; }

 protected:
  void publish_raw_(int32_t v) override;
  std::map<int32_t, const char *> map_;
};
#endif

}  // namespace esphome::palazzetti
