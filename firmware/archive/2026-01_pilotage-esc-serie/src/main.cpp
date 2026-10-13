#include <Arduino.h>
#include "esc_motor.hpp"

static ESCMotor* esc = nullptr;

static const uint32_t TELEMETRY_MS = 200;
static uint32_t lastTelMs = 0;

// Buffer pour accumuler la ligne reçue (style readline)
static String rxLine;

void setup() {
  Serial.begin(115200);
  delay(200);

  ESCMotor::Config cfg;
  cfg.escPin = 18;
  cfg.ledcChannel = 0;
  cfg.pwmFreqHz = 50;
  cfg.pwmResolutionBits = 16;
  cfg.pulseMinUs = 1000;
  cfg.pulseMaxUs = 2000;
  cfg.armTimeMs = 2000;
  cfg.failsafeMs = 500;

  esc = new ESCMotor(cfg);
  esc->begin();

  Serial.println("READY");
  Serial.println("Commands: T,0.10  |  P,1500  |  X");
  Serial.println("Terminator expected: LF (\\n) or CRLF (\\r\\n)");
}

static void readSerialLinesAndProcess() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    // Fin de ligne sur \n (Linux/MATLAB LF, ou Windows CRLF -> on gère \r dans handleCommandLine)
    if (c == '\n') {
      if (esc) esc->handleCommandLine(rxLine, Serial);
      rxLine = ""; // reset buffer
    } else {
      // Accumule (y compris \r si CRLF, on le nettoie ensuite)
      rxLine += c;

      // sécurité : évite buffer infini si garbage
      if (rxLine.length() > 120) {
        Serial.println("ERR,LINE_TOO_LONG");
        rxLine = "";
      }
    }
  }
}

void loop() {
  if (!esc) return;

  // arming + failsafe
  esc->update();

  // "readline" en continu
  readSerialLinesAndProcess();

  // télémétrie
  const uint32_t now = millis();
  if (now - lastTelMs >= TELEMETRY_MS) {
    lastTelMs = now;
    Serial.print("STAT,armed=");
    Serial.print(esc->isArmed() ? 1 : 0);
    Serial.print(",thr=");
    Serial.print(esc->throttle(), 3);
    Serial.print(",pulse=");
    Serial.println(esc->pulseUs());
  }
}
