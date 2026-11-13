"""Contrôle du banc de stabilisation assemblé en Python (build123d), avant SolidWorks :
1. interférences entre pièces du dispositif au repos (moteurs A2212 et disques en rotation pris par leur volume équivalent) ;
2. balayage du cardan : dispositif incliné de −20° à +20° en roulis et en tangage, pour les 5 rangées d'inserts, la
   position équilibrée et les deux bouts des lumières des paliers, contre la fourche et le poteau ;
3. point le plus bas en inclinaison, d'où la hauteur du socle et la longueur du poteau ;
4. masse, centre de gravité, hauteur du centre de gravité au-dessus de chaque pivot et couple de gravité à 10°.

Usage : python rw_verif.py [dossier des rendus]   (Python avec build123d)
"""
import itertools
import math
import os
import sys

import numpy as np
from build123d import Box, Cylinder, Location, Plane, Pos, Rot

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rw_cables as K
import rw_pieces as P
from rw_params import *  # noqa: F401,F403

MARGE_SOCLE = 15.0


def moteur_equivalent():
    """Volume équivalent de l'A2212 (relevé sur le modèle du commerce), face d'appui à z = 0 : croix de fixation
    Ø30,8 × 2, stator et cloche Ø28 jusqu'à 29,3, arbre Ø3,2 jusqu'à 40,7."""
    return (Cylinder(15.4, 2.0, align=P.MIN) + Pos(0, 0, 2) * Cylinder(CLOCHE[2], CLOCHE[1] - 2, align=P.MIN)
            + Cylinder(1.6, ARBRE_FIN, align=P.MIN))


def pose_esc(k):
    """ESC k debout sur le plateau : épaisseur radiale, longueur tangentielle, largeur verticale."""
    return Rot(0, 0, ESC_FACE[k]) * Pos(ESC_A, 0, Z_PLATEAU + E_PLATEAU)


def forme_esc():
    return Box(ESC[2], ESC[0], ESC[1], align=P.MIN)


def pose_carte():
    return Pos(0, 0, Z_PLATEAU + E_PLATEAU + ENTRETOISE)


def pose_fiche(k):
    """Fiche XT60 de l'ESC k, branchée sur sa sortie de la carte."""
    return Pos(PDB_SORTIES[PDB_SORTIE_ESC[k]], 0, Z_PLATEAU + E_PLATEAU + ENTRETOISE + PDB[2] + XT60_DOUILLE_H)


def pose_fiche_entree():
    """Fiche du câble d'alimentation, branchée sur l'entrée de la carte (sa longueur selon +X)."""
    z = Z_PLATEAU + E_PLATEAU + ENTRETOISE + PDB[2] + PDB_ENTREE[2] / 2
    return Pos(PDB_ENTREE[1], 0, z) * Rot(0, 90, 0) * Pos(0, 0, 0)


def pose_tcrt(a):
    """Carte retournée : composants vers le disque (−w), capteur côté +u."""
    return Location(P.plan_roue(a)) * Pos(0, TCRT_V, W_CARTE) * Rot(180, 0, 0)


def disque_tournant(a):
    """Disque et couronne des vis d'équilibrage (têtes et écrous) en rotation, repère du dispositif."""
    e0, e1, re = DISQUE
    v0, v1, ri, rv = VIS_DISQUE
    d = Location(P.plan_roue(a, R_APPUI + e0)) * Cylinder(re, e1 - e0, align=P.MIN)
    c = Location(P.plan_roue(a, R_APPUI + v0)) * (Cylinder(rv, v1 - v0, align=P.MIN) - Cylinder(ri, v1 - v0, align=P.MIN))
    return d + c


