#include "GY_BNO055.hpp"

GY_BNO055::GY_BNO055() {}

bool GY_BNO055::begin(TwoWire &wire, uint8_t i2cAddr, int sda, int scl, uint32_t freq) {
  _wire = &wire;

  if (sda >= 0 && scl >= 0) _wire->begin(sda, scl, freq);
  else { _wire->begin(); _wire->setClock(freq); }

  _addr = i2cAddr;
  if (!checkChipId()) {
    _addr = (i2cAddr == 0x28) ? 0x29 : 0x28;
    if (!checkChipId()) return false;
  }

  if (!setOperationMode(OprMode::CONFIGMODE)) return false;

  // reset
  if (!write8(REG_SYS_TRIGGER, 0x20)) return false;
  delay(1200);

  if (!checkChipId()) return false;
  if (!write8(REG_PAGE_ID, 0x00)) return false;

  // power normal
  if (!write8(REG_PWR_MODE, 0x00)) return false;
  delay(10);

  // ne force pas crystal externe
  write8(REG_SYS_TRIGGER, 0x00);
  delay(10);

  if (!setOperationMode(OprMode::NDOF)) return false;
  delay(20);

  return true;
}

bool GY_BNO055::checkChipId() {
  uint8_t id = 0;
  for (int i = 0; i < 5; i++) {
    if (read8(REG_CHIP_ID, id) && id == CHIP_ID) return true;
    delay(50);
  }
  return false;
}

bool GY_BNO055::setMode(OprMode mode) {
  return setOperationMode(mode);
}

bool GY_BNO055::setOperationMode(OprMode mode) {
  if (!write8(REG_OPR_MODE, (uint8_t)OprMode::CONFIGMODE)) return false;
  delay(25);
  if (!write8(REG_OPR_MODE, (uint8_t)mode)) return false;
  delay(25);
  return true;
}

bool GY_BNO055::write8(uint8_t reg, uint8_t val) {
  _wire->beginTransmission(_addr);
  _wire->write(reg);
  _wire->write(val);
  return (_wire->endTransmission() == 0);
}

bool GY_BNO055::read8(uint8_t reg, uint8_t &val) {
  _wire->beginTransmission(_addr);
  _wire->write(reg);
  if (_wire->endTransmission(false) != 0) return false;
  if (_wire->requestFrom((int)_addr, 1) != 1) return false;
  val = _wire->read();
  return true;
}

bool GY_BNO055::readLen(uint8_t reg, uint8_t *buf, size_t len) {
  _wire->beginTransmission(_addr);
  _wire->write(reg);
  if (_wire->endTransmission(false) != 0) return false;

  size_t got = _wire->requestFrom((int)_addr, (int)len);
  if (got != len) return false;

  for (size_t i = 0; i < len; i++) buf[i] = _wire->read();
  return true;
}

// Euler: 1 LSB = 1/16 degree, order: Heading(yaw), Roll, Pitch
bool GY_BNO055::readEulerDeg(Vector3 &out) {
  uint8_t b[6];
  if (!readLen(REG_EUL_DATA_X_LSB, b, 6)) return false;

  int16_t heading = u8ToS16(b[0], b[1]);
  int16_t roll    = u8ToS16(b[2], b[3]);
  int16_t pitch   = u8ToS16(b[4], b[5]);

  const float lsb_to_deg = 1.0f / 16.0f;
  out.x = (float)heading * lsb_to_deg; // yaw
  out.y = (float)roll    * lsb_to_deg; // roll
  out.z = (float)pitch   * lsb_to_deg; // pitch
  return true;
}

// Gyro: 1 LSB = 1/16 deg/s (default)
bool GY_BNO055::readGyroDPS(Vector3 &out) {
  uint8_t b[6];
  if (!readLen(REG_GYR_DATA_X_LSB, b, 6)) return false;

  int16_t x = u8ToS16(b[0], b[1]);
  int16_t y = u8ToS16(b[2], b[3]);
  int16_t z = u8ToS16(b[4], b[5]);

  const float lsb_to_dps = 1.0f / 16.0f;
  out.x = (float)x * lsb_to_dps;
  out.y = (float)y * lsb_to_dps;
  out.z = (float)z * lsb_to_dps;
  return true;
}

// Quaternion: 1 LSB = 1/2^14
bool GY_BNO055::readQuaternion(Quaternion &q) {
  uint8_t b[8];
  if (!readLen(REG_QUA_DATA_W_LSB, b, 8)) return false;

  int16_t w = u8ToS16(b[0], b[1]);
  int16_t x = u8ToS16(b[2], b[3]);
  int16_t y = u8ToS16(b[4], b[5]);
  int16_t z = u8ToS16(b[6], b[7]);

  const float scale = 1.0f / 16384.0f;
  q.w = (float)w * scale;
  q.x = (float)x * scale;
  q.y = (float)y * scale;
  q.z = (float)z * scale;
  return true;
}

bool GY_BNO055::getCalibrationStatus(uint8_t &sys, uint8_t &gyro, uint8_t &accel, uint8_t &mag) {
  uint8_t c = 0;
  if (!read8(REG_CALIB_STAT, c)) return false;
  sys   = (c >> 6) & 0x03;
  gyro  = (c >> 4) & 0x03;
  accel = (c >> 2) & 0x03;
  mag   = (c >> 0) & 0x03;
  return true;
}
