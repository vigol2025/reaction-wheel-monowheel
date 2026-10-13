# 1. Contexte et besoin

## Le projet Crystof

Crystof est le robot mascotte de l'association étudiante **CRYSTEO** (JUNIA). L'association a défini le projet en 2024-2025 : un robot à l'image de sa mascotte, en trois sous-ensembles.

| Sous-ensemble | Fonction attendue |
| --- | --- |
| Corps (monowheel) | Tenir en équilibre sur une seule roue, à l'arrêt comme en mouvement ; avancer, reculer, s'incliner pour tourner |
| Bras | Deux rotules actives à trois degrés de liberté, avec des mains interchangeables |
| Tête | Écran tactile, caméra, haut-parleur et micro ; commandes vocales traitées par une IA embarquée |

Le corps est la base de tout le reste : sans équilibre, ni les bras ni la tête n'ont de sens. **Ce dépôt couvre le sous-système d'équilibre du corps**, stabilisé par des roues de réaction. Les bras et la tête restent au stade du cahier des charges.

## Ce que j'ai repris à mon compte

Mes premiers travaux datent d'octobre 2025. J'ai pris en charge la stabilisation, du calcul jusqu'au code :

- l'état de l'art sur les robots à roue de réaction (octobre 2025) ;
- le dimensionnement des couples, des inerties, des moteurs et des volants ([docs/02](02-dimensionnement.md)) ;
- le choix de l'architecture à 4 roues d'inertie à 45° ([docs/03](03-architecture-4-roues.md)) ;
- le modèle système sous Capella ([capella/](../capella/README.md)) ;
- la CAO de la roue de réaction et des pièces imprimées en 3D ([cad/](../cad/README.md)) ;
- le firmware ESP32 et les outils MATLAB/Simulink de caractérisation ([firmware/](../firmware/README.md), [matlab/](../matlab/README.md)) ;
- le dossier de sponsoring ([sources/](sources/2025-12-03_dossier-sponsoring.pdf)).

Le cahier des charges initial et le budget de départ (environ 666 €, puis 716 €) ont été établis par l'association. Ils ne sont pas republiés ici.

## Exigences retenues pour la stabilisation

Ces valeurs viennent de ma note de dimensionnement ([docs/02](02-dimensionnement.md)).

| Grandeur | Valeur |
| --- | --- |
| Masse du robot | 6,5 kg |
| Hauteur | 50 cm, centre de masse à 25 cm |
| Rayon du corps | 20 cm |
| Perturbation à corriger | 10° d'inclinaison |
| Temps de correction | 0,4 s |
| Axes à stabiliser | Roulis et tangage |

## Pourquoi des roues de réaction

Un monowheel est un pendule inversé instable sur deux axes. Deux familles d'actionneurs inertiels existent :

- **le gyroscope de contrôle (CMG)** : un volant à vitesse constante dont on bascule l'axe. Très efficace, mais il faut un cardan motorisé ;
- **la roue de réaction** : on accélère ou on freine un volant, et le corps reçoit le couple opposé. Il suffit d'un moteur et d'un disque.

Le projet utilise des roues de réaction, réalisables avec des moteurs brushless de modélisme et des pièces imprimées en 3D. C'est aussi le principe de robots de référence comme la Wheelbot ou le robot de KTH (voir [références](references.md)).