def dispositif(moteur):
    """{nom : (forme, masse en g ou None pour volume × masse volumique, masse volumique)} dans le repère du dispositif."""
    d = {"moyeu": (P.moyeu(), None, RHO_IMPRIME), "plateau": (P.plateau(), None, RHO_IMPRIME),
         "bornier": (P.bornier(), None, RHO_IMPRIME)}
    pl, ca, pc, tc = P.platine(), P.carter(), P.porte_capteur(), P.tcrt()
    for k, a in enumerate(ANGLES_ROUES, 1):
        L = Location(P.plan_roue(a))
        d[f"platine{k}"] = (L * pl, None, RHO_IMPRIME)
        d[f"carter{k}"] = (L * ca, None, RHO_IMPRIME)
        d[f"porte{k}"] = (L * pc, None, RHO_IMPRIME)
        d[f"tcrt{k}"] = (pose_tcrt(a) * tc, MASSES["tcrt"], None)
        d[f"moteur{k}"] = (Location(P.plan_roue(a, R_APPUI)) * moteur, MASSES["moteur"], None)
        d[f"disque{k}"] = (disque_tournant(a), MASSES["disque"], None)
        d[f"esc{k}"] = (pose_esc(k - 1) * forme_esc(), MASSES["esc"], None)
        d[f"xt60{k}"] = (pose_fiche(k - 1) * P.fiche_xt60(XT60_FICHE_H), MASSES["xt60"] / 2, None)
    zt = Z_PLATEAU + E_PLATEAU
    d["bno055"] = (Pos(0, 0, zt - 1.0) * Rot(0, 0, -90) * P.bno055(), MASSES["bno055"], None)
    for k, xb in enumerate(X_BARRETTES, 1):
        d[f"barrette{k}"] = (Pos(xb, 0, zt + BORNIER_H - 2.6) * Rot(0, 0, 90) * P.barrette(), MASSES["barrette"], None)
    d["carte"] = (pose_carte() * P.carte_xt60(), MASSES["pdb"] + 4 * MASSES["xt60"] / 2 + MASSES["xt60"], None)
    d["xt60_alim"] = (pose_fiche_entree() * Pos(0, 0, 0) * P.fiche_xt60(FICHE_ENTREE), MASSES["xt60"] / 2, None)
    for k, (x, y) in enumerate(POS_ENTRETOISES, 1):
        d[f"entretoise{k}"] = (Pos(x, y, Z_PLATEAU + E_PLATEAU) * P.entretoise_m3(), MASSES["entretoise"], None)
    for nom, (fam, solide, _, m) in K.solides().items():        # câblage : tubes au diamètre réel, masse linéique
        d["c_" + nom] = (solide, m, None)
    tg, ec = P.tige_equilibrage(), P.ecrou_m6()                  # équilibrage : 4 tiges M6, écrous de serrage et de réglage
    for k, a in enumerate(EQ_FACES, 1):
        d[f"eq_tige{k}"] = (Location(P.plan_tige_equilibrage(a)) * tg, MASSES["tige_m6"], None)
    for i, (k, a, z, role, j) in enumerate(P.ecrous_equilibrage(), 1):
        d[f"eq_ecrou{k + 1}_{i}"] = (Location(P.plan_tige_equilibrage(a)) * Pos(0, 0, z) * ec, MASSES["ecrou_m6"], None)
    return d


# hauteurs de pivot contrôlées : les 5 rangées d'inserts, la position équilibrée et les deux bouts des lumières des paliers
PIVOTS_VERIF = tuple(sorted({*Z_PIVOTS, Z_PIVOT_EQUILIBRE, max(Z_PIVOTS) + PALIER_REGLAGE, min(Z_PIVOTS) - PALIER_REGLAGE},
                            reverse=True))


def cardan(zp):
    """Pièces qui tournent avec le croisillon (roulis seul) et pièces liées au moyeu (paliers), au pivot zp."""
    lie_croix = {"croisillon": (Pos(0, 0, zp) * P.croisillon(), None, RHO_PLEIN),
                 "tige": (Pos(0, 0, zp) * Rot(90, 0, 0) * Cylinder(D_TIGE / 2, TIGE, align=P.C), MASSES["tige"], None)}
    lie_moyeu = {}
    for s in (-1, 1):
        pl = Plane(origin=(0, s * R_PAROI, zp), x_dir=(-s, 0, 0), z_dir=(0, s, 0))
        lie_moyeu[f"palier{s}"] = (Location(pl) * P.palier(), None, RHO_IMPRIME)
        pc = Plane(origin=(0, s * (R_PAROI + PALIER[2] + 0.5), zp), x_dir=(-s, 0, 0), z_dir=(0, s, 0))
        lie_croix[f"collier{s}"] = (Location(pc) * P.collier(), None, RHO_PLEIN)
    return lie_croix, lie_moyeu


