"""Rendus du banc de stabilisation (matplotlib), dans rendus/ :
- banc_vues.png : repos en perspective, incliné de +20° sur les deux axes, face, dessus (planche titrée, pour le README) ;
- vue_iso.png, vue_inclinee.png, vue_face.png, vue_dessus.png : les mêmes vues séparées, sans titre (documentation) ;
- cardan_coupe.png : coupe du cardan par le plan XZ ;
- etage.png : dessus du dispositif (ESC debout autour du BNO055, bornier à deux rangées, câbles) ;
- cablage.png : le câblage seul et les appareils qu'il relie ;
- distribution.png : la carte de distribution XT60 sur ses entretoises, fiches et fils d'alimentation des ESC ;
- corps.png : le corps sans plateau, boucles des fils moteur ;
- module_roue.png : platine, moteur, disque, carter, potence et carte TCRT5000 ;
- equilibrage.png : le corps, ses paliers à lumières et les 4 tiges d'équilibrage avec leurs écrous.

Usage : python rw_rendus.py [vues] [cardan] [interface] [module] [equilibrage]   (Python avec build123d et matplotlib ;
sans argument, tous les rendus, environ 20 min)
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from build123d import Box, Cylinder, Location, Pos, Rot, import_step
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.stdout.reconfigure(encoding="utf-8")
ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import rw_pieces as P
import rw_verif as V
from rw_params import *  # noqa: F401,F403

DOSSIER = os.path.dirname(ICI)
RENDUS = os.path.join(DOSSIER, "rendus")
STEP_A2212 = os.path.join(os.path.dirname(DOSSIER), "A2212 BLDC Motor v1.step")
COULEURS = {"moyeu": "#4C72B0", "platine": "#DD8452", "carter": "#BBBBBB", "moteur": "#555555", "disque": "#C44E52",
            "esc": "#8172B3", "plateau": "#6A8FC8", "bornier": "#DD8452", "barrette": "#222222", "bno055": "#2CA02C",
            "xt60": "#E8C547", "carte": "#2B2B2B", "entretoise": "#C9A227", "palier": "#DD8452", "collier": "#DD8452", "croisillon": "#E8A33D",
            "tige": "#333333", "fourche": "#937860", "tube": "#999999", "socle": "#937860", "porte": "#DD8452",
            "tcrt": "#1F6E43", "c_moteur": "#2E5FD0", "c_alim": "#D03030", "c_branche": "#A02020", "c_principal": "#A02020",
            "c_commande": "#E377C2", "c_capteur": "#17BECF", "c_bno": "#2CA02C", "c_nappe": "#9467BD",
            "eq_tige": "#8C8C8C", "eq_ecrou": "#C9A227"}
IGNORES = ()


def couleur(nom):
    return next((v for k, v in COULEURS.items() if nom.startswith(k)), "#888888")


def triangles(forme, c, T=None, tol=0.6):
    if T is not None:
        forme = T * forme
    v, f = forme.tessellate(tol, tol)
    Vv = np.array([[p.X, p.Y, p.Z] for p in v])
    return [Vv[list(t)] for t in f], [c] * len(f)


def dessiner(ax, tris, cols, lumiere=(0.4, -0.5, 0.77), limites=None):
    t = np.array(tris)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    lum = 0.55 + 0.45 * np.abs(n @ np.array(lumiere))
    rgba = matplotlib.colors.to_rgba_array(cols)
    rgba[:, :3] *= lum[:, None]
    ax.add_collection3d(Poly3DCollection(t, facecolors=rgba, edgecolors="none", linewidths=0))
    if limites is None:
        lo, hi = t.reshape(-1, 3).min(0), t.reshape(-1, 3).max(0)
        c, r = (lo + hi) / 2, (hi - lo).max() / 2
        limites = [(c[k] - r, c[k] + r) for k in range(3)]
    ax.set_xlim(*limites[0]); ax.set_ylim(*limites[1]); ax.set_zlim(*limites[2])
    ax.set_box_aspect([b - a for a, b in limites])
    ax.set_axis_off()


def scene(dev, lc, lm, fix, zp, phi, theta):
    T = V.rotation(phi, theta, zp)
    Tc = Pos(0, 0, zp) * Rot(phi, 0, 0) * Pos(0, 0, -zp)
    tris, cols = [], []
    for n, (f, *_) in {**dev, **lm}.items():
        if n not in IGNORES:
            a, b = triangles(f, couleur(n), T); tris += a; cols += b
    for n, (f, *_) in lc.items():
        a, b = triangles(f, couleur(n), Tc); tris += a; cols += b
    for n, f in fix.items():
        a, b = triangles(f, couleur(n)); tris += a; cols += b
    return tris, cols


def main():
    choix = set(sys.argv[1:]) or {"vues", "cardan", "interface", "module", "equilibrage"}
    os.makedirs(RENDUS, exist_ok=True)
    zp = Z_PIVOT_EQUILIBRE
    moteur = import_step(STEP_A2212)
    dev = V.dispositif(V.moteur_equivalent())
    for k, a in enumerate(ANGLES_ROUES, 1):
        dev[f"moteur{k}"] = (Location(P.plan_roue(a, R_APPUI + 2)) * moteur, None, None)
        e0, e1, re = DISQUE
        dev[f"disque{k}"] = (Location(P.plan_roue(a, R_APPUI + e0)) * disque_ajoure(), None, None)
    lc, lm = V.cardan(zp)
    fix = V.fixe(zp, zp + Z_SOCLE, TUBE[2] + 4)
    vues = [("vue_iso", 0, 0, 22, -55, "repos, vue isométrique"), ("vue_inclinee", 20, 20, 22, -55, "roulis +20°, tangage +20°"),
            ("vue_face", 0, 0, 0, -90, "repos, vue de face (plan XZ)"), ("vue_dessus", 0, 0, 90, -90, "repos, vue de dessus")]
    planche = plt.figure(figsize=(18, 12))
    for i, (nom, phi, theta, el, az, titre) in enumerate(vues if "vues" in choix else []):
        tris, cols = scene(dev, lc, lm, fix, zp, phi, theta)
        for fig, ax in ((planche, planche.add_subplot(2, 2, i + 1, projection="3d")),
                        (None, None)):
            if fig is None:
                fig = plt.figure(figsize=(8, 8))
                ax = fig.add_subplot(projection="3d")
                fig.subplots_adjust(0, 0, 1, 1)
            dessiner(ax, tris, cols)
            ax.view_init(elev=el, azim=az)
            if fig is planche:
                ax.set_title(titre)
            else:
                fig.savefig(os.path.join(RENDUS, nom + ".png"), dpi=90, transparent=True, bbox_inches="tight", pad_inches=0)
                plt.close(fig)
    if "vues" in choix:
        planche.tight_layout()
        planche.savefig(os.path.join(RENDUS, "banc_vues.png"), dpi=75)
    plt.close(planche)
    if "cardan" in choix:
        cardan_coupe(dev, lc, lm, zp)
    if "interface" in choix:
        interface(dev)
        interieur(dev)
    if "module" in choix:
        module_roue(moteur)
    if "equilibrage" in choix:
        equilibrage(dev, lm)
    print("rendus écrits dans", RENDUS)


def equilibrage(dev, lm):
    """equilibrage.png : le corps sans plateau ni carters, platines, paliers de tangage à lumières, les 4 tiges M6 et
    leurs écrous (serrage contre la paroi, paquets de réglage)."""
    d = {**dev, **lm}
    noms = ["moyeu"] + [f"platine{k}" for k in range(1, 5)] + [n for n in d if n.startswith(("eq_", "palier"))]
    _vue(d, noms, "equilibrage.png", [(-125, 125), (-125, 125), (-75, 75)], 22, -32, taille=(11, 9), tol=0.2)


def cardan_coupe(dev, lc, lm, zp):
    # coupe du cardan : on garde y > 0 et on regarde depuis −Y
    coupe = Pos(0, 100, 0) * Box(400, 200, 600)
    items = [(P.moyeu() & coupe, "#4C72B0"), (P.plateau() & coupe, "#6A8FC8"), (Pos(0, 0, zp) * P.fourche(), "#937860"),
             (Pos(0, 0, zp - 40 - 60) * Cylinder(6, 78, align=P.MIN), "#999999"),
             (dev["bno055"][0], "#2CA02C")]
    items += [(f, "#E8A33D" if n == "croisillon" else ("#333333" if n == "tige" else "#DD8452")) for n, (f, *_) in lc.items()]
    items += [(f, "#C96A3B") for n, (f, *_) in lm.items()]
    items += [(Location(P.plan_roue(a)) * P.platine(), "#DD8452") for a in ANGLES_ROUES[:2]]
    tris, cols = [], []
    for f, c in items:
        a, b = triangles(f, c, tol=0.4); tris += a; cols += b
    fig = plt.figure(figsize=(14, 7))
    for i, (el, az) in enumerate([(12, -90), (25, -60)]):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        dessiner(ax, tris, cols, lumiere=(0.3, -0.8, 0.5), limites=[(-95, 95), (-95, 95), (-110, 80)])
        ax.view_init(elev=el, azim=az)
    fig.subplots_adjust(0, 0, 1, 1, wspace=0)
    fig.savefig(os.path.join(RENDUS, "cardan_coupe.png"), dpi=80, transparent=True)
    plt.close(fig)


def disque_ajoure():
    """Disque d'origine, représenté avec ses 4 rayons (moyeu, 4 rayons de 11 mm, jante de r 50 à 60) : face côté moteur à
    z = 0. Le modèle d'origine (disque.SLDPRT) n'est pas modifié ; les contrôles prennent le disque plein."""
    e = DISQUE[1] - DISQUE[0]
    d = Cylinder(12.0, e, align=P.MIN) + (Cylinder(DISQUE[2], e, align=P.MIN) - Cylinder(50.0, e, align=P.MIN))
    for k in range(4):
        d += Rot(0, 0, 45 + 90 * k) * Pos(31.0, 0, 0) * Box(40.0, 11.0, e, align=P.MIN)
    return d


def _vue(dev, noms, fichier, limites, el, az, taille=(10, 8), tol=0.3):
    tris, cols = [], []
    for n in noms:
        a, b = triangles(dev[n][0], couleur(n), tol=tol); tris += a; cols += b
    fig = plt.figure(figsize=taille)
    ax = fig.add_subplot(projection="3d")
    dessiner(ax, tris, cols, limites=limites)
    ax.view_init(elev=el, azim=az)
    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(os.path.join(RENDUS, fichier), dpi=90, transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def interface(dev):
    """etage.png : le dessus du dispositif, ESC debout autour du BNO055, bornier, câbles ; cablage.png : le câblage
    seul, avec les appareils qu'il relie."""
    cab = [n for n in dev if n.startswith("c_")]
    app = ["bornier", "barrette1", "barrette2", "bno055", "carte", "xt60_alim"] + [f"{n}{k}" for n in ("esc", "xt60", "tcrt", "entretoise") for k in range(1, 5)]
    struct = ["moyeu", "plateau"] + [f"{n}{k}" for n in ("platine", "carter", "porte") for k in range(1, 5)]
    _vue(dev, struct + app + cab, "etage.png", [(-150, 150), (-150, 150), (-60, 120)], 50, -125, taille=(11, 9))
    _vue(dev, app + cab, "cablage.png", [(-150, 150), (-150, 150), (-60, 120)], 38, -125, taille=(11, 9))


