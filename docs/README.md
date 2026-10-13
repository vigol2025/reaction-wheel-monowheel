# Documentation technique

La documentation détaillée est en français. Ordre de lecture conseillé :

| # | Document | Ce qu'on y trouve |
| --- | --- | --- |
| 1 | [Contexte et besoin](01-contexte-et-besoin.md) | Le projet Crystof, ma part du travail, les exigences de stabilisation |
| 2 | [Dimensionnement](02-dimensionnement.md) | Couples, inerties, choix des moteurs et du volant, relecture critique |
| 3 | [Architecture à 4 roues](03-architecture-4-roues.md) | Configuration à 45°, allocation du couple, choix du microcontrôleur et du capteur |
| 4 | [Revue du budget de couple](04-revue-budget-de-couple.md) | Pourquoi le moteur A2212 ne peut pas tenir le robot final, et ce que j'ai changé |
| 5 | [Plan TRL 4](05-plan-trl4.md) | Les trois phases d'essai, avec leurs critères de réussite |
| 6 | [Retour d'expérience](06-retour-d-experience.md) | Ce qui a marché, ce que je ferais autrement |
| | [Références](references.md) | Articles, fiches techniques et outils consultés |

Documentation au plus près des fichiers :

- [firmware/](../firmware/README.md) : architecture du code, conception temps réel, points connus ;
- [matlab/](../matlab/README.md) : pilotage et caractérisation des moteurs depuis Simulink ;
- [cad/](../cad/README.md) : pièces et assemblages SolidWorks, fichiers d'impression 3D ;
- [capella/](../capella/README.md) : modèle système Arcadia du robot entier.

Documents d'origine, datés : [sources/](sources/).