def fixe(zp, z_socle, l_tube):
    f = {"fourche": Pos(0, 0, zp) * P.fourche()}
    zb = zp - FOURCHE_BASE[0] - FOURCHE_BASE[1]
    f["tube"] = Pos(0, 0, zb + EMMANCHEMENT - l_tube) * (Cylinder(TUBE[0] / 2, l_tube, align=P.MIN))
    if z_socle is not None:
        f["socle"] = Pos(0, 0, z_socle) * P.socle()
    return f


def rotation(phi, theta, zp):
    """Roulis phi (autour de X, croisillon) puis tangage theta (autour de Y tourné), autour du pivot."""
    return Pos(0, 0, zp) * Rot(phi, 0, 0) * Rot(0, theta, 0) * Pos(0, 0, -zp)


def matrice(phi, theta):
    a, b = math.radians(phi), math.radians(theta)
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    return rx @ ry


def sommets(forme):
    v, _ = forme.tessellate(0.5, 0.5)
    return np.array([[p.X, p.Y, p.Z] for p in v])


def boite_np(V):
    return V.min(0), V.max(0)


def recouvre(a, b, marge=0.0):
    return bool(np.all(a[0] - marge <= b[1]) and np.all(b[0] - marge <= a[1]))


def inter(a, b):
    ba, bb = a.bounding_box(), b.bounding_box()
    if (ba.min.X > bb.max.X or bb.min.X > ba.max.X or ba.min.Y > bb.max.Y or bb.min.Y > ba.max.Y
            or ba.min.Z > bb.max.Z or bb.min.Z > ba.max.Z):
        return 0.0
    try:
        r = a & b                             # build123d renvoie None quand l'intersection est vide
        return 0.0 if r is None else r.volume
    except Exception:
        return float("nan")


def masse(forme, m, rho):
    return m if m is not None else forme.volume / 1000.0 * rho


