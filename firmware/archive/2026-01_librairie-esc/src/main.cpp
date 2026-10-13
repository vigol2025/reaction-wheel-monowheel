#include <Arduino.h>
#include "esc_motor.hpp"

// Choisis le pin que tu utilises sur ton ESP32
// Exemple : GPIO 18 (à adapter à ton câblage)
constexpr uint8_t ESC_PWM_PIN   = 18;
constexpr uint8_t ESC_LEDC_CH   = 0;

ESCMotor esc(ESC_PWM_PIN, ESC_LEDC_CH);

void attendreReponseUtilisateur(char &answer) {
    // Attend qu'un caractère arrive sur le port série
    while (true) {
        if (Serial.available() > 0) {
            char c = Serial.read();
            c = tolower(c);
            if (c == 'o' || c == 'n' || c == 'y') {
                answer = c;
                break;
            }
        }
        delay(10);
    }
}

void testBidirectionnalite() {
    Serial.println(F("\n=== Test de bidirectionnalite de l'ESC ==="));
    Serial.println(F("Assure-toi que le moteur est bien fixe et que rien ne touche l'helice."));
    delay(3000);

    // 1) Marche avant modérée
    Serial.println(F("Phase 1 : marche 'avant' a ~40% pendant 3 secondes..."));
    esc.setNormalized(0.4f);   // valeur positive -> 'avant'
    delay(3000);

    // Stop / neutre
    Serial.println(F("Stop moteur 2 secondes..."));
    esc.setNormalized(0.0f);   // neutre (~1500µs)
    delay(2000);

    // 2) Marche 'arriere' (pour ESC bidirectionnels)
    Serial.println(F("Phase 2 : tentative de marche 'arriere' a ~40% pendant 4 secondes..."));
    Serial.println(F("Sur un ESC avion classique, le moteur devrait simplement s'arreter ou ne pas tourner."));
    Serial.println(F("Sur un ESC voiture/bateau bidirectionnel, le moteur devrait tourner dans le SENS INVERSE."));
    esc.setNormalized(-0.4f);  // valeur negative -> 'arriere' si ESC bidirectionnel
    delay(4000);

    // Stop
    Serial.println(F("Stop moteur."));
    esc.setNormalized(0.0f);
    delay(2000);

    Serial.println(F("\nLe moteur a-t-il clairement tourne dans le SENS INVERSE"));
    Serial.println(F("par rapport a la phase 1 ?"));
    Serial.println(F("Reponds par 'o' (oui) ou 'n' (non) puis appuie sur Entree."));

    char answer = 0;
    attendreReponseUtilisateur(answer);

    if (answer == 'o' || answer == 'y') {
        Serial.println(F("\n>>> Conclusion : ESC BIDIRECTIONNEL."));
        Serial.println(F("Il s'agit tres probablement d'un ESC de type voiture/bateau ou drone avec reverse."));
        Serial.println(F("Type probable : ESC brushless bidirectionnel controle PWM (mode RC)."));
    } else {
        Serial.println(F("\n>>> Conclusion : ESC NON bidirectionnel (unidirectionnel)."));
        Serial.println(F("Tu possedes tres probablement un ESC de type avion/multirotor :"));
        Serial.println(F(" - Controle par signal PWM RC classique (1-2ms a 50Hz)."));
        Serial.println(F(" - Sens unique, la valeur basse coupe simplement le moteur."));
    }

    Serial.println(F("\nTest termine."));
}

void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println(F("\nDemarrage ESP32 - Test ESC"));

    esc.begin();

    Serial.println(F("Armement de l'ESC (gaz minimum quelques secondes)..."));
    esc.arm(4000);
    Serial.println(F("Armement termine."));

    testBidirectionnalite();
}

void loop() {
    // Rien de plus, on laisse juste tourner.
    // Tu peux ajouter d'autres tests ici si tu veux rejouer le test etc.
}
