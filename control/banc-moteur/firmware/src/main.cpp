// Banc moteur A2212 : l'ESP32 applique à l'ESC l'impulsion calculée par Simulink
// et renvoie une télémétrie à 100 Hz. Toute la commande (référence, erreur, ESO) tourne dans Simulink.
//
// Trame de commande, PC -> ESP32 (7 octets) :
//   0xA5 0x5A | impulsion (uint16, µs, petit-boutiste) | drapeaux (bit 0 = marche) | seq | somme
// Trame de télémétrie, ESP32 -> PC (19 octets) :
//   0xB5 0x5B | struct Telemetrie (16 octets) | somme
// somme = somme des octets entre l'en-tête et la somme, modulo 256.
//
// Sécurité :
//   - 3 s au neutre au démarrage pour armer l'ESC ;
//   - neutre si aucune trame valide pendant 200 ms (Simulink arrêté, câble USB débranché) ;
//   - neutre si le drapeau marche vaut 0 ;
//   - trame rejetée si l'impulsion sort de [1000, 2000] µs ; impulsion bornée à [1300, 1700] µs.

#include <Arduino.h>
#include <math.h>
#include "config.h"

enum Etat : uint8_t { ARMEMENT = 0, ARRET = 1, MARCHE = 2, FAILSAFE = 3 };

struct __attribute__((packed)) Telemetrie {
  uint32_t t_ms;        // temps depuis le démarrage de l'ESP32
  uint16_t impulsion;   // µs réellement envoyée à l'ESC
  uint8_t etat;         // voir enum Etat
  uint8_t seq;          // numéro de la dernière trame de commande valide
  float vitesse;        // rad/s ; NAN tant qu'aucun capteur n'est monté
  uint16_t nb_ok;       // trames de commande valides reçues
  uint16_t nb_erreurs;  // trames rejetées (somme fausse ou impulsion hors plage)
};
static_assert(sizeof(Telemetrie) == 16, "la trame de télémétrie doit faire 16 octets");

static Etat etat = ARMEMENT;
static int impulsion_appliquee = -1;
static int impulsion_demandee = IMP_NEUTRE;
static bool marche_demandee = false;
static uint8_t seq_recu = 0;
static uint16_t nb_ok = 0;
static uint16_t nb_erreurs = 0;
static uint32_t t_demarrage = 0;
static uint32_t t_derniere_trame = 0;
static uint32_t t_telemetrie = 0;
static bool trame_recue = false;

// Écrit l'impulsion sur le périphérique LEDC (seulement si elle change)
static void ecrireImpulsion(int us) {
  if (us == impulsion_appliquee) return;
  impulsion_appliquee = us;
  const uint32_t periode_us = 1000000UL / PWM_FREQ_HZ;
  const uint32_t duty_max = (1UL << PWM_RESOLUTION) - 1UL;
  ledcWrite(LEDC_CANAL, (uint32_t)(((uint64_t)us * duty_max) / periode_us));
}

// Vitesse du disque en rad/s. Aucun capteur pour l'instant : NAN.
// C'est ici qu'il faudra brancher la lecture du capteur (fourche optique, AS5600...).
static float lireVitesse() {
  return NAN;
}

// Lit les octets reçus et décode les trames de commande (machine à états)
static void lireCommandes() {
  static uint8_t octets[5];
  static int n = -2;  // -2 : attend 0xA5, -1 : attend 0x5A, 0 à 4 : octets de la trame
  while (Serial.available() > 0) {
    const uint8_t c = (uint8_t)Serial.read();
    if (n == -2) {
      if (c == 0xA5) n = -1;
      continue;
    }
    if (n == -1) {
      n = (c == 0x5A) ? 0 : (c == 0xA5 ? -1 : -2);
      continue;
    }
    octets[n++] = c;
    if (n < 5) continue;
    n = -2;
    const uint8_t somme = (uint8_t)(octets[0] + octets[1] + octets[2] + octets[3]);
    const int imp = (int)octets[0] | ((int)octets[1] << 8);
    if (somme != octets[4] || imp < IMP_VALIDE_MIN || imp > IMP_VALIDE_MAX) {
      nb_erreurs++;
      continue;
    }
    impulsion_demandee = imp;
    marche_demandee = (octets[2] & 0x01) != 0;
    seq_recu = octets[3];
    nb_ok++;
    t_derniere_trame = millis();
    trame_recue = true;
  }
}

static void envoyerTelemetrie(uint32_t t) {
  Telemetrie m;
  m.t_ms = t;
  m.impulsion = (uint16_t)impulsion_appliquee;
  m.etat = (uint8_t)etat;
  m.seq = seq_recu;
  m.vitesse = lireVitesse();
  m.nb_ok = nb_ok;
  m.nb_erreurs = nb_erreurs;
  const uint8_t* p = reinterpret_cast<const uint8_t*>(&m);
  uint8_t somme = 0;
  for (size_t k = 0; k < sizeof(m); k++) somme += p[k];
  const uint8_t entete[2] = {0xB5, 0x5B};
  Serial.write(entete, 2);
  Serial.write(p, sizeof(m));
  Serial.write(somme);
}

static void afficherEtat(uint32_t t) {
  bool allumee = false;
  switch (etat) {
    case ARMEMENT: allumee = (t / 100) % 2; break;   // clignotement rapide
    case ARRET:    allumee = false; break;
    case MARCHE:   allumee = true; break;
    case FAILSAFE: allumee = (t / 500) % 2; break;   // clignotement lent
  }
  digitalWrite(PIN_LED, allumee ? HIGH : LOW);
}

void setup() {
  Serial.begin(BAUDS);
  pinMode(PIN_LED, OUTPUT);
  ledcSetup(LEDC_CANAL, PWM_FREQ_HZ, PWM_RESOLUTION);
  ledcAttachPin(PIN_ESC, LEDC_CANAL);
  ecrireImpulsion(IMP_NEUTRE);
  t_demarrage = millis();
}

void loop() {
  lireCommandes();
  const uint32_t t = millis();

  if (t - t_demarrage < ARMEMENT_MS) {
    etat = ARMEMENT;
    ecrireImpulsion(IMP_NEUTRE);
  } else if (!trame_recue || t - t_derniere_trame > FAILSAFE_MS) {
    etat = FAILSAFE;
    ecrireImpulsion(IMP_NEUTRE);
  } else if (!marche_demandee) {
    etat = ARRET;
    ecrireImpulsion(IMP_NEUTRE);
  } else {
    etat = MARCHE;
    ecrireImpulsion(constrain(impulsion_demandee, IMP_BANC_MIN, IMP_BANC_MAX));
  }

  afficherEtat(t);

  if (t - t_telemetrie >= TELEMETRIE_MS) {
    t_telemetrie = t;
    envoyerTelemetrie(t);
  }
}
