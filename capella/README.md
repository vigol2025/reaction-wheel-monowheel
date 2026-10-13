# Modèle système Capella (décembre 2025)

Le dossier [`MONOWHEEL/`](MONOWHEEL/) est un projet [Capella](https://mbse-capella.org/), outil d'ingénierie système basé sur des modèles (MBSE) qui applique la méthode **Arcadia**. Il couvre le robot entier, pas seulement la stabilisation.

## Ouvrir le modèle

Dans Capella : *File > Import > Existing Projects into Workspace*, puis choisir le dossier `MONOWHEEL`. Les diagrammes sont dans `MONOWHEEL.aird`, le modèle sémantique dans `MONOWHEEL.capella`.

## Niveaux d'analyse

| Niveau Arcadia | Question traitée |
| --- | --- |
| Analyse opérationnelle | Qui utilise le robot, et pour quoi faire |
| Analyse système | Ce que le robot doit faire, vu de l'extérieur |
| Architecture logique | Comment les fonctions se répartissent, sans choix technologique |
| Architecture physique | Quels composants réels réalisent ces fonctions |
| Arborescence produit (EPBS) | Découpage en éléments à acheter ou fabriquer |

## Composants modélisés

| Domaine | Composants logiques | Composants physiques |
| --- | --- | --- |
| Équilibre et mouvement | Contrôleur d'attitude et d'équilibre, contrôleur de traction et de déplacement | 4 moteurs de stabilisation et 4 ESC, moteur au sol Turnigy Aerodrive SK3-6374, ESC Hobbywing 120A V3, centrale inertielle |
| Calcul | Gestionnaire de modes et de comportements, exécuteur de modes de pilotage | NUCLEO-G474RE (STM32) |
| Énergie et sécurité | Gestionnaire énergie et sécurité | Batterie LiPo 6S Tattu R-Line V4 120C, fusible 100 A, barrette de distribution, connecteurs XT60 anti-étincelle, régulateur 5 V Pololu D24V22F5 |
| Mesures | Gestionnaire d'alertes et de télémétrie, journalisation | Capteur de courant ACS758 100 A, INA219, capteur de température TMP117, mesure de tension batterie |
| Interface | Interpréteur de commandes, capture des entrées utilisateur, passerelle vers le corps | Manette, PC, liaison de communication, IHM |

## Écarts avec la réalisation

- Le modèle référence un **BNO085** ; c'est un **BNO055** qui est câblé et codé.
- Le modèle prévoit un **STM32** ; les prototypes tournent sur **ESP32** ([docs/03](../docs/03-architecture-4-roues.md)).
- Les capteurs de courant prévus (ACS758, INA219) ne sont pas encore implémentés : c'est ce qui manque pour détecter la saturation des volants.
