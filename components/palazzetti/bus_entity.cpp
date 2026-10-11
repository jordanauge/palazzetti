#include "bus_entity.h"

#include <cmath>
#include <cstdio>

#include "esphome/core/log.h"

namespace esphome::palazzetti {

static const char *const TAG = "palazzetti.entity";

void BusEntity::setup() {
  for (uint8_t i = 0; i < this->length_(); i++)
    this->parent_->add_listener(this->mem_, this->addr_ + i, this);
}

void BusEntity::update() {
  for (uint8_t i = 0; i < this->length_(); i++)
    this->parent_->poll(this->mem_, this->addr_ + i);
}

void BusEntity::on_value(Memory mem, uint16_t addr, uint8_t value) {
  uint8_t i = addr - this->addr_;
  this->bytes_[i] = value;
  this->seen_ |= 1 << i;
  uint8_t full = (1 << this->length_()) - 1;
  if (this->seen_ == full) {
    this->seen_ = 0;
    this->publish_raw_(this->decode_());
  }
}

int32_t BusEntity::decode_() const {
  const uint8_t *b = this->bytes_;
  switch (this->enc_) {
    case Encoding::INT8:
      return static_cast<int8_t>(b[0]);
    case Encoding::BCD:
      return micronova::bcd_to_int(b[0]);
    case Encoding::UINT16_BE:
      return (b[0] << 8) | b[1];
    case Encoding::UINT16_LE:
      return (b[1] << 8) | b[0];
    case Encoding::INT16_BE:
      return static_cast<int16_t>((b[0] << 8) | b[1]);
    case Encoding::INT16_LE:
      return static_cast<int16_t>((b[1] << 8) | b[0]);
    default:
      return b[0];
  }
}

void BusEntity::encode_write_(int32_t v) {
  if (this->length_() != 1) {
    ESP_LOGW(TAG, "Multi-byte writes refused: bus transactions are not atomic");
    return;
  }
  bool valid = this->enc_ == Encoding::INT8 ? v >= -128 && v <= 127 :
               this->enc_ == Encoding::BCD ? v >= 0 && v <= 99 : v >= 0 && v <= 255;
  if (!valid) {
    ESP_LOGW(TAG, "Entity write refused: value outside encoding range");
    return;
  }
  uint8_t b[2];
  switch (this->enc_) {
    case Encoding::BCD:
      b[0] = micronova::int_to_bcd(v);
      break;
    case Encoding::UINT16_BE:
    case Encoding::INT16_BE:
      b[0] = (v >> 8) & 0xFF;
      b[1] = v & 0xFF;
      break;
    case Encoding::UINT16_LE:
    case Encoding::INT16_LE:
      b[0] = v & 0xFF;
      b[1] = (v >> 8) & 0xFF;
      break;
    default:
      b[0] = v & 0xFF;
  }
  for (uint8_t i = 0; i < this->length_(); i++) {
    if (!this->parent_->can_write(this->mem_, this->addr_ + i, b[i])) {
      ESP_LOGW(TAG, "Entity write denied by central write policy");
      return;
    }
  }
  if (this->parent_->queue_size() + this->length_() > this->parent_->queue_capacity()) {
    ESP_LOGW(TAG, "Entity write refused: insufficient queue capacity");
    return;
  }
  for (uint8_t i = 0; i < this->length_(); i++)
    this->parent_->write(this->mem_, this->addr_ + i, b[i]);
}

#ifdef USE_NUMBER
void BusNumber::control(float value) {
  if (!std::isfinite(value)) {
    ESP_LOGW(TAG, "Entity write refused: non-finite value");
    return;
  }
  float decoded = (value - this->offset_) / this->multiply_;
  if (!std::isfinite(decoded) || decoded < -128 || decoded > 255) {
    ESP_LOGW(TAG, "Entity write refused: value outside byte range");
    return;
  }
  int32_t raw = lroundf(decoded);
  ESP_LOGD(TAG, "'%s': %.2f -> raw %d", this->get_name().c_str(), value, (int) raw);
  this->encode_write_(raw);
}
#endif

#ifdef USE_SWITCH
void BusSwitch::publish_raw_(int32_t v) {
  bool off = v == this->off_value_;
  for (auto s : this->off_states_)
    off |= v == s;
  this->publish_state(!off);
}

void BusSwitch::write_state(bool state) { this->encode_write_(state ? this->on_value_ : this->off_value_); }
#endif

#ifdef USE_TEXT_SENSOR
void BusTextSensor::publish_raw_(int32_t v) {
  auto it = this->map_.find(v);
  if (it != this->map_.end()) {
    this->publish_state(it->second);
    return;
  }
  char buf[24];
  snprintf(buf, sizeof(buf), "unknown (%d)", (int) v);
  this->publish_state(buf);
}
#endif

}  // namespace esphome::palazzetti
