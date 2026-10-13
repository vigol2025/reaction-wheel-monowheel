#include "ESCMotor.hpp"

ESCMotor::ESCMotor(const Config& cfg) : cfg_(cfg) {
  pulseUsCmd_ = cfg_.pulseArmUs;
}

void ESCMotor::begin() {
  ledcSetup(cfg_.ledcChannel, cfg_.pwmFreqHz, cfg_.pwmResolutionBits);
  ledcAttachPin(cfg_.escPin, cfg_.ledcChannel);

  bootMs_ = millis();
  lastCmdMs_ = bootMs_;
  armed_ = false;

  neutral(); // démarre au neutre (important pour ESC bidirectionnel)
}

void ESCMotor::update() {
  const uint32_t now = millis();

  // Arming: tenir neutre pendant armTimeMs
  if (!armed_) {
    applyPulseUs_(cfg_.pulseArmUs);
    if (now - bootMs_ >= cfg_.armTimeMs) {
      armed_ = true;
      lastCmdMs_ = now;
    }
    return;
  }

  // Failsafe: retour neutre si plus de commande
  if (cfg_.failsafeMs > 0 && (now - lastCmdMs_ > cfg_.failsafeMs)) {
    neutral();
    lastCmdMs_ = now;
  }
}

void ESCMotor::setPulseUs(int pulseUs) {
  pulseUs = constrain(pulseUs, cfg_.pulseMinUs, cfg_.pulseMaxUs);
  pulseUsCmd_ = pulseUs;
  applyPulseUs_(pulseUsCmd_);
  lastCmdMs_ = millis();
}

void ESCMotor::neutral() {
  pulseUsCmd_ = constrain(cfg_.pulseArmUs, cfg_.pulseMinUs, cfg_.pulseMaxUs);
  applyPulseUs_(pulseUsCmd_);
  lastCmdMs_ = millis();
}

void ESCMotor::applyPulseUs_(int pulseUs) {
  const uint32_t duty = pulseUsToDuty_(pulseUs);
  ledcWrite(cfg_.ledcChannel, duty);
}

uint32_t ESCMotor::pulseUsToDuty_(int pulseUs) const {
  pulseUs = constrain(pulseUs, cfg_.pulseMinUs, cfg_.pulseMaxUs);

  const uint32_t periodUs = 1000000UL / (uint32_t)cfg_.pwmFreqHz; // 20000us @50Hz
  const uint32_t maxDuty = (1UL << cfg_.pwmResolutionBits) - 1UL;

  return (uint32_t)(((uint64_t)pulseUs * (uint64_t)maxDuty) / (uint64_t)periodUs);
}
