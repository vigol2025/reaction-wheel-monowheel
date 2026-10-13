#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "GY_BNO055.hpp"
#include "ESCMotor.hpp"

/*
 * TEST PHASE 1 (passage TRL3 -> TRL4) : un seul axe, un seul moteur,
 * boucle complete IMU -> PID -> ESC.
 *
 * BUT : prouver que la boucle logicielle fonctionne (lecture IMU correcte,
 * PID calcule un couple dans le bon sens, l'ESC reagit) sur un gabarit simple
 * (axe pivot + un seul ensemble rxn_wheel), PAS de faire tenir le monowheel
 * complet a 6.5 kg. D'apres la revue du budget de couple
 * (voir docs/04-revue-budget-de-couple.md), le
 * moteur A2212 retenu delivre ~0.10-0.20 Nm alors que le calcul d'origine
 * demandait ~1.17 Nm/moteur pour le robot final : ce test valide seulement
 * l'architecture logicielle, pas la capacite a stabiliser le robot final.
 *
 * TEMPS REEL : la boucle est cadencee par vTaskDelayUntil() (FreeRTOS, deja
 * present sous l'Arduino Core ESP32 -- loop() tourne comme une tache FreeRTOS)
 * au lieu d'un polling actif sur micros(). Un depassement de budget de boucle
 * (deadline manquee) est detecte et signale, au lieu d'etre ignore en silence.
 * Conception temps reel detaillee : firmware/README.md.
 *
 * SUIVI TEMPS REEL : une ligne JSON ({"angle":...,"rateDps":...,...}) est
 * envoyee a chaque log, au format attendu par le plugin "Serial Port" de
 * PlotJuggler 4 (protocole "json" dans sa boite de dialogue de connexion).
 * PlotJuggler > Start > Serial Port > choisir le port, 115200 bauds,
 * protocole "json" > Start. Les champs angle/rateDps/u/pulseUs/loopWorkUs/
 * overruns apparaissent comme series a glisser dans une vue.
 *
 * Compilation/upload de CE fichier uniquement (l'autre environnement compile
 * main.cpp, la version complete a 4 roues) :
 *   pio run -e test_single_axis -t upload -t monitor
 */

// ===== I2C ESP32 =====
static constexpr int I2C_SDA = 21;
static constexpr int I2C_SCL = 22;

// ===== Boucle de controle =====
static constexpr uint32_t LOOP_HZ = 200;
static constexpr uint32_t LOOP_DT_US = 1000000UL / LOOP_HZ;
static constexpr uint32_t LOG_MS = 100;

// >>> A REGLER selon le montage physique : quel axe ce moteur doit-il corriger ?
enum class Axis { ROLL, PITCH };
static constexpr Axis TEST_AXIS = Axis::ROLL;

// >>> A REGLER selon ton cablage reel. Valeur par defaut = w1 de la version 4 roues
// (main.cpp), pratique si tu reutilises le meme ESC/pin que le premier moteur du
// montage complet.
static constexpr int ESC_PIN = 18;
static constexpr int ESC_CHANNEL = 0;

// Sens de correction. Si au premier essai le volant AGGRAVE l'inclinaison au lieu
// de la corriger (retour positif au lieu de negatif), passe cette valeur a -1.
static constexpr int INVERT = 1;

// ===== Securite =====
// Plus serre que les 45 deg de la version finale : gabarit de test plus fragile,
// on coupe plus tot par prudence. Ajuste si besoin une fois le montage verifie.
static constexpr float MAX_ANGLE_DEG = 30.0f;

// ===== PID (point de depart = memes gains que la version 4 roues, a affiner
// empiriquement pendant ce test avant de les reporter dans main.cpp) =====
struct PID {
  float kp = 1.8f, ki = 0.0f, kd = 0.10f;
  float integ = 0.0f, integLimit = 40.0f;
};
static PID pid;

static float pidStep(float errDeg, float rateRadS, float dt) {
  pid.integ += errDeg * dt;
  pid.integ = constrain(pid.integ, -pid.integLimit, pid.integLimit);
  return pid.kp * errDeg + pid.ki * pid.integ - pid.kd * rateRadS;
}

GY_BNO055 imu;
ESCMotor *esc = nullptr;

// ===== Ordonnancement temps reel (FreeRTOS) =====
static TickType_t lastWakeTick;
static const TickType_t LOOP_PERIOD_TICKS = pdMS_TO_TICKS(1000 / LOOP_HZ); // 5 ticks @200Hz (tick FreeRTOS = 1ms par defaut sur ESP32 Arduino)

static uint32_t lastLoopUs = 0;
static uint32_t lastLogMs = 0;
static uint32_t overrunCount = 0;

