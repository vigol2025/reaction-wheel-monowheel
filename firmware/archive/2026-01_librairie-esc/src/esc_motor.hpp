#pragma once
#include <Arduino.h>

class ESCMotor {
public:
    /**
     * @param pwmPin        Pin utilisé pour le signal PWM vers l'ESC
     * @param ledcChannel   Canal LEDC de l'ESP32 (0-15)
     * @param minPulse      Durée d'impulsion en µs pour gaz minimum (classique: 1000µs)
     * @param maxPulse      Durée d'impulsion en µs pour gaz maximum (classique: 2000µs)
     * @param freq          Fréquence du signal (ESC RC : ~50Hz)
     * @param resolutionBits Résolution LEDC (ex: 16 bits)
     */
    ESCMotor(uint8_t pwmPin,
             uint8_t ledcChannel = 0,
             uint16_t minPulse = 1000,
             uint16_t maxPulse = 2000,
             uint16_t freq = 50,
             uint8_t resolutionBits = 16);

    void begin();
    void arm(uint32_t armTimeMs = 3000);

    // Impulsion brute en microsecondes
    void writeMicroseconds(uint16_t pulse);

    /**
     * Réglage de la "commande" normalisée :
     *  - Pour ESC unidirectionnel : on utilise [0.0 ; 1.0] -> [minPulse ; maxPulse]
     *  - Pour test bidirectionnel : on accepte [-1.0 ; 1.0]
     *    -1.0 => 1.0ms, 0 => 1.5ms, +1.0 => 2.0ms
     * Sur un ESC avion, les valeurs < ~1.0ms ou proches de 1.5ms font juste stop.
     */
    void setNormalized(float value);

private:
    uint8_t  _pwmPin;
    uint8_t  _channel;
    uint8_t  _resolutionBits;
    uint16_t _minPulse;
    uint16_t _maxPulse;
    uint16_t _neutralPulse;
    uint16_t _freq;
    uint32_t _periodUs;
    uint32_t _maxDuty;

    void _applyPulse(uint16_t pulse);
};
