# 6. Retour d'expérience

Ce que je retiens d'un an sur ce projet, et ce que je ferais autrement.

## Ce qui a bien marché

- **Partir des équations.** Le dimensionnement a fixé tôt les ordres de grandeur (3,3 N·m, 1,17 N·m par roue, 20 A par moteur). C'est grâce à lui que l'écart avec l'A2212 a pu être chiffré rapidement et sans ambiguïté.
- **Un firmware modulaire.** Séparer capteur, variateur, groupe de roues et correcteur en bibliothèques a permis d'écrire le test sur un axe en réutilisant le code existant, sans le dupliquer.
- **Des outils de caractérisation.** Piloter l'ESC depuis Simulink, avec un curseur et un keep-alive, rend les essais moteur reproductibles et sûrs.
- **Une modélisation système.** Le modèle Capella a forcé à lister les fonctions et les composants du robot entier, y compris l'énergie, la sécurité et la télémétrie.

## Ce que je ferais autrement

1. **Mesurer tôt.** Jusqu'en septembre 2026, aucune grandeur n'avait été mesurée : ni le couple moteur, ni l'inertie du volant, ni la réponse du système. Le calcul était rigoureux, mais il n'avait jamais été confronté au réel.
2. **Garder la cohérence entre calcul, achat et CAO.** Le calcul visait un moteur de 300 g et un volant de 250 g ; on a acheté un moteur de 65 g et dessiné un disque de 30 à 66 g. Une simple vérification à chaque achat aurait suffi.
3. **Justifier les gains du correcteur.** Les gains actuels (kp = 1,8, kd = 0,10) sont des valeurs de départ, sans lien tracé avec l'inertie du système. Ils seront à déterminer sur banc, puis à documenter.
4. **Mesurer la vitesse des volants.** Les ESC sont commandés en boucle ouverte. Sans mesure de vitesse, impossible de voir un volant saturer, c'est-à-dire atteindre sa vitesse maximale et ne plus pouvoir produire de couple.
5. **Vérifier la tenue mécanique.** Un disque imprimé qui tourne à plusieurs milliers de tr/min peut se rompre. Un calcul de contrainte centrifuge, même approché, est à faire avant les essais à pleine vitesse.
6. **Poser des jalons validés.** Le planning d'origine enchaînait les étapes sans critère de passage. La démarche par niveaux de maturité (TRL), avec un critère écrit avant chaque essai, corrige ce point.
