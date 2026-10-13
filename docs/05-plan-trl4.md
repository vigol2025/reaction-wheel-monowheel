# 5. Plan de passage au TRL 4

**Où en est le sous-système de stabilisation : TRL 3.** Les composants fonctionnent séparément (le BNO055 donne l'attitude, chaque ESC fait tourner son moteur dans les deux sens), mais ils n'ont jamais été intégrés et testés ensemble sur banc. Le TRL 4 sera atteint quand l'ensemble capteur, correcteur et roues tiendra l'équilibre en laboratoire, de façon reproductible.

Règle suivie pour chaque phase : **le critère de réussite est écrit avant l'essai**, pour ne pas réinterpréter un résultat après coup.

| Phase | Objectif | Statut au 13/10/2026 |
| --- | --- | --- |
| 0 | Vérifier que le couple disponible couvre le besoin | Faite le 14/09/2026 : échec, voir la [revue du budget de couple](04-revue-budget-de-couple.md) |
| 1 | Valider la boucle logicielle sur un axe et un moteur | Code prêt, essai à faire |
| 2 | Intégrer les 4 roues sur un cardan 2 axes, sans risque de chute | À venir |
| 3 | Équilibre libre en laboratoire, perturbations répétables | À venir : c'est le franchissement du TRL 4 |

## Phase 1 : un axe, un moteur

**Objectif.** Prouver que la boucle BNO055 → PID → ESC corrige dans le bon sens, sur un montage léger compatible avec le couple de l'A2212. Ce n'est pas un test de tenue du robot final.

**Montage.** Un ensemble roue de réaction (A2212, disque, support) sur un pivot à un axe, le BNO055 solidaire de l'axe.

**Code.** `firmware/stabilisation/src/test_single_axis.cpp`, environnement PlatformIO `test_single_axis` : boucle à 200 Hz cadencée par FreeRTOS, détection des dépassements de période, télémétrie JSON pour PlotJuggler ([firmware/](../firmware/README.md)).

**Déroulé.**

1. Câbler l'ESC et reporter la broche dans le code ; choisir l'axe corrigé (roulis ou tangage).
2. Laisser l'ESC s'armer sans toucher le montage, puis pousser l'axe à la main. Si le volant aggrave l'inclinaison, inverser le sens dans le code.
3. Appliquer une perturbation propre et observer : correction, oscillation ou divergence.

**Critère de réussite, à chiffrer avant l'essai.** L'axe revient à moins de X° de la position neutre en moins de Y s après une perturbation de Z°, sans atteindre la coupure de sécurité (30°).

**En cas d'échec, vérifier dans cet ordre** : l'alimentation, le sens de correction, la fréquence de boucle réellement tenue (visible dans la télémétrie), puis le couple disponible pour la masse réelle de ce montage. Pas de réglage des gains à l'aveugle.

## Phase 2 : quatre roues sur cardan

**Montage.** Les 4 roues de réaction, montées à 45°, sur un cardan 2 axes tenu par une structure fixe.

**Essais.**

1. Vérifier l'alimentation des 4 moteurs en même temps, sous charge.
2. Valider l'allocation : une poussée en roulis pur doit faire réagir les 4 moteurs dans les proportions prévues par la pseudo-inverse ([docs/03](03-architecture-4-roues.md)).
3. Reprendre l'essai de perturbation sur les deux axes, puis sur les deux à la fois.
4. Couper la commande : les 4 moteurs doivent revenir au neutre (failsafe).
5. Fonctionnement continu de 10 à 15 minutes : pas de dérive, pas de surchauffe, pas de perte du capteur.

**Critère de réussite.** Stabilisation tenue sur les deux axes, dans les seuils de la phase 1, sur toute la durée de l'essai continu.

## Phase 3 : équilibre libre

**Montage.** Le système sur son propre point d'appui, avec une sécurité (sangle ou portique) qui n'intervient qu'en cas de chute.

**Essais.** Perturbation calibrée et répétable, au moins 5 à 10 essais.

**Critère de réussite.** Retour à l'équilibre dans une proportion d'essais fixée à l'avance, par exemple 8 sur 10.

## Hors périmètre

- La roue de propulsion au sol, les bras et la tête.
- Le passage à un STM32 : seulement si un échec est clairement dû à la fréquence de boucle.
- Le choix du moteur du robot final : il dépend de la décision prise à la suite de la [revue du budget de couple](04-revue-budget-de-couple.md).