def interieur(dev):
    """distribution.png : l'étage de près, carte de distribution XT60 sur ses entretoises, fiches des ESC branchées,
    fils d'alimentation, BNO055 dessous ; corps.png : le corps sans plateau, boucles des fils moteur contre les faces."""
    noms = ["plateau", "bno055", "carte", "xt60_alim"] + [f"{n}{k}" for n in ("esc", "xt60", "entretoise", "c_alim") for k in range(1, 5)]
    _vue(dev, noms + ["c_principal"], "distribution.png", [(-90, 90), (-90, 90), (40, 160)], 32, -60, taille=(10, 8))
    noms = ["moyeu"] + [f"{n}{k}" for n in ("platine", "c_moteur") for k in range(1, 5)]
    _vue(dev, noms, "corps.png", [(-100, 100), (-100, 100), (-60, 100)], 62, -118)


def module_roue(moteur):
    """Face du corps à l'origine, axe du moteur selon +X ; vu de trois quarts : platine, moteur, disque ajouré, carter,
    potence et carte TCRT5000 devant un rayon du disque."""
    L = Location(P.plan_roue(0.0, 0.0))
    items = [(L * P.platine(), "#DD8452"),
             (Location(P.plan_roue(0.0, E_PLATINE + 2)) * moteur, "#555555"),
             (Location(P.plan_roue(0.0, E_PLATINE + DISQUE[0])) * disque_ajoure(), "#C44E52"),
             (L * P.carter(), "#BBBBBB"),
             (L * P.porte_capteur(), "#E8A33D"),
             (L * Pos(0, TCRT_V, W_CARTE) * Rot(180, 0, 0) * P.tcrt(), "#1F6E43")]
    tris, cols = [], []
    for f, c in items:
        a, b = triangles(f, c); tris += a; cols += b        # 0,6 : une face du modèle A2212 refuse une maille plus fine
    fig = plt.figure(figsize=(9, 8))
    ax = fig.add_subplot(projection="3d")
    dessiner(ax, tris, cols)
    ax.view_init(elev=18, azim=-38)
    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(os.path.join(RENDUS, "module_roue.png"), dpi=90, transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


if __name__ == "__main__":
    main()
