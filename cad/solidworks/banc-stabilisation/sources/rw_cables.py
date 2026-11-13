"""Câblage du dispositif (version 3) : chaque câble est un tube de son diamètre réel, balayé le long de son cheminement,
coudes arrondis. Les longueurs mesurées sont respectées au millimètre : 18 cm du moteur à l'ESC, 13 cm de
l'ESC à sa XT60 (rw_params.LONGUEURS) ; le mou est rangé dans le cheminement lui-même. Les autres longueurs (branches
de commande, capteurs) sont relevées sur le modèle et imprimées. Les ESC se branchent sur la carte de distribution XT60
1 vers 4 achetée, au centre de l'étage. Repère du dispositif.

Familles (une pièce SolidWorks chacune) : RW-50 fils moteur (3 × 16 AWG), RW-51 fils d'alimentation des ESC
(2 × 16 AWG), RW-52 câble d'alimentation (vers l'entrée de la carte de distribution), RW-53 câbles de commande des ESC, RW-54 câbles des
capteurs de vitesse, RW-55 câble du BNO055, RW-56 nappe des signaux vers la table.

Usage : python rw_cables.py [dossier des STEP]   (Python avec build123d) : longueurs, écarts, puis STEP par famille
"""
import itertools
import math
import os
import sys

import numpy as np
from build123d import Circle, Compound, Edge, Plane, Wire, export_step, sweep

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rw_params import *  # noqa: F401,F403

Z_DECK = Z_PLATEAU + E_PLATEAU                          # dessus du plateau
Z_ESC = Z_DECK + ESC[1] / 2                             # mi-hauteur des ESC (sortie des fils de puissance)
R_VOIE = 77.5                                           # voie des câbles de signal, sur la bordure du plateau
PAS_VOIE, PAS_VOL = 3.6, 4.0                            # étagement des câbles dans la voie, puis au-dessus du bornier
Z_VOL = Z_DECK + 31.0                                   # premier niveau de vol vers le bornier (au-dessus des prises)
Z_BNO = Z_DECK + ESC[1] + 4.0                           # le câble du BNO055 passe au-dessus de l'ESC −X
Z_PRISE = Z_DECK + BORNIER_H + 14.5                     # dessus d'une prise Dupont branchée sur le bornier
FAMILLES = {"moteur": "RW-50_Fils-moteur", "alim": "RW-51_Fils-alim-ESC", "faisceau": "RW-52_Cable-alimentation",
            "commande": "RW-53_Cables-commande-ESC", "capteur": "RW-54_Cables-capteurs", "bno": "RW-55_Cable-BNO055",
            "nappe": "RW-56_Nappe-signaux"}
LINEIQUE = {"moteur": 54.0, "alim": 36.0, "faisceau": 36.0, "commande": 10.0, "capteur": 9.0, "bno": 12.0, "nappe": 45.0}  # g/m
# bornier : rangée des ESC (ordre d'arrivée des câbles) et rangée des capteurs, de +Y vers −Y
ORDRE_ESC = (1, 2, 3, 0)          # indices k : ESC 2, ESC 3, ESC 4, ESC 1
ORDRE_CAPTEURS = (0, 1, 2, 3)     # capteurs 1, 2, 3, 4


# ---------------------------------------------------------------- repères
def coin(c, r, u, z):
    """Point du repère d'un coin (angle c) : r radial, u tangentiel (sens trigonométrique), z."""
    a = math.radians(c)
    return np.array([r * math.cos(a) - u * math.sin(a), r * math.sin(a) + u * math.cos(a), z])


def face(a, u, v, w):
    """Point du repère d'une face (plan_roue) : u tangentiel, v vertical, w normal sortant depuis la face extérieure."""
    return coin(a, R_PAROI + w, u, v)


def polaire(r, t, z):
    return np.array([r * math.cos(math.radians(t)), r * math.sin(math.radians(t)), z])


def tourne(p, c):
    a = math.radians(c)
    return np.array([p[0] * math.cos(a) - p[1] * math.sin(a), p[0] * math.sin(a) + p[1] * math.cos(a), p[2]])


def a_z(p, z):
    return np.array([p[0], p[1], z])


