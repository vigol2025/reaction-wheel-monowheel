#include "esc_motor.hpp"

ESCMotor::ESCMotor(uint8_t pwmPin,
                   uint8_t ledcChannel,
                   uint16_t minPulse,
                   uint16_t maxPulse,
                   uint16_t freq,
                   uint8_t resolutionBits)
    : _pwmPin(pwmPin),
      _channel(ledcChannel),
      _resolutionBits(resolutionBits),
      _minPulse(minPulse),
      _maxPulse(maxPulse),
      _freq(freq)
{
    _periodUs     = 1000000UL / _freq;            // période d'un cycle (50Hz -> 20000 µs)
    _maxDuty      = (1UL << _resolutionBits) - 1; // max valeur de duty
    _neutralPulse = (_minPulse + _maxPulse) / 2;  // ~1500 µs
}

void ESCMotor::begin() {
    ledcSetup(_channel, _freq, _resolutionBits);
    ledcAttachPin(_pwmPin, _channel);

    // On commence à gaz minimum par sécurité
    _applyPulse(_minPulse);
}

void ESCMotor::arm(uint32_t armTimeMs) {
    // La plupart des ESC s'arment en recevant gaz minimum pendant quelques secondes
    _applyPulse(_minPulse);
    delay(armTimeMs);
}

void ESCMotor::writeMicroseconds(uint16_t pulse) {
    if (pulse < _minPulse) pulse = _minPulse;
    if (pulse > _maxPulse) pulse = _maxPulse;
    _applyPulse(pulse);
}

void ESCMotor::setNormalized(float value) {
    // On sature la valeur
    if (value > 1.0f)  value = 1.0f;
    if (value < -1.0f) value = -1.0f;

    // Mapping [-1;1] -> [minPulse;maxPulse] en passant par neutral.
    //   -1.0 -> minPulse
    //    0.0 -> neutralPulse (~1500µs)
    //   +1.0 -> maxPulse
    float halfRange = (float)(_maxPulse - _minPulse) / 2.0f;
    uint16_t pulse = (uint16_t)((float)_neutralPulse + value * halfRange);
    _applyPulse(pulse);
}

void ESCMotor::_applyPulse(uint16_t pulse) {
    // Convertit pulse (µs) en duty cycle pour LEDC
    float dutyRatio = (float)pulse / (float)_periodUs;  // entre 0 et 1
    uint32_t duty   = (uint32_t)(dutyRatio * (float)_maxDuty);
    if (duty > _maxDuty) duty = _maxDuty;
    ledcWrite(_channel, duty);
}
