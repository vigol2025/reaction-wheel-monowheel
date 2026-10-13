#include "esc_motor.hpp"

ESCMotor::ESCMotor(const Config& cfg) : cfg_(cfg) {
  pulseUsCmd_ = cfg_.pulseMinUs;
}

void ESCMotor::begin() {
  // Setup LEDC PWM (ESP32)
  ledcSetup(cfg_.ledcChannel, cfg_.pwmFreqHz, cfg_.pwmResolutionBits);
  ledcAttachPin(cfg_.escPin, cfg_.ledcChannel);

  bootMs_ = millis();
  lastCmdMs_ = bootMs_;
  armed_ = false;

  stop(); // pulse min
}

void ESCMotor::update() {
  const uint32_t now = millis();

  // Arming: tenir min pulse pendant armTimeMs
  if (!armed_) {
    applyPulseUs_(cfg_.pulseMinUs);
    if (now - bootMs_ >= cfg_.armTimeMs) {
      armed_ = true;
      lastCmdMs_ = now;
    }
    return;
  }

  // Failsafe
  if (cfg_.failsafeMs > 0 && (now - lastCmdMs_ > cfg_.failsafeMs)) {
    stop();
    lastCmdMs_ = now; // évite spam
  }
}

void ESCMotor::setThrottle(float throttle01) {
  throttle01 = clamp01_(throttle01);
  throttleCmd_ = throttle01;

  const int span = cfg_.pulseMaxUs - cfg_.pulseMinUs;
  const int pulse = cfg_.pulseMinUs + (int)(throttle01 * span);

  pulseUsCmd_ = pulse;
  applyPulseUs_(pulseUsCmd_);
  lastCmdMs_ = millis();
}

void ESCMotor::setPulseUs(int pulseUs) {
  pulseUs = constrain(pulseUs, cfg_.pulseMinUs, cfg_.pulseMaxUs);
  pulseUsCmd_ = pulseUs;

  const int span = cfg_.pulseMaxUs - cfg_.pulseMinUs;
  throttleCmd_ = (float)(pulseUsCmd_ - cfg_.pulseMinUs) / (float)span;

  applyPulseUs_(pulseUsCmd_);
  lastCmdMs_ = millis();
}

void ESCMotor::stop() {
  throttleCmd_ = 0.0f;
  pulseUsCmd_ = cfg_.pulseMinUs;
  applyPulseUs_(pulseUsCmd_);
  lastCmdMs_ = millis();
}

bool ESCMotor::handleCommandLine(const String& lineRaw, Stream& out) {
  // ==== "comme MATLAB readline" : on nettoie CR/LF/espaces ====
  String line = lineRaw;
  line.replace("\r", ""); // IMPORTANT si terminator CR/LF côté PC
  line.trim();

  // DEBUG: affiche EXACTEMENT ce qui est reçu
  out.print("RX:[");
  out.print(line);
  out.println("]");

  if (line.isEmpty()) return false;

  // STOP command: X
  if (line.equals("X")) {
    stop();
    out.println("OK,X");
    return true;
  }

  // Throttle command: T,0.35
  if (line.startsWith("T,")) {
    float t = line.substring(2).toFloat();
    setThrottle(t);
    out.print("OK,T,");
    out.println(throttleCmd_, 3);
    return true;
  }

  // Pulse command: P,1500
  if (line.startsWith("P,")) {
    int p = line.substring(2).toInt();
    setPulseUs(p);
    out.print("OK,P,");
    out.println(pulseUsCmd_);
    return true;
  }

  out.println("ERR,UNKNOWN");
  return false;
}

void ESCMotor::applyPulseUs_(int pulseUs) {
  const uint32_t duty = pulseUsToDuty_(pulseUs);
  ledcWrite(cfg_.ledcChannel, duty);
}

uint32_t ESCMotor::pulseUsToDuty_(int pulseUs) const {
  pulseUs = constrain(pulseUs, cfg_.pulseMinUs, cfg_.pulseMaxUs);

  const uint32_t periodUs = 1000000UL / (uint32_t)cfg_.pwmFreqHz; // 20000us @ 50Hz
  const uint32_t maxDuty = (1UL << cfg_.pwmResolutionBits) - 1UL;

  // duty = (pulseUs / periodUs) * maxDuty
  return (uint32_t)(((uint64_t)pulseUs * (uint64_t)maxDuty) / (uint64_t)periodUs);
}

float ESCMotor::clamp01_(float v) const {
  if (v < 0.0f) return 0.0f;
  if (v > 1.0f) return 1.0f;
  return v;
}
