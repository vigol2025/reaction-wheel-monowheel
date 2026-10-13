#include <Arduino.h>
#include "GY_BNO055.hpp"
#include "ReactionWheelArray.hpp"
#include "AttitudeController.hpp"

// ===== I2C ESP32 =====
static constexpr int I2C_SDA = 21;
static constexpr int I2C_SCL = 22;

// ===== Control loop =====
static constexpr uint32_t LOOP_HZ = 200;
static constexpr uint32_t LOOP_DT_US = 1000000UL / LOOP_HZ;

static constexpr uint32_t LOG_MS = 100;
static uint32_t lastLogMs = 0;
static uint32_t lastLoopUs = 0;

// ===== IMU =====
GY_BNO055 imu;

// ===== Pointers (construction propre après config) =====
ReactionWheelArray *wheels = nullptr;
AttitudeController *ctrl = nullptr;

void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println("\n=== Reaction Wheel Stabilization (4x ±45°) | ESP32 + BNO055 ===");
  Serial.println("ESC bidirectionnels: neutre=1500us | reverse=1000 | forward=2000");

  // -------- IMU init --------
  if (!imu.begin(Wire, 0x28, I2C_SDA, I2C_SCL, 400000)) {
    Serial.println("ERREUR: BNO055 introuvable (0x28/0x29).");
    while (true) delay(1000);
  }
  imu.setMode(GY_BNO055::OprMode::NDOF);

  Serial.print("BNO055 OK. Addr=0x");
  Serial.println(imu.address(), HEX);

  // -------- Wheels config --------
  ReactionWheelArray::Config rwCfg;
  rwCfg.escBase.pwmFreqHz = 50;
  rwCfg.escBase.pwmResolutionBits = 16;
  rwCfg.escBase.armTimeMs = 2500;
  rwCfg.escBase.failsafeMs = 500;

  rwCfg.pulseMinUs = 1000;
  rwCfg.pulseMaxUs = 2000;
  rwCfg.pulseNeutralUs = 1500;
  rwCfg.deltaMaxUs = 500; // pleine plage (u=-1..+1)

// >>> Mets ici tes vraies pins ESC + channels LEDC
rwCfg.w1 = ReactionWheelArray::WheelConfig(18, 0, 0);
rwCfg.w2 = ReactionWheelArray::WheelConfig(19, 1, 0);
rwCfg.w3 = ReactionWheelArray::WheelConfig(21, 2, 0);
rwCfg.w4 = ReactionWheelArray::WheelConfig(22, 3, 0);

// Inversion si nécessaire (à régler au test)
// rwCfg.w2.invert = 1;


  wheels = new ReactionWheelArray(rwCfg);
  wheels->begin();

  // -------- Controller config --------
  AttitudeController::Config cCfg;
  cCfg.roll.kp = 1.8f;
  cCfg.roll.ki = 0.0f;
  cCfg.roll.kd = 0.10f;
  cCfg.roll.integLimit = 40.0f;

  cCfg.pitch.kp = 1.8f;
  cCfg.pitch.ki = 0.0f;
  cCfg.pitch.kd = 0.10f;
  cCfg.pitch.integLimit = 40.0f;

  cCfg.tauMax = 1.0f;
  cCfg.kTauToU = 0.25f;
  cCfg.uMax = 1.0f;

  cCfg.maxAngleDeg = 45.0f;

  ctrl = new AttitudeController(cCfg);

  Serial.println("Arming ESC... (neutre pendant armTimeMs)");
  lastLoopUs = micros();
}

void loop() {
  if (!wheels || !ctrl) return;

  const uint32_t nowUs = micros();
  if (nowUs - lastLoopUs < LOOP_DT_US) return;

  const uint32_t dtUs = nowUs - lastLoopUs;
  lastLoopUs = nowUs;
  const float dt = (float)dtUs / 1e6f;

  // update arming/failsafe ESC
  wheels->update();

  // --- IMU read ---
  GY_BNO055::Vector3 eul, gyr;
  GY_BNO055::Quaternion q;

  const bool okE = imu.readEulerDeg(eul);
  const bool okG = imu.readGyroDPS(gyr);
  const bool okQ = imu.readQuaternion(q);

  if (!okE || !okG || !okQ) {
    wheels->neutralAll();
    return;
  }

  // Euler: yaw/roll/pitch
  const float yawDeg   = eul.x;
  const float rollDeg  = eul.y;
  const float pitchDeg = eul.z;

  float u1,u2,u3,u4;
  ctrl->step(rollDeg, pitchDeg, gyr.x, gyr.y, dt, u1,u2,u3,u4);

  // Apply
  wheels->setCommand(u1,u2,u3,u4);

  // --- Logs ---
  const uint32_t nowMs = millis();
  if (nowMs - lastLogMs >= LOG_MS) {
    lastLogMs = nowMs;

    uint8_t csys,cgyro,cacc,cmag;
    imu.getCalibrationStatus(csys,cgyro,cacc,cmag);

    Serial.print("CALIB "); Serial.print((int)csys); Serial.print("/");
    Serial.print((int)cgyro); Serial.print("/");
    Serial.print((int)cacc); Serial.print("/");
    Serial.print((int)cmag);

    Serial.print(" | EUL yaw/roll/pitch=");
    Serial.print(yawDeg,1); Serial.print(",");
    Serial.print(rollDeg,1); Serial.print(",");
    Serial.print(pitchDeg,1);

    Serial.print(" | GYR x/y/z(dps)=");
    Serial.print(gyr.x,1); Serial.print(",");
    Serial.print(gyr.y,1); Serial.print(",");
    Serial.print(gyr.z,1);

    Serial.print(" | QUAT wxyz=");
    Serial.print(q.w,3); Serial.print(",");
    Serial.print(q.x,3); Serial.print(",");
    Serial.print(q.y,3); Serial.print(",");
    Serial.print(q.z,3);

    Serial.print(" | u=");
    Serial.print(u1,2); Serial.print(",");
    Serial.print(u2,2); Serial.print(",");
    Serial.print(u3,2); Serial.print(",");
    Serial.print(u4,2);

    Serial.print(" | pulse=");
    Serial.print(wheels->pulse1()); Serial.print(",");
    Serial.print(wheels->pulse2()); Serial.print(",");
    Serial.print(wheels->pulse3()); Serial.print(",");
    Serial.println(wheels->pulse4());
  }
}