# ---------------------------------------------------------------- chemins
def chemin(points, r):
    """Fil de lignes et d'arcs passant près des points, coudes de rayon r (réduit là où les segments sont trop courts).
    Renvoie le fil et le plus petit rayon employé."""
    P = [np.asarray(p, float) for p in points]
    P = [p for i, p in enumerate(P) if i == 0 or np.linalg.norm(p - P[i - 1]) > 1e-6]
    aretes, depart, rmin = [], P[0], r
    n = len(P)
    for i in range(1, n - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        la, lc = np.linalg.norm(a - b), np.linalg.norm(c - b)
        u1, u2 = (a - b) / la, (c - b) / lc
        cos_t = float(np.clip(u1 @ u2, -1, 1))
        if cos_t < -0.99999:                              # alignés
            continue
        th = math.acos(cos_t)                             # angle intérieur
        t = r / math.tan(th / 2)
        tmax = min(la * (1.0 if i == 1 else 0.5), lc * (1.0 if i == n - 2 else 0.5)) - 1e-3
        rr = r
        if t > tmax:
            t, rr = tmax, tmax * math.tan(th / 2)
        rmin = min(rmin, rr)
        t1, t2 = b + u1 * t, b + u2 * t
        bis = (u1 + u2) / np.linalg.norm(u1 + u2)
        milieu = b + bis * (rr / math.sin(th / 2) - rr)
        if np.linalg.norm(t1 - depart) > 1e-4:
            aretes.append(Edge.make_line(tuple(depart), tuple(t1)))
        aretes.append(Edge.make_three_point_arc(tuple(t1), tuple(milieu), tuple(t2)))
        depart = t2
    if np.linalg.norm(P[-1] - depart) > 1e-4:
        aretes.append(Edge.make_line(tuple(depart), tuple(P[-1])))
    return Wire(aretes), rmin


def longueur(points, r):
    return chemin(points, r)[0].length


def ajuste(f, cible, lo, hi):
    """Paramètre t de [lo, hi] pour lequel longueur(f(t)) = cible (dichotomie ; f croissante ou décroissante)."""
    flo, fhi = f(lo) - cible, f(hi) - cible
    assert flo * fhi <= 0, ("longueur hors plage", round(flo + cible, 1), round(fhi + cible, 1), cible)
    for _ in range(40):
        m = (lo + hi) / 2
        fm = f(m) - cible
        if fm * flo <= 0:
            hi = m
        else:
            lo, flo = m, fm
    return (lo + hi) / 2


# ---------------------------------------------------------------- points fixes
def sortie_esc(k, bout, dz=0.0):
    """Sortie des fils d'un bout de l'ESC k (0 à 3) : point au ras de la face d'extrémité, direction de sortie.
    bout : "moteur" (vers le coin de son moteur) ou "alim" (alimentation et commande, vers le coin précédent)."""
    s = 1.0 if bout == "moteur" else -1.0
    p = tourne(np.array([ESC_A, s * (ESC[0] / 2 + 0.3), Z_ESC + dz]), ESC_FACE[k])
    d = tourne(np.array([0.0, s, 0.0]), ESC_FACE[k])
    return p, d


def z_carte():
    """Dessous de la carte de distribution, posée sur ses entretoises."""
    return Z_DECK + ENTRETOISE


def sortie_carte(k):
    """Dessus de la fiche XT60 de l'ESC k, branchée sur sa sortie de la carte : le fil en sort vers le haut."""
    return np.array([PDB_SORTIES[PDB_SORTIE_ESC[k]], 0.0, z_carte() + PDB[2] + XT60_DOUILLE_H + XT60_FICHE_H + 0.3])


def prise(rangee, rang):
    """Dessus de la prise branchée sur le bornier : rangée 0 (ESC) ou 1 (capteurs), rang 0 à 3 depuis +Y."""
    y = (BORNIER_N - 1) / 2 * 2.54 - (4 * rang + 1) * 2.54
    return np.array([X_BARRETTES[rangee], y, Z_PRISE])


# ---------------------------------------------------------------- puissance
def fil_moteur(j):
    """Moteur j vers le bout moteur de l'ESC j : sort à la base du stator, entre dans le corps par la fente, fait une
    boucle contre la face intérieure (le mou des 18 cm), monte par l'encoche du coin et entre dans l'ESC. La fente est
    ouverte en haut : les fils, soudés aux deux bouts, s'y posent par-dessus."""
    a = ANGLES_ROUES[j]
    e, de = sortie_esc(j, "moteur")
    n = e + de * R_COURBURE                                # aplomb de la montée, dans l'encoche
    wl = -13.0                                             # la boucle passe devant les écrous de la croix du moteur

    uf = FENTE_FILS[2]
    nl = np.array([-(n[0] * math.sin(math.radians(a))) + n[1] * math.cos(math.radians(a)),
                   math.hypot(n[0], n[1]) and (n[0] * math.cos(math.radians(a)) + n[1] * math.sin(math.radians(a))) - R_PAROI])   # u, w de la montée

    def pts(vb):
        return [face(a, uf, V_FILS, 9.0), face(a, uf, V_FILS, wl), face(a, uf, vb, wl), face(a, uf + 18.0, vb, wl),
                face(a, uf + 18.0, 30.0, wl), face(a, nl[0], 46.0, nl[1]), n, e]
    vb = ajuste(lambda t: longueur(pts(t), R_COURBURE), LONGUEURS["moteur"], 14.0, -28.0)
    return pts(vb)


def fil_alim(k):
    """Bout alimentation de l'ESC k vers sa sortie de la carte de distribution : le fil monte dans le coin, passe
    au-dessus des ESC et descend dans la fiche XT60, branchée sur la carte (les 13 cm, au millimètre)."""
    e, de = sortie_esc(k, "alim", dz=5.0)
    n = e + de * 8.0
    f = sortie_carte(k)
    monte = a_z(n, Z_DECK + ESC[1] + 6.0)                  # au-dessus de l'ESC, puis en diagonale vers la carte

    def pts(h):
        return [e, n, monte, a_z(f, h), f]
    h = ajuste(lambda t: longueur(pts(t), R_COURBURE), LONGUEURS["alim_esc"], f[2] + 8.0, f[2] + 60.0)
    return pts(h)


def principal():
    """Câble d'alimentation : de la fiche branchée sur l'entrée de la carte, au-dessus de l'ESC +X, puis le long de la face
    +X jusqu'au collier."""
    x1 = PDB_ENTREE[1] + FICHE_ENTREE + 0.3
    z = z_carte() + PDB[2] + PDB_ENTREE[2] / 2
    x = R_PAROI + 6.0
    return [np.array([x1, 0.0, z]), np.array([x1 + 12.0, 0.0, z]), np.array([x, -6.0, z - 12.0]), np.array([x, -SORTIE_Y, 16.0]),
            np.array([R_PAROI + 4.0, -SORTIE_Y, -20.0]), np.array([R_PAROI + 4.0, -SORTIE_Y, -33.0])]


# ---------------------------------------------------------------- signaux
def voie(c0, u0, sens, niveau, arrivee):
    """Depuis le point (coin c0, u0) de la voie, dans le sens donné (+1 trigonométrique), au niveau donné (0 à 3), jusqu'à
    la prise d'arrivée : bordure du plateau, montée sur le dernier pan diagonal, vol au-dessus des ESC, descente."""
    z = Z_DECK + 1.75 + PAS_VOIE * niveau
    zv = Z_VOL + PAS_VOL * niveau
    c1 = 180.0 - 45.0 * sens                               # dernier pan diagonal avant le bornier : 135 ou 225°
    u1 = sens * (14.0 + 5.0 * (3 - niveau))                # le câble du haut monte le premier
    pts = [coin(c0, R_VOIE, u0, z)]
    t = c0
    while abs(t - c1) > 1e-6:                              # sommets de l'octogone entre les deux pans
        for dt in (22.5, 67.5):
            pts.append(polaire(R_VOIE / math.cos(math.radians(22.5)), t + sens * dt, z))
        t += 90.0 * sens
    m = coin(c1, R_VOIE, u1, z)
    return pts + [m, a_z(m, zv), a_z(arrivee, zv), arrivee]


def _cote(k_ou_j, ordre):
    """Rang sur le bornier, sens de parcours et niveau : les deux premiers rangs arrivent par +Y, les autres par −Y ;
    le câble qui vient de loin prend la prise extérieure."""
    rang = ordre.index(k_ou_j)
    return rang, (1 if rang < 2 else -1), rang in (0, 3)


def cable_commande(k):
    """Câble de commande de l'ESC k (3 fils), de son bout alimentation au bornier, rangée des ESC."""
    c = ESC_COIN_ALIM[k]
    rang, sens, loin = _cote(k, ORDRE_ESC)
    niveau = 1 if loin else 3
    zn = Z_DECK + 1.75 + PAS_VOIE * niveau                 # il sort de l'ESC à la hauteur de sa voie, sous les fils
    e, de = sortie_esc(k, "alim", dz=zn - Z_ESC)           # d'alimentation, qui montent
    return [e, e + de * 9.0] + voie(c, 6.0, sens, niveau, prise(0, rang))


def cable_capteur(j):
    """Câble du capteur de vitesse j (3 fils Dupont) : de la prise de la carte, il contourne le carter par le haut,
    rejoint le plateau et la voie, jusqu'au bornier, rangée des capteurs."""
    a = ANGLES_ROUES[j]
    rang, sens, loin = _cote(j, ORDRE_CAPTEURS)
    niveau = 0 if loin else 2
    z = Z_DECK + 1.75 + PAS_VOIE * niveau
    wp = W_CARTE - 1.25
    u_prise = -(TCRT_CARTE[0] / 2 + 6.0 + 14.5)
    debut = [face(a, u_prise, TCRT_V, wp), face(a, -46.0, TCRT_V, wp), face(a, -46.0, 74.0, wp), face(a, -46.0, 74.0, 24.0),
             face(a, -14.0, 74.0, 24.0), face(a, -14.0, z, 6.0)]
    return debut + voie(a, -14.0, sens, niveau, prise(1, rang))


def cable_bno():
    """4 fils Dupont du BNO055 : sous la carte de distribution, au-dessus de l'ESC −X et du bornier, puis le long de la
    face −X jusqu'au collier."""
    return [np.array([-9.0, 0.0, Z_DECK + 19.0]), np.array([-9.0, 0.0, Z_DECK + 25.0]), np.array([-PDB[0] / 2 - 4.5, 0.0, Z_DECK + 25.0]),
            np.array([-PDB[0] / 2 - 4.5, 0.0, Z_BNO]),        # monte entre la carte et l'ESC −X
            np.array([-101.5, 0.0, Z_BNO]),
            np.array([-101.5, 0.0, 44.0]), np.array([-83.0, 8.0, 24.0]), np.array([-83.0, 8.0, -33.0])]


def nappe():
    """Fils Dupont sous le bornier (commandes, capteurs), en nappe le long de la face −X jusqu'au collier."""
    return [np.array([-88.0, 0.0, 46.0]), np.array([-88.0, SORTIE_Y, 34.0]), np.array([-85.5, SORTIE_Y, 10.0]),
            np.array([-85.5, SORTIE_Y, -33.0])]


def cables():
    """{nom : (famille, points, diamètre, rayon de courbure)}"""
    out = {}
    for k in range(4):
        out[f"moteur{k + 1}"] = ("moteur", fil_moteur(k), D_MOTEUR, R_COURBURE)
        out[f"alim{k + 1}"] = ("alim", fil_alim(k), D_ALIM, R_COURBURE)
        out[f"commande{k + 1}"] = ("commande", cable_commande(k), D_COMMANDE, 6.0)
        out[f"capteur{k + 1}"] = ("capteur", cable_capteur(k), D_CAPTEUR, 6.0)
    out["principal"] = ("faisceau", principal(), D_PRINCIPAL, R_COURBURE)
    out["bno"] = ("bno", cable_bno(), D_BNO, 8.0)
    out["nappe"] = ("nappe", nappe(), D_NAPPE, 12.0)
    return out


def tube(points, d, r):
    w, rmin = chemin(points, r)
    p0, p1 = np.asarray(points[0], float), np.asarray(points[1], float)
    section = Plane(origin=tuple(p0), z_dir=tuple((p1 - p0) / np.linalg.norm(p1 - p0))) * Circle(d / 2)
    return sweep(section, path=w), w, rmin


def solides():
    """{nom : (famille, solide, longueur en mm, masse en g)}"""
    out = {}
    for nom, (fam, pts, d, r) in cables().items():
        s, w, _ = tube(pts, d, r)
        out[nom] = (fam, s, w.length, w.length / 1000.0 * LINEIQUE[fam])
    return out


def main():
    C = cables()
    axes, bilan = {}, {}
    print("câble            Ø      longueur   rayon mini")
    for nom, (fam, pts, d, r) in C.items():
        w, rmin = chemin(pts, r)
        axes[nom] = (np.array([tuple(w.position_at(i / 300)) for i in range(301)]), d)
        bilan[nom] = w.length
        print(f"  {nom:12s} {d:4.1f}   {w.length:7.1f} mm   {rmin:5.1f} mm")
    # écart mini entre deux câbles (distance entre axes moins les deux rayons), hors bouts communs
    pires = []
    for (na, (A, da)), (nb, (B, db)) in itertools.combinations(axes.items(), 2):
        dmin = np.min(np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)) - (da + db) / 2
        if dmin < 1.0:
            pires.append((dmin, na, nb))
    print("\nécarts entre câbles inférieurs à 1 mm (négatif : ils se traversent) :")
    for dmin, na, nb in sorted(pires):
        print(f"  {dmin:6.2f} mm  {na} / {nb}")
    if not pires:
        print("  aucun")
    if len(sys.argv) > 1:
        os.makedirs(sys.argv[1], exist_ok=True)
        S = solides()
        for fam, fichier in FAMILLES.items():
            corps = [s for f, s, _, _ in S.values() if f == fam]
            export_step(Compound(children=corps), os.path.join(sys.argv[1], fichier + ".step"))
            print("écrit", fichier, len(corps), "câble(s)")


if __name__ == "__main__":
    main()
