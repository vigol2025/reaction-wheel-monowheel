#pragma once
#include <Arduino.h>
#include "ESCMotor.hpp"

class ReactionWheelArray {
public:
  struct WheelConfig {
    int pin;
    int channel;
    int invert;

    WheelConfig(int p=18, int ch=0, int inv=0) : pin(p), channel(ch), invert(inv) {}
  };

  struct Config {
    ESCMotor::Config escBase;

    WheelConfig w1 = WheelConfig(18, 0, 0);
    WheelConfig w2 = WheelConfig(19, 1, 0);
    WheelConfig w3 = WheelConfig(21, 2, 0);
    WheelConfig w4 = WheelConfig(22, 3, 0);

    int pulseNeutralUs = 1500;
    int pulseMinUs     = 1000;
    int pulseMaxUs     = 2000;
    int deltaMaxUs     = 500;
  };

  explicit ReactionWheelArray(const Config& cfg);

  void begin();
  void update();

  void setCommand(float u1, float u2, float u3, float u4);
  void neutralAll();

  int pulse1() const { return p1_; }
  int pulse2() const { return p2_; }
  int pulse3() const { return p3_; }
  int pulse4() const { return p4_; }

  bool allArmed() const;

private:
  Config cfg_;

  ESCMotor m1_, m2_, m3_, m4_;

  int p1_=1500, p2_=1500, p3_=1500, p4_=1500;

  int mapUtoPulse_(float u, int invert) const;
};
