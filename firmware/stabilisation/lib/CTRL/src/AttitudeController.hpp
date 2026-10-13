#pragma once
#include <Arduino.h>

/**
 * AttitudeController:
 * - stabilise roll/pitch (consigne = 0)
 * - utilise gyro pour amortissement
 * - mixing 4 roues à ±45°
 * - sort u1..u4 ∈ [-1,+1]
 */
class AttitudeController {
public:
  struct PID {
    float kp=0, ki=0, kd=0;
    float integ=0;
    float integLimit=50.0f;
  };

  struct Config {
    PID roll;
    PID pitch;

    float tauMax = 1.0f;     // limite interne
    float kTauToU = 0.25f;   // conversion tau -> u
    float uMax = 1.0f;

    float cos45 = 0.70710678f;

    float maxAngleDeg = 45.0f; // sécurité
  };

  explicit AttitudeController(const Config& cfg);

  void reset();

  void step(float rollDeg, float pitchDeg,
            float gxDps, float gyDps,
            float dt,
            float &u1, float &u2, float &u3, float &u4);

private:
  Config cfg_;

  float pidStep_(PID &p, float errDeg, float rateRadS, float dt);
  void mix45_(float tauX, float tauY, float &t1, float &t2, float &t3, float &t4);
};