void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println("\n=== TEST PHASE 1 : 1 axe, 1 moteur, IMU -> PID -> ESC ===");
  Serial.println("ESC bidirectionnel: neutre=1500us | reverse=1000 | forward=2000");

  if (!imu.begin(Wire, 0x28, I2C_SDA, I2C_SCL, 400000)) {
    Serial.println("ERREUR: BNO055 introuvable (0x28/0x29).");
    while (true) delay(1000);
  }
  imu.setMode(GY_BNO055::OprMode::NDOF);
  Serial.print("BNO055 OK. Addr=0x");
  Serial.println(imu.address(), HEX);

  ESCMotor::Config escCfg;
  escCfg.escPin = ESC_PIN;
  escCfg.ledcChannel = ESC_CHANNEL;
  escCfg.pwmFreqHz = 50;
  escCfg.pwmResolutionBits = 16;
  escCfg.pulseMinUs = 1000;
  escCfg.pulseMaxUs = 2000;
  escCfg.pulseArmUs = 1500;
  escCfg.armTimeMs = 2500;
  escCfg.failsafeMs = 500;

  esc = new ESCMotor(escCfg);
  esc->begin();

  Serial.println("Arming ESC... (neutre pendant armTimeMs, ne pas toucher au moteur)");
  lastLoopUs = micros();
  lastWakeTick = xTaskGetTickCount();
}

void loop() {
  if (!esc) {
    vTaskDelayUntil(&lastWakeTick, LOOP_PERIOD_TICKS);
    return;
  }

  const uint32_t iterStartUs = micros();
  const uint32_t dtUs = iterStartUs - lastLoopUs;
  lastLoopUs = iterStartUs;
  const float dt = (float)dtUs / 1e6f;

  esc->update(); // gere arming + failsafe

  GY_BNO055::Vector3 eul, gyr;
  const bool okE = imu.readEulerDeg(eul);
  const bool okG = imu.readGyroDPS(gyr);

  float angleDeg = 0.0f, rateDps = 0.0f, uApplied = 0.0f;
  bool imuOk = okE && okG;

  if (!imuOk) {
    esc->neutral();
  } else {
    // Euler: eul.x=yaw, eul.y=roll, eul.z=pitch (voir GY_BNO055.hpp)
    angleDeg = (TEST_AXIS == Axis::ROLL) ? eul.y : eul.z;
    rateDps  = (TEST_AXIS == Axis::ROLL) ? gyr.x : gyr.y;

    if (fabsf(angleDeg) > MAX_ANGLE_DEG) {
      esc->neutral();
      pid.integ = 0.0f;
    } else {
      const float err = -angleDeg; // consigne = 0
      const float d2r = 3.1415926f / 180.0f;
      const float rateRadS = rateDps * d2r;

      float tau = pidStep(err, rateRadS, dt);
      tau = constrain(tau, -1.0f, 1.0f);

      // memes constantes que la version 4 roues (kTauToU=0.25) pour rester comparable
      uApplied = constrain(0.25f * tau * (float)INVERT, -1.0f, 1.0f);
      const int pulseUs = 1500 + (int)(uApplied * 500.0f);
      esc->setPulseUs(pulseUs);
    }
  }

  // --- Detection de deadline manquee (concept temps reel : ne jamais deriver en silence) ---
  const uint32_t workUs = micros() - iterStartUs;
  if (workUs > LOOP_DT_US) {
    overrunCount++;
  }

  const uint32_t nowMs = millis();
  if (nowMs - lastLogMs >= LOG_MS) {
    lastLogMs = nowMs;

    uint8_t csys, cgyro, cacc, cmag;
    imu.getCalibrationStatus(csys, cgyro, cacc, cmag);

    Serial.print("CALIB "); Serial.print((int)csys); Serial.print("/");
    Serial.print((int)cgyro); Serial.print("/");
    Serial.print((int)cacc); Serial.print("/");
    Serial.print((int)cmag);

    Serial.print(" | axe="); Serial.print(TEST_AXIS == Axis::ROLL ? "roll" : "pitch");
    Serial.print(" | angle="); Serial.print(angleDeg, 2);
    Serial.print(" | rateDps="); Serial.print(rateDps, 2);
    Serial.print(" | u="); Serial.print(uApplied, 2);
    Serial.print(" | pulse="); Serial.print(esc->pulseUs());
    Serial.print(" | overruns="); Serial.println(overrunCount);

    // --- Ligne JSON pour PlotJuggler 4 (plugin Serial Port, protocole "json") ---
    // Le splitter de PlotJuggler capture tout ce qui est entre '{' et '}', peu
    // importe le texte autour (la ligne CALIB au-dessus ne le perturbe pas).
    Serial.print("{\"angle\":"); Serial.print(angleDeg, 3);
    Serial.print(",\"rateDps\":"); Serial.print(rateDps, 3);
    Serial.print(",\"u\":"); Serial.print(uApplied, 3);
    Serial.print(",\"pulseUs\":"); Serial.print(esc->pulseUs());
    Serial.print(",\"loopWorkUs\":"); Serial.print(workUs);
    Serial.print(",\"overruns\":"); Serial.print(overrunCount);
    Serial.println("}");
  }

  // --- Ordonnancement temps reel : attente precise jusqu'au prochain tick, ---
  // --- pas un polling actif. Rattrape automatiquement les depassements. ---
  vTaskDelayUntil(&lastWakeTick, LOOP_PERIOD_TICKS);
}
