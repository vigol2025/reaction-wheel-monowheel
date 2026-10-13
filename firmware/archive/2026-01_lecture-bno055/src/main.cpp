#include <Arduino.h>
#include "GY-BNO055.hpp"

// --- I2C pins ESP32 (adapte si besoin) ---
static constexpr int I2C_SDA = 21;
static constexpr int I2C_SCL = 22;

// --- seuils détection mouvement ---
// static constexpr float ACC_MOVEMENT_MS2 = 1.2f;   // ~0.12g
// static constexpr float GYR_MOVEMENT_DPS = 15.0f;  // deg/s
// static constexpr float ANGLE_CHANGE_DEG = 5.0f;   // deg

static constexpr float ACC_MOVEMENT_MS2 = 0.25f;  // plus sensible
static constexpr float GYR_MOVEMENT_DPS = 3.0f;   // plus sensible
static constexpr float ANGLE_CHANGE_DEG = 1.0f;   // plus sensible

GY_BNO055 imu;

static float wrap180(float a) {
  while (a > 180.f) a -= 360.f;
  while (a < -180.f) a += 360.f;
  return a;
}

void setup() {
  Serial.begin(115200);
  delay(200);

  Serial.println("\n=== ESP32 + GY-BNO055 (BNO055) I2C Demo (PlatformIO) ===");

  if (!imu.begin(Wire, 0x28, I2C_SDA, I2C_SCL, 400000)) {
    Serial.println("ERREUR: BNO055 introuvable sur 0x28/0x29. Verifie cablage SDA/SCL, alim, adresse.");
    while (true) delay(1000);
  }

  Serial.print("BNO055 OK. Adresse I2C detectee: 0x");
  Serial.println(imu.address(), HEX);

  // Mode fusion complet (acc + gyro + mag) => angles + quaternion stables
  imu.setMode(GY_BNO055::OprMode::NDOF);

  Serial.println("Bouge le capteur pour voir accel/gyro/mag + angles Euler + quaternion.");
  Serial.println("Astuce calibration: fais des mouvements en 8 (mag), rotation lente, etc.");
}

void loop() {
  static uint32_t t0 = 0;
  const uint32_t now = millis();
  const uint32_t dt = now - t0;
  if (dt < 50) return; // ~20 Hz
  t0 = now;

  GY_BNO055::Vector3 acc, lin, grv, gyr, mag, eul;
  GY_BNO055::Quaternion q;

  bool ok =
    imu.readAccelMS2(acc) &&
    imu.readLinAccelMS2(lin) &&
    imu.readGravityMS2(grv) &&
    imu.readGyroDPS(gyr) &&
    imu.readMagUT(mag) &&
    imu.readEulerDeg(eul) &&
    imu.readQuaternion(q);

  if (!ok) {
    Serial.println("Lecture I2C echouee (bruit I2C/cablage?).");
    return;
  }

  uint8_t sysStatus, selfTest, sysError;
  if (imu.getSystemStatus(sysStatus, selfTest, sysError)) {
    Serial.print("SYS_STATUS="); Serial.print(sysStatus);
    Serial.print(" SELFTEST=0x"); Serial.print(selfTest, HEX);
    Serial.print(" SYS_ERR="); Serial.println(sysError);
  }


  // --- Calibration status ---
  uint8_t csys, cgyro, cacc, cmag;
  imu.getCalibrationStatus(csys, cgyro, cacc, cmag);

  // --- Mouvement detecté ? ---
  static GY_BNO055::Vector3 prevEul{0,0,0};
  static bool first = true;

  float dYaw=0, dRoll=0, dPitch=0;
  if (!first) {
    dYaw   = wrap180(eul.x - prevEul.x);
    dRoll  = wrap180(eul.y - prevEul.y);
    dPitch = wrap180(eul.z - prevEul.z);
  }
  first = false;
  prevEul = eul;

  auto absf = [](float v){ return v < 0 ? -v : v; };

  bool accMove = (absf(lin.x) > ACC_MOVEMENT_MS2) || (absf(lin.y) > ACC_MOVEMENT_MS2) || (absf(lin.z) > ACC_MOVEMENT_MS2);
  bool gyrMove = (absf(gyr.x) > GYR_MOVEMENT_DPS) || (absf(gyr.y) > GYR_MOVEMENT_DPS) || (absf(gyr.z) > GYR_MOVEMENT_DPS);
  bool angMove = (absf(dYaw) > ANGLE_CHANGE_DEG) || (absf(dRoll) > ANGLE_CHANGE_DEG) || (absf(dPitch) > ANGLE_CHANGE_DEG);

  // --- Affichage complet ---
  Serial.println("--------------------------------------------------");

  Serial.print("CALIB sys/gyro/acc/mag = ");
  Serial.print((int)csys); Serial.print("/");
  Serial.print((int)cgyro); Serial.print("/");
  Serial.print((int)cacc); Serial.print("/");
  Serial.println((int)cmag);

  Serial.print("ACC (m/s^2)     : ");
  Serial.print(acc.x, 3); Serial.print(", ");
  Serial.print(acc.y, 3); Serial.print(", ");
  Serial.println(acc.z, 3);

  Serial.print("LIN ACC (m/s^2) : ");
  Serial.print(lin.x, 3); Serial.print(", ");
  Serial.print(lin.y, 3); Serial.print(", ");
  Serial.println(lin.z, 3);

  Serial.print("GRAV (m/s^2)    : ");
  Serial.print(grv.x, 3); Serial.print(", ");
  Serial.print(grv.y, 3); Serial.print(", ");
  Serial.println(grv.z, 3);

  Serial.print("GYRO (deg/s)    : ");
  Serial.print(gyr.x, 3); Serial.print(", ");
  Serial.print(gyr.y, 3); Serial.print(", ");
  Serial.println(gyr.z, 3);

  Serial.print("MAG (uT)        : ");
  Serial.print(mag.x, 3); Serial.print(", ");
  Serial.print(mag.y, 3); Serial.print(", ");
  Serial.println(mag.z, 3);

  // Euler: yaw/roll/pitch
  Serial.print("EULER (deg) yaw/roll/pitch : ");
  Serial.print(eul.x, 2); Serial.print(", ");
  Serial.print(eul.y, 2); Serial.print(", ");
  Serial.println(eul.z, 2);

  Serial.print("dEuler (deg) dYaw/dRoll/dPitch : ");
  Serial.print(dYaw, 2); Serial.print(", ");
  Serial.print(dRoll, 2); Serial.print(", ");
  Serial.println(dPitch, 2);

  Serial.print("QUAT (w,x,y,z)  : ");
  Serial.print(q.w, 4); Serial.print(", ");
  Serial.print(q.x, 4); Serial.print(", ");
  Serial.print(q.y, 4); Serial.print(", ");
  Serial.println(q.z, 4);

  if (accMove || gyrMove || angMove) {
    Serial.print(">>> MOUVEMENT DETECTE: ");
    if (accMove) Serial.print("[ACC] ");
    if (gyrMove) Serial.print("[GYRO] ");
    if (angMove) Serial.print("[ANGLE] ");
    Serial.println();
  } else {
    Serial.println("Mouvement faible (en dessous des seuils).");
  }
}
