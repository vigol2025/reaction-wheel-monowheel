# Banc moteur A2212 : commande depuis Simulink à travers l'ESP32

La commande du TP1 (référence, erreur, commande virtuelle, ESO) tourne dans Simulink, en temps réel, sur le PC. Toutes les 10 ms, Simulink envoie l'impulsion à l'ESP32 par le câble USB ; l'ESP32 l'applique à l'ESC sur le GPIO 26 et renvoie sa télémétrie. Le modèle du moteur tourne en parallèle (jumeau numérique) et reçoit exactement la même impulsion que le vrai moteur.

```
PC : Simulink (temps réel)                              ESP32 (firmware PlatformIO)          Puissance
  référence → erreur → −K → calcul de V → impulsion ──USB──> trame 7 octets ──> GPIO 26 ──> ESC 30 A ──> A2212 + disque
  ESO <── mesure y <── jumeau numérique (modèle)   <──USB── télémétrie 19 octets (100 Hz)
```

**Sans capteur de vitesse** (situation actuelle), la commande se ferme sur la vitesse du jumeau numérique : le vrai moteur reçoit les impulsions que calcule la commande, mais rien ne vérifie qu'il tourne à la bonne vitesse. Les courbes d'erreur et de perturbation sont donc celles du modèle. Quand un capteur sera monté, il suffira de compléter `lireVitesse()` dans le firmware et de basculer « Source de la mesure » sur capteur.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `firmware/` | Projet PlatformIO pour l'ESP32 (VS Code) : réception des trames, signal de l'ESC, sécurité, télémétrie |
| `firmware/include/config.h` | Broches, limites d'impulsion, temps d'armement et de failsafe |
| `banc_parametres.m` | Paramètres de la maquette, port série, limites du banc. À lancer avant la simulation |
| `banc_moteur_A2212.slx` | Le modèle Simulink : commande du TP, pupitre, liaison ESP32, jumeau numérique, scopes |

## Câblage

| De | Vers | Remarque |
| --- | --- | --- |
| ESC, fil blanc (signal) | ESP32 GPIO 26 | |
| ESC, fil noir (masse) | ESP32 GND | Masse commune obligatoire, sinon le signal n'a pas de référence |
| ESC, fil rouge (BEC 5 V) | **Rien** | L'ESP32 est alimenté par l'USB pendant les essais Simulink : deux sources de 5 V ne doivent jamais être reliées |
| Convertisseur abaisseur, sortie | **Débranché de VIN** pendant les essais Simulink | Même raison. S'il sert plus tard sans PC, régler sa sortie sur 5 V et la brancher sur VIN, pas sur 3V3 |
| Batterie 3S (XT60) | Entrée de l'ESC | À brancher en dernier |
| ESP32 USB | PC | Alimentation et liaison série à 115 200 bauds |

D'après les photos du câblage, le fil rouge du BEC de l'ESC (prolongé par le cavalier jaune) et la sortie du convertisseur arrivent tous les deux sur la ligne d'alimentation de la plaque d'essai : les débrancher avant de brancher l'USB.

## Mise en route

1. **Charger le firmware**, batterie débranchée : dans VS Code, ouvrir le dossier `firmware/` avec PlatformIO, puis *Upload* (ou `pio run -t upload`).
2. **Libérer le port** : fermer le moniteur série de PlatformIO et tout autre programme qui utilise le port de l'ESP32.
3. **Régler le port** : dans le Gestionnaire de périphériques, noter le port COM de l'ESP32, le mettre dans `port_esp32` de `banc_parametres.m`, puis lancer le script.
4. **Ouvrir `banc_moteur_A2212.slx`** et vérifier le pupitre : *Mode* sur le haut (impulsion manuelle), *Marche ou arrêt* sur arrêt, curseur *Impulsion manuelle* à 1500.
5. **Brancher la batterie** : l'ESC reçoit déjà 1500 µs et s'arme (bips).
6. **Run** : l'ouverture du port redémarre l'ESP32, qui reste 3 s au neutre (état 0), puis passe à l'arrêt (état 1). Dans le scope *État de la liaison*, « liaison active » doit valoir 1.
7. **Premiers tours en manuel** : double-clic sur *Marche ou arrêt* pour passer en marche, puis curseur à 1550 µs ; revenir à 1500, puis arrêt.
8. **Commande du TP** : à l'arrêt, basculer *Mode* vers le bas (impulsion du TP), puis marche. Le vrai moteur reçoit la commande calculée sur le jumeau.
9. **Pour finir** : arrêt, *Stop*, puis débrancher la batterie.

## Ce que montrent les scopes

| Scope | Courbes |
| --- | --- |
| Vitesses | ωr, ω du jumeau, ω du capteur (vide tant qu'il n'y a pas de capteur) |
| Erreur de suivi | e = y − ωr, avec y la mesure utilisée par la commande |
| Perturbation | d simulée et d estimée par l'ESO |
| Tension et impulsions | V appliquée, impulsion envoyée par Simulink, impulsion appliquée par l'ESP32 (télémétrie) |
| État de la liaison | État de l'ESP32, liaison active, trames rejetées |

Tous ces signaux sont aussi enregistrés : après un essai, *Simulation > Data Inspector* permet de les superposer et de les exporter.

## Sécurité

| Protection | Où | Effet |
| --- | --- | --- |
| Armement | ESP32 | 3 s au neutre au démarrage |
| Failsafe | ESP32 | Neutre si aucune trame valide pendant 200 ms : Stop, câble débranché, Simulink figé |
| Marche | Simulink et ESP32 | Neutre tant que *Marche ou arrêt* est sur arrêt |
| Limites du banc | Simulink et ESP32 | Impulsion bornée à 1300 et 1700 µs (±4,44 V, environ 6 200 tr/min au plus en régime établi, disque en PLA) |
| Trames invalides | ESP32 | Rejetées si la somme est fausse ou si l'impulsion sort de 1000 à 2000 µs |
| Mesure absente | Simulink | Avec la source capteur, la marche est refusée si la liaison est coupée ou si la vitesse vaut NaN |
| Valeur non numérique | Simulink | Une impulsion NaN est remplacée par le neutre, marche coupée |

État de l'ESP32, aussi visible sur sa LED bleue : 0 armement (clignotement rapide), 1 arrêt (éteinte), 2 marche (allumée), 3 failsafe (clignotement lent).

## Protocole série (115 200 bauds)

**Commande, PC vers ESP32, 7 octets, toutes les 10 ms** : `0xA5 0x5A`, impulsion en µs (uint16, petit-boutiste), drapeaux (bit 0 = marche), numéro de trame, somme (des 4 octets utiles, modulo 256).

**Télémétrie, ESP32 vers PC, 19 octets, toutes les 10 ms** : `0xB5 0x5B`, temps en ms (uint32), impulsion appliquée (uint16), état (uint8), numéro de la dernière trame reçue (uint8), vitesse en rad/s (float, NaN sans capteur), trames valides (uint16), trames rejetées (uint16), somme (des 16 octets utiles, modulo 256).
