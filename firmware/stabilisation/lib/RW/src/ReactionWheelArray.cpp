#include "ReactionWheelArray.hpp"

static ESCMotor::Config makeEscCfg(const ReactionWheelArray::Config& rw, int pin, int ch) {
  auto c = rw.escBase;
  c.escPin = pin;
  c.ledcChannel = ch;
  c.pulseMinUs = rw.pulseMinUs;
  c.pulseMaxUs = rw.pulseMaxUs;
  c.pulseArmUs = rw.pulseNeutralUs; // arming au neutre
  return c;
}

ReactionWheelArray::ReactionWheelArray(const Config& cfg)
: cfg_(cfg),
  m1_(makeEscCfg(cfg_, cfg_.w1.pin, cfg_.w1.channel)),
  m2_(makeEscCfg(cfg_, cfg_.w2.pin, cfg_.w2.channel)),
  m3_(makeEscCfg(cfg_, cfg_.w3.pin, cfg_.w3.channel)),
  m4_(makeEscCfg(cfg_, cfg_.w4.pin, cfg_.w4.channel))
{}

void ReactionWheelArray::begin() {
  m1_.begin(); m2_.begin(); m3_.begin(); m4_.begin();
  neutralAll();
}

void ReactionWheelArray::update() {
  m1_.update(); m2_.update(); m3_.update(); m4_.update();
}

bool ReactionWheelArray::allArmed() const {
  return m1_.isArmed() && m2_.isArmed() && m3_.isArmed() && m4_.isArmed();
}

int ReactionWheelArray::mapUtoPulse_(float u, int invert) const {
  u = constrain(u, -1.0f, 1.0f);
  if (invert) u = -u;

  int pulse = cfg_.pulseNeutralUs + (int)(u * (float)cfg_.deltaMaxUs);
  pulse = constrain(pulse, cfg_.pulseMinUs, cfg_.pulseMaxUs);
  return pulse;
}

void ReactionWheelArray::setCommand(float u1, float u2, float u3, float u4) {
  p1_ = mapUtoPulse_(u1, cfg_.w1.invert);
  p2_ = mapUtoPulse_(u2, cfg_.w2.invert);
  p3_ = mapUtoPulse_(u3, cfg_.w3.invert);
  p4_ = mapUtoPulse_(u4, cfg_.w4.invert);

  m1_.setPulseUs(p1_);
  m2_.setPulseUs(p2_);
  m3_.setPulseUs(p3_);
  m4_.setPulseUs(p4_);
}

void ReactionWheelArray::neutralAll() {
  p1_=cfg_.pulseNeutralUs; p2_=cfg_.pulseNeutralUs;
  p3_=cfg_.pulseNeutralUs; p4_=cfg_.pulseNeutralUs;

  m1_.setPulseUs(p1_);
  m2_.setPulseUs(p2_);
  m3_.setPulseUs(p3_);
  m4_.setPulseUs(p4_);
}
