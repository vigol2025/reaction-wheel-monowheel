#pragma once
#include <Arduino.h>

/**
 * ESCMotor: contrôle d'un ESC RC via LEDC (ESP32).
 * - ESC bidirectionnel: neutre = pulseArmUs (souvent 1500us)
 * - plage: pulseMinUs..pulseMaxUs (souvent 1000..2000us)
 * - arming: maintenir pulseArmUs pendant armTimeMs
 * - failsafe: revenir au neutre si plus de commande
 */
class ESCMotor {
public:
  struct Config {
    int escPin = 18;
    int ledcChannel = 0;

    int pwmFreqHz = 50;            // 50 Hz
    int pwmResolutionBits = 16;

    int pulseMinUs = 1000;
    int pulseMaxUs = 2000;
    int pulseArmUs = 1500;         // neutre (arming + stop)

    uint32_t armTimeMs = 2000;
    uint32_t failsafeMs = 500;
  };

  explicit ESCMotor(const Config& cfg);

  void begin();
  void update();

  void setPulseUs(int pulseUs);  // 1000..2000
  void neutral();                // pulseArmUs

  bool isArmed() const { return armed_; }
  int pulseUs() const { return pulseUsCmd_; }

private:
  Config cfg_;
  int pulseUsCmd_ = 1500;

  bool armed_ = false;
  uint32_t bootMs_ = 0;
  uint32_t lastCmdMs_ = 0;

  void applyPulseUs_(int pulseUs);
  uint32_t pulseUsToDuty_(int pulseUs) const;
};
