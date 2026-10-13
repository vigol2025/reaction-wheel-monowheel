#pragma once
#include <Arduino.h>
#include <Wire.h>

class GY_BNO055 {
public:
  struct Vector3 { float x, y, z; };
  struct Quaternion { float w, x, y, z; };

  enum class OprMode : uint8_t {
    CONFIGMODE = 0x00,
    NDOF       = 0x0C
  };

  GY_BNO055();

  bool begin(TwoWire &wire = Wire, uint8_t i2cAddr = 0x28, int sda = -1, int scl = -1, uint32_t freq = 400000);
  bool setMode(OprMode mode);

  // Euler: out.x=yaw, out.y=roll, out.z=pitch (degrés)
  bool readEulerDeg(Vector3 &out);

  // Gyro: deg/s
  bool readGyroDPS(Vector3 &out);

  // Quaternion: w,x,y,z (normalisé)
  bool readQuaternion(Quaternion &q);

  bool getCalibrationStatus(uint8_t &sys, uint8_t &gyro, uint8_t &accel, uint8_t &mag);

  uint8_t address() const { return _addr; }

private:
  TwoWire *_wire = nullptr;
  uint8_t _addr = 0x28;

  bool checkChipId();
  bool write8(uint8_t reg, uint8_t val);
  bool read8(uint8_t reg, uint8_t &val);
  bool readLen(uint8_t reg, uint8_t *buf, size_t len);

  bool setOperationMode(OprMode mode);

  static int16_t u8ToS16(uint8_t lsb, uint8_t msb) { return (int16_t)((msb << 8) | lsb); }

  static constexpr uint8_t REG_CHIP_ID      = 0x00;
  static constexpr uint8_t CHIP_ID          = 0xA0;
  static constexpr uint8_t REG_PAGE_ID      = 0x07;
  static constexpr uint8_t REG_OPR_MODE     = 0x3D;
  static constexpr uint8_t REG_PWR_MODE     = 0x3E;
  static constexpr uint8_t REG_SYS_TRIGGER  = 0x3F;
  static constexpr uint8_t REG_CALIB_STAT   = 0x35;

  static constexpr uint8_t REG_EUL_DATA_X_LSB = 0x1A; // 6 bytes
  static constexpr uint8_t REG_GYR_DATA_X_LSB = 0x14; // 6 bytes
  static constexpr uint8_t REG_QUA_DATA_W_LSB = 0x20; // 8 bytes
};
