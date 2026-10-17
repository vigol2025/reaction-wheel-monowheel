# 4. Revue du budget de couple (14/09/2026)

**Verdict : le moteur A2212 acheté pour les prototypes fournit 6 à 12 fois moins de couple que le dimensionnement ne l'exige. Il ne peut pas stabiliser le robot final de 6,5 kg.**

C'est le résultat le plus important du projet à ce jour. Je l'ai obtenu en septembre 2026, en reprenant tout le dossier avant de lancer les essais sur banc : plutôt que de régler des gains de PID sur un système qui ne pouvait pas marcher, j'ai d'abord vérifié que la physique le permettait.

## 4.1 Le constat de départ

Le dimensionnement ([docs/02](02-dimensionnement.md)) a été fait pour un Eaglepower 8308-160KV (280 à 310 g, 3,57 N·m à 60 A). Les prototypes de janvier 2026 ont été conçus autour d'un **A2212**, petit moteur d'avion de modélisme disponible et bon marché (environ 65 g, 27,7 × 27 mm). Personne n'avait encore comparé les deux.

## 4.2 Couple disponible avec l'A2212

D'après la fiche du fabricant, la variante 930 KV tire 9,8 A en continu sous 11,1 V (batterie 3S) :

$$
k_T \approx \frac{9{,}5493}{K_V} = \frac{9{,}5493}{930} = 0{,}0103\ \text{N·m/A}
\qquad
\tau \approx 0{,}0103 \times 9{,}8 \approx 0{,}10\ \text{N·m}
$$

La variante 1 400 KV à 19 A donne environ 0,13 N·m. Même avec une pointe optimiste à 0,20 N·m, le gabarit du moteur limite le couple : ce n'est pas un problème de réglage électrique.

## 4.3 Comparaison

| Grandeur | Besoin (dimensionnement) | A2212 | Écart |
| --- | --- | --- | --- |
| Couple par roue | 1,17 N·m | 0,10 à 0,13 N·m en continu | 9 à 12 fois moins |
| Couple par roue, en pointe | 1,17 N·m | 0,20 N·m au mieux | environ 6 fois moins |
| Couple de gravité seul à 10° (4 roues projetées sur un axe) | 2,78 N·m | 4 × 0,13 × 0,707 ≈ 0,37 N·m | 7,5 fois moins |

La dernière ligne suffit à conclure : à 10° d'inclinaison, les quatre moteurs réunis ne compensent même pas la gravité, quel que soit le réglage du correcteur.

La [simulation en boucle fermée](../simulation/README.md) d'octobre 2026 le confirme : avec les A2212, le robot tombe en 0,56 s, en LQR comme en placement de pôles, les deux axes restant saturés à 0,28 N·m.

## 4.4 Le volant n'est pas celui du calcul non plus

J'ai mesuré le disque dessiné en CAO directement à partir de son maillage ([cad/](../cad/README.md)) : diamètre 120 mm, épaisseur 4,5 mm, volume 24,5 cm³. Le calcul supposait 0,25 kg sur un rayon de 80 mm. Avec ce volume, il faudrait un matériau de 10,2 g/cm³, plus dense que l'acier. En PLA (1,24 g/cm³), le disque pèse environ 30 g ; en aluminium, environ 66 g.

## 4.5 Ce que j'en ai tiré

1. **Ne pas tester ce qui ne peut pas marcher.** L'objectif du premier essai a été réduit : valider la chaîne logicielle (capteur, correcteur, variateur, réaction mesurable dans le bon sens) sur un montage à un seul axe, volontairement léger. Ce code reste valable quel que soit le moteur final ([plan TRL4](05-plan-trl4.md)).
2. **Deux options pour le robot final**, à trancher : revenir à un moteur de la classe de l'Eaglepower 8308, ou réduire fortement la taille et la masse du robot.
3. **Mesurer avant de régler.** Aucune grandeur du projet (couple moteur, inertie du volant, gains du correcteur) n'avait encore été mesurée. Le plan TRL4 fixe pour chaque essai un critère de réussite écrit avant l'essai.
