# Archive du firmware

Les étapes qui ont mené au firmware de référence ([`../stabilisation/`](../stabilisation/)), dans l'ordre. Elles ne sont plus développées, mais elles montrent le cheminement et restent utiles pour re-caractériser un capteur ou un moteur isolément.

| Dossier | Date | Ce qu'il fait | Ce qu'il a apporté |
| --- | --- | --- | --- |
| [`2026-01_lecture-bno055/`](2026-01_lecture-bno055/) | 10-11/01/2026 | Lit le BNO055 en mode fusion NDOF : accéléromètre, gyromètre, magnétomètre, angles et quaternion ; détecte les mouvements | Driver I2C du capteur, repris dans `lib/IMU` |
| [`2026-01_pilotage-esc-serie/`](2026-01_pilotage-esc-serie/) | 13-14/01/2026 | Pilote un ESC par commandes série (`T,0.35` pour un gaz, `P,1500` pour une impulsion, `X` pour arrêter) avec télémétrie ; utilisé avec les modèles Simulink de [`matlab/pilotage-esc/`](../../matlab/README.md) | Caractérisation des moteurs depuis MATLAB, failsafe et keep-alive |
| [`2026-01_librairie-esc/`](2026-01_librairie-esc/) | 16/01/2026 | Bibliothèque ESC réutilisable avec un test de bidirectionnalité intégré | Base de `lib/ESC/ESCMotor` |
| [`2026-02_test-esc-bidirectionnel/`](2026-02_test-esc-bidirectionnel/) | 12/02/2026 | Test interactif d'un ESC (confirmation au clavier, o/n) pour vérifier les deux sens de rotation | Validation du neutre à 1 500 µs, indispensable pour une roue de réaction |

Les trois projets PlatformIO compilent seuls (`pio run -t upload` depuis le dossier). Le test bidirectionnel est un fichier unique, à placer dans le `src/` d'un projet PlatformIO pour ESP32.
