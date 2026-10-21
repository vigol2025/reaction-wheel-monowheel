#pragma once
#include <Arduino.h>

// ===== Broches =====
static constexpr int PIN_ESC = 26;          // fil blanc (signal) de l'ESC
static constexpr int PIN_LED = 2;           // LED bleue de la carte : allumée = marche, clignote = failsafe

// ===== Signal de l'ESC (LEDC) =====
static constexpr int LEDC_CANAL = 0;
static constexpr int PWM_FREQ_HZ = 50;      // période de 20 ms, comme le firmware de janvier
static constexpr int PWM_RESOLUTION = 16;   // bits

// ===== Impulsions (µs) =====
static constexpr int IMP_NEUTRE = 1500;     // ESC bidirectionnel : 1500 µs = arrêt
static constexpr int IMP_VALIDE_MIN = 1000; // en dehors de [1000, 2000] µs, la trame est rejetée
static constexpr int IMP_VALIDE_MAX = 2000;
static constexpr int IMP_BANC_MIN = 1300;   // limites de sécurité du banc (disque en PLA) :
static constexpr int IMP_BANC_MAX = 1700;   // environ 5 700 tr/min au plus

// ===== Temps =====
static constexpr uint32_t ARMEMENT_MS = 3000;  // neutre au démarrage pour armer l'ESC
static constexpr uint32_t FAILSAFE_MS = 200;   // neutre si aucune trame valide pendant ce temps
static constexpr uint32_t TELEMETRIE_MS = 10;  // une trame de télémétrie toutes les 10 ms (100 Hz)

// ===== Liaison série =====
static constexpr uint32_t BAUDS = 115200;
