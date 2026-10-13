#include "AttitudeController.hpp"

AttitudeController::AttitudeController(const Config& cfg) : cfg_(cfg) {}

void AttitudeController::reset() {
  cfg_.roll.integ = 0.0f;
  cfg_.pitch.integ = 0.0f;
}

float AttitudeController::pidStep_(PID &p, float errDeg, float rateRadS, float dt) {
  p.integ += errDeg * dt;
  p.integ = constrain(p.integ, -p.integLimit, p.integLimit);

  // amortissement gyro: -kd*omega
  return p.kp * errDeg + p.ki * p.integ - p.kd * rateRadS;
}

void AttitudeController::mix45_(float tauX, float tauY, float &t1, float &t2, float &t3, float &t4) {
  const float c = cfg_.cos45;
  const float k = 1.0f / (2.0f * c);

  t1 = ( tauX + tauY) * k;
  t2 = (-tauX + tauY) * k;
  t3 = (-tauX - tauY) * k;
  t4 = ( tauX - tauY) * k;
}

void AttitudeController::step(float rollDeg, float pitchDeg,
                              float gxDps, float gyDps,
                              float dt,
                              float &u1, float &u2, float &u3, float &u4) {
  // sécurité
  if (fabsf(rollDeg) > cfg_.maxAngleDeg || fabsf(pitchDeg) > cfg_.maxAngleDeg) {
    u1=u2=u3=u4=0;
    reset();
    return;
  }

  // consigne = 0
  const float er = -rollDeg;
  const float ep = -pitchDeg;

  // gyro deg/s -> rad/s
  const float d2r = 3.1415926f / 180.0f;
  const float wx = gxDps * d2r;
  const float wy = gyDps * d2r;

  float tauX = pidStep_(cfg_.roll,  er, wx, dt);
  float tauY = pidStep_(cfg_.pitch, ep, wy, dt);

  tauX = constrain(tauX, -cfg_.tauMax, cfg_.tauMax);
  tauY = constrain(tauY, -cfg_.tauMax, cfg_.tauMax);

  float t1,t2,t3,t4;
  mix45_(tauX, tauY, t1,t2,t3,t4);

  u1 = constrain(cfg_.kTauToU * t1, -cfg_.uMax, cfg_.uMax);
  u2 = constrain(cfg_.kTauToU * t2, -cfg_.uMax, cfg_.uMax);
  u3 = constrain(cfg_.kTauToU * t3, -cfg_.uMax, cfg_.uMax);
  u4 = constrain(cfg_.kTauToU * t4, -cfg_.uMax, cfg_.uMax);
}
