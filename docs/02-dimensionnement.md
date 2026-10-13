# 2. Dimensionnement des roues de réaction

Ce document reprend mes deux notes de calcul, dans l'ordre où je les ai faites :

- [calculs manuscrits du 21/10/2025](sources/2025-10-21_calculs-manuscrits-dimensionnement.pdf) : premier passage, moteur Turnigy Multistar 9225-160KV ;
- [note de dimensionnement du 07/11/2025](sources/2025-11-07_note-dimensionnement-monowheel.docx) : version mise au propre, moteur Eaglepower 8308-160KV.

Une relecture critique faite en octobre 2026 est à la fin du document.

## 2.1 Modèle du robot

Le corps est modélisé par un cylindre plein de masse m = 6,5 kg, de rayon R et de hauteur H = 0,50 m, avec un centre de masse à h = 0,25 m.

$$
I_x = I_y = \frac{1}{12} m \left(3R^2 + H^2\right) \qquad I_z = \frac{1}{2} m R^2
$$

Application numérique : I_x = I_y = 0,237 kg·m² et I_z = 0,203 kg·m².

## 2.2 Couple nécessaire pour corriger 10° en 0,4 s

Accélération angulaire constante pour parcourir Δθ = 10° (0,1745 rad) en t = 0,4 s :

$$
\alpha = \frac{2\,\Delta\theta}{t^2} = 2{,}18\ \text{rad/s}^2
$$

Couple d'inertie, couple de gravité à 10° d'inclinaison, puis couple total :

$$
\tau_R = I_x\,\alpha = 0{,}517\ \text{N·m} \qquad
\tau_g = m\,g\,h\,\sin\theta = 2{,}78\ \text{N·m} \qquad
\tau_T = \tau_R + \tau_g = 3{,}3\ \text{N·m}
$$

La gravité représente 84 % du besoin : c'est elle qui dimensionne les moteurs, pas l'inertie du robot.

## 2.3 Couple par roue

Les quatre roues sont orientées à 45° des axes de roulis et de tangage ([docs/03](03-architecture-4-roues.md)). Chacune ne contribue donc qu'à hauteur de cos 45° sur un axe :

$$
4\,\tau_w \cos 45^\circ \ge \tau_T \quad\Rightarrow\quad \tau_w \ge 1{,}17\ \text{N·m}
$$

## 2.4 Choix du moteur

La constante de couple d'un moteur brushless se déduit de son KV :

$$
k_T = \frac{60}{2\pi\,K_V} \qquad \text{pour } K_V = 160\ \text{tr/min/V} : k_T = 0{,}0597\ \text{N·m/A}
$$

| Grandeur | Valeur |
| --- | --- |
| Courant par moteur pour 1,17 N·m | 19,6 A, soit 80 A pour les 4 moteurs |
| Courant maximal par moteur | 48 A, soit 192 A en pointe |
| Puissance mécanique à 3 600 tr/min | 441 W par moteur, 1,76 kW au total |

Deux candidats se sont succédé, tous deux à 160 KV :

| Date | Moteur | Caractéristiques clés | Variateur (ESC) prévu |
| --- | --- | --- | --- |
| 21/10/2025 | Turnigy Multistar 9225-160KV | 48 A, 1 200 W, 329 g, LiPo 6S à 8S | Castle Phoenix Edge 100A |
| 07/11/2025 | Eaglepower 8308-160KV | 50 à 60 A, 1 200 à 1 500 W, 280 à 310 g, 3,57 N·m à 60 A | Hobbywing Skywalker 80A |

À 60-80 % de son courant maximal, l'Eaglepower fournit 1,7 à 2,3 N·m : la marge sur les 1,17 N·m requis est confortable.

## 2.5 Volant d'inertie

| Grandeur | Valeur |
| --- | --- |
| Masse, rayon | 0,25 kg, 80 mm (diamètre 160 mm) |
| Inertie | I_v = 0,0016 kg·m² |
| Moment cinétique à 3 600 tr/min | H_v = I_v ω = 0,603 N·m·s par roue |
| Projection sur un axe | 0,426 N·m·s par roue, 1,21 N·m·s pour les quatre |

Variation de vitesse du robot pendant la correction : ΔΩ = α t = 0,873 rad/s. Variation de vitesse que doivent prendre les volants pour l'absorber :

$$
\Delta\omega_v = \frac{I_x}{I_v}\,\Delta\Omega = \frac{0{,}237}{0{,}0016} \times 0{,}873 = 129\ \text{rad/s} \approx 1\,230\ \text{tr/min}
$$

## 2.6 Roue au sol (hors périmètre de ce dépôt)

La propulsion était prévue avec un moteur brushless de type 6374 (Turnigy Aerodrive SK3-6374-149KV dans la note manuscrite, 6374-170KV dans la note du 07/11), piloté par un ESC de 80 à 120 A. Aucun code ne la pilote à ce jour.

## 2.7 Relecture critique (octobre 2026)

En préparant ce dépôt, j'ai relu mes calculs. Quatre points sont à corriger ou à préciser ; aucun ne change l'ordre de grandeur du besoin, qui reste d'environ 3,3 N·m.

1. **Rayon du robot.** L'énoncé donne R = 20 cm, mais l'application numérique utilise R = 25 cm. Avec 20 cm, I_x = 0,200 kg·m² et τ_T = 3,2 N·m. L'erreur va dans le sens prudent.
2. **Inertie du volant.** La formule écrite est ½ m r², mais la valeur calculée, 0,0016 kg·m², correspond à m r². Pour le disque réellement dessiné (une jante et quatre rayons, voir [cad/](../cad/README.md)), la masse est concentrée sur la jante : m r² est la bonne approximation. C'est donc la formule qui est à corriger, pas la valeur.
3. **Vitesse par roue.** Diviser 1 230 tr/min par 4 (307,5 tr/min) oublie la projection à 45°. Chaque roue ne contribue qu'à cos 45° : il faut 1 230 / (4 × 0,707) ≈ 435 tr/min par roue, toujours très en dessous des vitesses des moteurs.
4. **Profil de correction.** α = 2Δθ/t² suppose une accélération constante sur toute la durée, sans phase de freinage. Pour revenir à la verticale et s'y arrêter (accélérer puis freiner), il faut α = 4Δθ/t², ce qui double τ_R : τ_T passe à environ 3,8 N·m.

Le point qui change vraiment le projet n'est pas dans ces calculs : c'est que le moteur finalement acheté n'est pas celui qui a été dimensionné. Voir la [revue du budget de couple](04-revue-budget-de-couple.md).