def main():
    moteur = moteur_equivalent()
    rendus = sys.argv[1] if len(sys.argv) > 1 else None
    dev = dispositif(moteur)
    croix0, moy0 = cardan(0.0)
    # 1. interférences au repos (dispositif, paliers et cardan au pivot le plus haut et le plus bas)
    print("1. interférences au repos (> 0,5 mm3)", flush=True)
    for zp in (PIVOTS_VERIF[0], Z_PIVOT_EQUILIBRE, PIVOTS_VERIF[-1]):
        lc, lm = cardan(zp)
        tout = {**{k: v[0] for k, v in dev.items()}, **{k: v[0] for k, v in lc.items()}, **{k: v[0] for k, v in lm.items()},
                "fourche": Pos(0, 0, zp) * P.fourche()}
        n = 0
        for (na, a), (nb, b) in itertools.combinations(tout.items(), 2):
            if na[:-1] == "moteur" and nb == "disque" + na[-1] or nb[:-1] == "moteur" and na == "disque" + nb[-1]:
                continue                       # le disque est monté sur l'arbre de son moteur
            if {na, nb} <= {"tige", "croisillon"} or (na.startswith("collier") and nb == "tige") or (nb.startswith("collier") and na == "tige"):
                continue
            if any(x.startswith("eq_ecrou") and y == "eq_tige" + x[8:].split("_")[0] for x, y in ((na, nb), (nb, na))):
                continue                       # l'écrou est vissé sur sa tige
            v = inter(a, b)
            if v != v or v > 0.5:
                n += 1
                print(f"   pivot {zp:+.0f} : {na} / {nb} : {v:.1f} mm3")
        print(f"   pivot {zp:+.0f} : {n} interférence(s)", flush=True)
    # 4. masses et centre de gravité (au repos, cardan au pivot équilibré)
    lc, lm = cardan(Z_PIVOT_EQUILIBRE)
    elems = {**dev, **lm, **lc}
    M = sum(masse(*v) for v in elems.values())
    G = sum(masse(*v) * np.array(tuple(v[0].center())) for v in elems.values()) / M
    print(f"\n4. masse du dispositif (avec croisillon, tige, paliers, colliers) : {M:.0f} g ; centre de gravité "
          f"x {G[0]:+.2f}, y {G[1]:+.2f}, z {G[2]:+.2f} mm")
    for k in ("moteur", "disque", "esc", "carter", "platine", "xt60", "porte", "tcrt", "c_", "eq_"):
        print(f"   {k} : {sum(masse(*v) for n, v in elems.items() if n.startswith(k)):.0f} g")
    for n in ("moyeu", "plateau", "bornier", "carte"):
        print(f"   {n} : {masse(*elems[n]):.0f} g")
    print("   pivot (z) | h = zG − zpivot | couple de gravité à 10° | à 5°")
    for zp in PIVOTS_VERIF:
        h = G[2] - zp
        c10 = M / 1000 * 9.81 * h / 1000 * math.sin(math.radians(10))
        c5 = M / 1000 * 9.81 * h / 1000 * math.sin(math.radians(5))
        print(f"   {zp:+6.0f}   | {h:+6.1f} mm | {c10:+.3f} N·m | {c5:+.3f} N·m")
    # 2-3. balayage : sommets des maillages tournés en numpy ; intersection exacte seulement si les boîtes se recouvrent
    print("\n2. balayage du cardan (roulis, tangage de −20 à +20°) contre fourche et poteau ; 3. point le plus bas", flush=True)
    pire, bas_pivot = None, {}
    for zp in PIVOTS_VERIF:
        lc, lm = cardan(zp)
        mobile = {k: v[0] for k, v in {**dev, **lm}.items()}
        V = {k: sommets(f) for k, f in mobile.items()}
        fix = fixe(zp, None, 200.0)
        Bf = {k: boite_np(sommets(f)) for k, f in fix.items()}
        Vc = sommets(lc["croisillon"][0])
        piv = np.array([0, 0, zp])
        bas, n = 1e9, 0
        for phi, theta in itertools.product((-20, -10, 0, 10, 20), repeat=2):
            Rm = matrice(phi, theta)
            for nm, v in V.items():
                w = (v - piv) @ Rm.T + piv
                bas = min(bas, w[:, 2].min())
                bw = boite_np(w)
                for nf, bf in Bf.items():
                    if recouvre(bw, bf):
                        vol = inter(rotation(phi, theta, zp) * mobile[nm], fix[nf])
                        if vol != vol or vol > 0.5:
                            n += 1
                            print(f"   pivot {zp:+.0f}, roulis {phi:+d}, tangage {theta:+d} : {nm} / {nf} : {vol:.1f} mm3", flush=True)
            wc = (Vc - piv) @ matrice(phi, 0).T + piv
            if recouvre(boite_np(wc), Bf["fourche"]):
                vol = inter(rotation(phi, 0, zp) * lc["croisillon"][0], fix["fourche"])
                if vol != vol or vol > 0.5:
                    n += 1
                    print(f"   pivot {zp:+.0f}, roulis {phi:+d} : croisillon / fourche : {vol:.1f} mm3", flush=True)
        rel = bas - zp
        bas_pivot[zp] = rel
        print(f"   pivot {zp:+.0f} : {n} contact(s) ; point le plus bas à {-rel:.1f} mm sous le pivot", flush=True)
        if zp in Z_PIVOTS:                             # le socle est dimensionné sur les rangées d'inserts
            pire = rel if pire is None else min(pire, rel)
    # socle : son dessus sous le point le plus bas, avec une marge ; poteau de longueur unique
    zb_fourche = -FOURCHE_BASE[0] - FOURCHE_BASE[1]        # bas de la fourche sous le pivot
    z_socle = pire - MARGE_SOCLE
    l_tube = (zb_fourche + EMMANCHEMENT) - (z_socle - SOCLE[2])
    print(f"\n3. dessus du socle à {-z_socle:.0f} mm sous le pivot ; poteau de {l_tube:.0f} mm (fourche à {-zb_fourche:.0f} mm "
          f"sous le pivot, emmanchement {EMMANCHEMENT:.0f}, traverse le socle) ; centre de rotation à "
          f"{-z_socle + SOCLE[2]:.0f} mm au-dessus de la table")
    for zp in (Z_PIVOT_EQUILIBRE, PIVOTS_VERIF[0]):
        print(f"   socle monté (Z_SOCLE {Z_SOCLE:.0f}) : pivot {zp:+.0f}, garde de {bas_pivot[zp] - Z_SOCLE:.1f} mm "
              "sous le point le plus bas à ±20° combinés")
    if rendus:
        os.makedirs(rendus, exist_ok=True)
        np.save(os.path.join(rendus, "socle.npy"), np.array([z_socle, l_tube]))
    return z_socle, l_tube


if __name__ == "__main__":
    main()
