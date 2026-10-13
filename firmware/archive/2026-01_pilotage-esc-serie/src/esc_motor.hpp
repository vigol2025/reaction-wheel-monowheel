#pragma once
#include <Arduino.h>

/**
 * ESCMotor: contrôle d'un ESC RC (signal servo 50 Hz, pulse 1000-2000 us)
 * via LEDC hardware ESP32 (stable et précis).
 */
class ESCMotor {
public:
  struct Config {
    int escPin = 18;               // GPIO vers signal ESC
    int ledcChannel = 0;           // canal LEDC
    int pwmFreqHz = 50;            // 50 Hz (période 20 ms)
    int pwmResolutionBits = 16;    // résolution duty
    int pulseMinUs = 1000;         // pulse mini
    int pulseMaxUs = 2000;         // pulse maxi
    uint32_t armTimeMs = 2000;     // arming
    uint32_t failsafeMs = 500;     // stop si pas de commande récente
  };

  explicit ESCMotor(const Config& cfg);

  void begin();      // init LEDC + démarrer à min
  void update();     // arming + failsafe (à appeler souvent)

  void setThrottle(float throttle01); // 0..1
  void setPulseUs(int pulseUs);       // 1000..2000
  void stop();                        // throttle=0

  // Lit une ligne texte déjà complète (sans \n) et applique la commande
  bool handleCommandLine(const String& lineRaw, Stream& out);

  bool isArmed() const { return armed_; }
  float throttle() const { return throttleCmd_; }
  int pulseUs() const { return pulseUsCmd_; }

private:
  Config cfg_;

  float throttleCmd_ = 0.0f;
  int pulseUsCmd_ = 1000;

  bool armed_ = false;
  uint32_t bootMs_ = 0;
  uint32_t lastCmdMs_ = 0;

  void applyPulseUs_(int pulseUs);
  uint32_t pulseUsToDuty_(int pulseUs) const;
  float clamp01_(float v) const;
};
