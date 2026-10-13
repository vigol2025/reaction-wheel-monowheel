#include <Arduino.h>

// ========= CONFIG =========
static constexpr int ESC_PIN = 18;     // <- change si besoin
static constexpr int LEDC_CH = 0;

static constexpr int PWM_FREQ = 50;    // 50 Hz servo
static constexpr int PWM_RES  = 16;    // 16 bits

static constexpr int PULSE_MIN = 1000;
static constexpr int PULSE_MAX = 2000;
static constexpr int PULSE_NEU = 1500;

// ========= PWM HELPERS =========
static uint32_t pulseUsToDuty(int pulseUs) {
  pulseUs = constrain(pulseUs, PULSE_MIN, PULSE_MAX);
  const uint32_t periodUs = 1000000UL / PWM_FREQ;           // 20000 us
  const uint32_t maxDuty  = (1UL << PWM_RES) - 1UL;
  return (uint32_t)(((uint64_t)pulseUs * (uint64_t)maxDuty) / (uint64_t)periodUs);
}

static void writePulseUs(int pulseUs) {
  ledcWrite(LEDC_CH, pulseUsToDuty(pulseUs));
}

// ========= MAIN =========
void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println("\n=== ESC Bidirectional Quick Test (ESP32 LEDC) ===");
  Serial.println("Observe le sens moteur:");
  Serial.println("  1500us = neutre (stop)");
  Serial.println("  1600us = sens A");
  Serial.println("  1400us = sens B (si ESC bidirectionnel)");
  Serial.println("ATTENTION: retire l'helice / fixe le moteur.");

  // setup LEDC
  ledcSetup(LEDC_CH, PWM_FREQ, PWM_RES);
  ledcAttachPin(ESC_PIN, LEDC_CH);

  // ARMING: neutre 1500us pendant ~3s
  Serial.println("Arming: 1500us pendant 3s...");
  writePulseUs(PULSE_NEU);
  delay(3000);

  Serial.println("Test sequence starts in 2s...");
  delay(2000);
}

void loop() {
  // 1) neutre
  Serial.println("CMD: 1500us (NEUTRAL) 2s");
  writePulseUs(1500);
  delay(2000);

  // 2) forward
  Serial.println("CMD: 1600us (DIR A) 3s");
  writePulseUs(1600);
  delay(3000);

  // 3) stop
  Serial.println("CMD: 1500us (NEUTRAL) 2s");
  writePulseUs(1500);
  delay(2000);

  // 4) reverse test
  Serial.println("CMD: 1400us (DIR B?) 3s");
  writePulseUs(1400);
  delay(3000);

  // 5) stop
  Serial.println("CMD: 1500us (NEUTRAL) 3s");
  writePulseUs(1500);
  delay(3000);

  Serial.println("---- Repeat ----");
}
