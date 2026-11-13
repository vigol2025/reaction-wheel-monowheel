"""Géométrie des pièces du banc de stabilisation (build123d), chacune dans son repère propre, et leurs positions dans
le repère du dispositif (voir rw_params.py). Version 3 : ESC debout sur l'étage (plateau), XT60 et nœud du faisceau
sous le plateau, capteur de vitesse sur une potence vissée au carter, qui lit les rayons du disque.

Pièces imprimées : RW-01 corps central, RW-02 platine moteur, RW-03 carter (avec bossage de potence), RW-04 palier de
tangage, RW-05 collier de blocage, RW-06 croisillon, RW-07 fourche de roulis, RW-08 plateau supérieur (étage des ESC),
RW-09 berceau de batterie (phase batterie, hors montage), RW-10 socle, RW-11 bornier à deux rangées, RW-12 potence du
capteur de vitesse.
Composants du commerce représentés en volumes simples : roulements 625-2Z, tige Ø5, vis épaulées, tube Ø12, entretoises,
batterie, ESC, BNO055, carte TCRT5000, XT60, interrupteur, barrettes mâles, paires XT60 et nœud du faisceau existant.

Usage : python rw_pieces.py <dossier de sortie des STEP> [pièces]   (Python avec build123d)
"""
import math
import os
import sys

from build123d import (Align, Box, CenterArc, Cone, Cylinder, Location, Plane, Polygon, Pos, RegularPolygon, Rot, SlotArc,
                       SlotOverall, Solid, export_step, extrude, loft)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rw_params import *  # noqa: F401,F403

C = (Align.CENTER, Align.CENTER, Align.CENTER)
MIN = (Align.CENTER, Align.CENTER, Align.MIN)


# ---------------------------------------------------------------- outils
def octo_points(r_in):
    R = r_in / math.cos(math.radians(22.5))
    return [(R * math.cos(math.radians(22.5 + 45 * k)), R * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]


def octogone(r_in, z0, z1):
    return Pos(0, 0, z0) * extrude(Polygon(*octo_points(r_in), align=None), z1 - z0)


def axes_roue(a):
    """Direction de l'axe du moteur d, direction tangentielle t (t × Z = d)."""
    r = math.radians(a)
    return (math.cos(r), math.sin(r), 0.0), (-math.sin(r), math.cos(r), 0.0)


def plan_roue(a, r=R_PAROI):
    """Repère d'une face : origine sur la face extérieure du corps, x tangentiel (u), y vertical (v), z selon la
    normale sortante (w) ; pour une face diagonale, z est l'axe du moteur."""
    d, t = axes_roue(a)
    return Plane(origin=(r * d[0], r * d[1], 0.0), x_dir=t, z_dir=d)


def cyl(p, d, r, h):
    """Cylindre centré en p, d'axe d."""
    return Location(Plane(origin=p, z_dir=d)) * Cylinder(r, h, align=C)


def fente_arc(r, a0, a1, larg, h):
    """Lumière en arc (plan XY local, angles en degrés depuis +X), extrudée sur h, centrée en z."""
    return Pos(0, 0, -h / 2) * extrude(SlotArc(CenterArc((0, 0), r, a0, a1 - a0), larg), h)


def profil(points, u0, largeur):
    """Profil dans le plan (w, v) d'une face, extrudé selon u de u0 − largeur / 2 à u0 + largeur / 2."""
    s = extrude(Polygon(*points, align=None), largeur)          # le sens dépend de l'ordre des points : recentré
    bb = s.bounding_box()
    s = Pos(0, 0, -(bb.min.Z + bb.max.Z) / 2) * s
    pl = Plane(origin=(u0, 0, 0), x_dir=(0, 0, 1), z_dir=(-1, 0, 0))                # x = w, y = v
    return Location(pl) * s


def boite_face(u, v, w, du, dv, dw):
    """Boîte de la face (centre u, v ; w de w à w + dw, dw < 0 vers l'intérieur)."""
    return Pos(u, v, min(w, w + dw)) * Box(du, dv, abs(dw), align=MIN)


def vis_plateau():
    return [(R_VIS_PLATEAU * math.cos(math.radians(a)), R_VIS_PLATEAU * math.sin(math.radians(a))) for a in VIS_PLATEAU]


def fenetre_x():
    """Fenêtre d'accès aux goupilles de roulis (faces ±X) : z bas, z haut."""
    return max(min(Z_PIVOTS) - FENETRE_X[1], Z_BAS + 6.0), max(Z_PIVOTS) + FENETRE_X[1]


# ---------------------------------------------------------------- RW-01 corps central
def moyeu():
    """Caisson octogonal ouvert en haut : modules de roue sur les faces diagonales, paliers sur ±Y, fenêtres d'accès sur
    ±X. Il ne porte plus d'électronique (elle est sur l'étage) ; ses parois laissent passer les fils moteur (fente
    ouverte vers le haut, à côté de chaque moteur)."""
    ri = R_PAROI - E_PAROI
    m = octogone(R_PAROI, Z_BAS, Z_HAUT) - octogone(ri, Z_BAS, Z_HAUT)
    m += octogone(ri, Z_BAS, Z_BAS + 4) - octogone(ri - REBORD_BAS, Z_BAS, Z_BAS + 4)      # rebord bas
    d_b, h_b = BOSSAGE
    for x, y in vis_plateau():                   # bossages des vis du plateau, cône à 45° dessous (imprimé debout)
        m += Pos(x, y, Z_HAUT - h_b) * Cylinder(d_b / 2, h_b, align=MIN)
        m += Pos(x, y, Z_HAUT - h_b - d_b / 2) * Cone(0.5, d_b / 2, d_b / 2, align=MIN)
    trous = []
    for a in ANGLES_ROUES:
        L = Location(plan_roue(a))
        for w, zz in TROUS_MOTEUR:
            trous.append(L * Pos(w, zz, 0) * Cylinder(1.7, 3 * E_PAROI, align=C))
        trous.append(L * Cylinder(7.0, 3 * E_PAROI, align=C))                              # bout d'arbre, circlip
        for w, zz in VIS_PLATINE:                                                           # inserts M3 de la platine
            trous.append(L * Pos(w, zz, 0) * Cylinder(2.0, 3 * E_PAROI, align=C))
        lf, vb, uf = FENTE_FILS                                    # fente des fils moteur, ouverte en haut
        trous.append(L * Pos(uf, (vb + Z_HAUT + 2.0) / 2, 0) * Box(lf, Z_HAUT + 2.0 - vb, 3 * E_PAROI, align=C))
    zmin, zmax = min(Z_PIVOTS) - 4 - PALIER_REGLAGE, max(Z_PIVOTS) + 4 + PALIER_REGLAGE
    for s in (-1, 1):                            # faces ±Y : lumière de la tige, inserts des paliers
        trous.append(Pos(0, s * (R_PAROI - E_PAROI / 2), (zmin + zmax) / 2) * Box(6.5, 3 * E_PAROI, zmax - zmin, align=C))
        for zp in Z_PIVOTS:
            for x in (-PALIER_TROUS_X, PALIER_TROUS_X):
                trous.append(Pos(x, s * (R_PAROI - E_PAROI / 2), zp) * Rot(90, 0, 0) * Cylinder(2.0, 3 * E_PAROI, align=C))
    f0, f1 = fenetre_x()
    for s in (-1, 1):                            # faces ±X : fenêtres d'accès aux goupilles de roulis
        trous.append(Pos(s * (R_PAROI - E_PAROI / 2), 0, (f0 + f1) / 2) * Box(3 * E_PAROI, FENETRE_X[0], f1 - f0, align=C))
        for y in (-s * SORTIE_Y - 3.5, -s * SORTIE_Y + 3.5):     # colliers des câbles vers la table
            trous.append(Pos(s * (R_PAROI - E_PAROI / 2), y, -20) * Box(3 * E_PAROI, 2.2, 3.6, align=C))
    for x, y in vis_plateau():                   # inserts M3 des vis du plateau, dans les bossages
        trous.append(Pos(x, y, Z_HAUT - 4) * Cylinder(2.0, 8, align=C))
    for a in EQ_FACES:                           # passages des 4 tiges filetées d'équilibrage
        trous.append(Location(plan_tige_equilibrage(a)) * Cylinder(EQ_TIGE[0] / 2 + 0.2, 3 * E_PAROI, align=C))
    return m.cut(*trous)


def plan_tige_equilibrage(a):
    """Repère d'une tige d'équilibrage : origine sur la face extérieure de la paroi, z le long de la tige vers l'extérieur."""
    r = math.radians(a)
    n, t = (math.cos(r), math.sin(r), 0.0), (-math.sin(r), math.cos(r), 0.0)
    o = (R_PAROI * n[0] + EQ_DECALAGE * t[0], R_PAROI * n[1] + EQ_DECALAGE * t[1], EQ_Z)
    return Plane(origin=o, x_dir=t, z_dir=n)


def tige_equilibrage():
    """Tige filetée M6 × 60 (repère : face extérieure de la paroi à z = 0, tige de −paroi −EQ_INTERIEUR à l'extérieur)."""
    z0 = -E_PAROI - EQ_INTERIEUR             # construite à sa place : un cylindre déplacé s'exporterait en sous-assemblage
    return Solid.make_cylinder(EQ_TIGE[0] / 2, EQ_TIGE[1], Plane.XY.offset(z0))


def ecrou_m6():
    """Écrou hexagonal M6 (repère : centre de l'écrou, axe z)."""
    sp, h = EQ_ECROU
    return extrude(RegularPolygon(sp / math.sqrt(3), 6), h / 2, both=True) - Cylinder(EQ_TIGE[0] / 2, 2 * h, align=C)


# ---------------------------------------------------------------- RW-02 platine moteur (repère de roue)
def platine():
    """Plaque contre la face diagonale : croix de l'A2212, coin découpé au droit de la fente des fils moteur du corps, bras
    du carter."""
    p = Pos(0, (Z_BAS + Z_HAUT) / 2, 0) * Box(41.0, Z_HAUT - Z_BAS, E_PLATINE, align=MIN)
    p += Pos(0, (Z_HAUT + BARRE_R[1]) / 2, 0) * Box(BARRE[0], BARRE_R[1] - Z_HAUT, E_PLATINE, align=MIN)
    p += Pos(0, (Z_BAS - BARRE_R[1]) / 2, 0) * Box(BARRE[0], BARRE_R[1] + Z_BAS, E_PLATINE, align=MIN)
    trous = [Pos(w, zz, 0) * Cylinder(1.7, 3 * E_PLATINE, align=C) for w, zz in TROUS_MOTEUR]
    trous.append(Cylinder(7.0, 3 * E_PLATINE, align=C))
    trous += [Pos(w, zz, 0) * Cylinder(1.7, 3 * E_PLATINE, align=C) for w, zz in VIS_PLATINE]
    lf, vb, uf = FENTE_FILS                                        # coin découpé au droit de la fente du corps, ouvert en haut
    u0 = -20.5 - 1.0
    trous.append(Pos((u0 + uf + lf / 2) / 2, (vb + Z_HAUT + 2.0) / 2, 0) * Box(uf + lf / 2 - u0, Z_HAUT + 2.0 - vb, 3 * E_PLATINE, align=C))
    rb = (BARRE_R[0] + BARRE_R[1]) / 2
    trous += [Pos(0, s * rb, 0) * Cylinder(1.7, 3 * E_PLATINE, align=C) for s in (-1, 1)]     # vis du carter
    return p.cut(*trous)


# ---------------------------------------------------------------- RW-12 potence du capteur de vitesse (repère de roue)
def porte_capteur():
    """Potence vissée sur le bossage du haut du carter (2 vis M3 dans des inserts, lumières de ±2 mm pour régler
    l'écart) : son bras descend devant la face extérieure du disque, en avant des écrous d'équilibrage, et tient la carte
    TCRT5000 à plat, capteur vers les rayons du disque."""
    lb, sb, w0 = PATTE_CARTER
    lp, ep = POTENCE
    v_appui = CARTER_R[1] + sb                     # face du bossage, en haut du carter
    w_bras = W_CARTE + TCRT_CARTE[2]               # dos de la carte = dessous du bras
    v_fin = TCRT_V - 6.0
    p = Pos(0, v_appui + 1.5, (w0 + w_bras + ep) / 2) * Box(lb, 3.0, w_bras + ep - w0, align=C)       # semelle
    p += Pos(0, (v_appui + 3.0 + v_fin) / 2, w_bras + ep / 2) * Box(lp, v_appui + 3.0 - v_fin, ep, align=C)   # bras
    trous = [Pos(0, TCRT_V, w_bras) * Cylinder(1.6, 3 * ep, align=C)]                                 # vis de la carte
    for w in (35.0, 43.0):
        for dw in (-2.0, 2.0):
            trous.append(Pos(0, v_appui + 1.5, w + dw) * Rot(90, 0, 0) * Cylinder(1.7, 8, align=C))
        trous.append(Pos(0, v_appui + 1.5, w) * Box(3.4, 8, 4.0, align=C))
    return p.cut(*trous)


# ---------------------------------------------------------------- RW-03 carter (repère de roue)
def carter():
    """Anneau autour du disque, tenu par 2 barres vissées sur la platine ; en haut, un bossage jusqu'à la lèvre
    extérieure reçoit la potence du capteur (2 inserts M3)."""
    z0, z1 = E_PLATINE + CARTER_AX[0], E_PLATINE + CARTER_AX[1]
    c = Pos(0, 0, z0) * (Cylinder(CARTER_R[1], z1 - z0, align=MIN) - Cylinder(CARTER_R[0], z1 - z0, align=MIN))
    for zl in (z0, z1 - 2):
        c += Pos(0, 0, zl) * (Cylinder(CARTER_R[1], 2, align=MIN) - Cylinder(LEVRE_R, 2, align=MIN))
    rb = (BARRE_R[0] + BARRE_R[1]) / 2
    for s in (-1, 1):
        c += Pos(0, s * rb, E_PLATINE) * Box(BARRE[0], BARRE_R[1] - BARRE_R[0], z0 + 4 - E_PLATINE, align=MIN)
        c -= Pos(0, s * rb, E_PLATINE) * Cylinder(2.0, 12, align=C)     # insert M3 en bout de barre
    lb, sb, w0 = PATTE_CARTER
    v_in, v_out = CARTER_R[0] + 0.5, CARTER_R[1] + sb
    c += Pos(0, (v_in + v_out) / 2, (w0 + z1) / 2) * Box(lb, v_out - v_in, z1 - w0, align=C)
    for w in (35.0, 43.0):                                              # inserts M3 de la potence
        c -= Pos(0, v_out, w) * Rot(90, 0, 0) * Cylinder(2.0, 14, align=C)
    return c


# ---------------------------------------------------------------- RW-04 palier de tangage (repère : axe selon +Z local)
def palier():
    lx, lz, e = PALIER
    p = Box(lx, lz, e, align=MIN)
    p -= Pos(0, 0, e - ROULEMENT[1]) * Cylinder(ROULEMENT[0] / 2 + 0.05, ROULEMENT[1], align=MIN)
    p -= Cylinder(3.25, 3 * e, align=C)
    for x in (-PALIER_TROUS_X, PALIER_TROUS_X):                                      # lumières verticales : réglage du pivot
        p -= Pos(x, 0, 0) * Box(3.4, 2 * PALIER_REGLAGE, 3 * e, align=C)
        for y in (-PALIER_REGLAGE, PALIER_REGLAGE):
            p -= Pos(x, y, 0) * Cylinder(1.7, 3 * e, align=C)
    p -= Pos(0, -R_GOUPILLE, 0) * Cylinder(1.6, 3 * e, align=C)                      # blocage
    p -= fente_arc(R_GOUPILLE, 90 - BUTEE, 90 + BUTEE, 3.3, 3 * e)                    # butée ±20°
    return p


# ---------------------------------------------------------------- RW-05 collier de blocage (repère : axe selon +Z local)
def collier():
    e = 6.0
    c = Cylinder(16.0, e, align=MIN)
    c += Pos(0, 0, -0.5) * Cylinder(4.5, 0.5, align=MIN)          # portée sur la bague intérieure du roulement
    c -= Cylinder(D_TIGE / 2 + 0.05, 3 * e, align=C)
    c -= Pos(0, -R_GOUPILLE, 0) * Cylinder(1.6, 3 * e, align=C)    # goupille de blocage (amovible)
    c -= Pos(0, R_GOUPILLE, 0) * Cylinder(1.45, 3 * e, align=C)    # goupille de butée (emmanchée)
    c -= Pos(9, 0, e / 2) * Rot(0, 90, 0) * Cylinder(2.0, 16, align=C)    # vis de pression M3 (insert)
    return c


# ---------------------------------------------------------------- RW-06 croisillon (centré)
def croisillon():
    h = CROIX / 2
    c = Box(CROIX, CROIX, CROIX, align=C)
    c -= Rot(90, 0, 0) * Cylinder(D_TIGE / 2 + 0.05, 2 * CROIX, align=C)                  # tige de tangage (Y)
    for s in (-1, 1):
        c -= Pos(s * (h - 4 + 0.005), 0, 0) * Rot(0, 90, 0) * Cylinder(2.8, 8.01, align=C)   # inserts M4 (vis épaulées), fond à 6
        for z, r in ((-R_GOUPILLE, 1.6), (R_GOUPILLE, 1.45)):                                 # blocage, butée : fond à 8
            c -= Pos(s * (h - 3 + 0.005), 0, z) * Rot(0, 90, 0) * Cylinder(r, 6.01, align=C)
    c -= Pos(0, 0, h - 6) * Cylinder(2.0, 12.01, align=C)                                  # vis de pression M3
    return c


# ---------------------------------------------------------------- RW-07 fourche de roulis (pivot à l'origine)
def fourche():
    x0 = CROIX / 2 + FOURCHE_JEU
    x1 = x0 + FOURCHE_BRAS
    g, hb = FOURCHE_BASE
    f = Pos(0, 0, -g - hb) * Box(2 * x1, 2 * FOURCHE_LARGE, hb, align=MIN)
    for s in (-1, 1):
        xc = s * (x0 + x1) / 2
        f += Pos(xc, 0, -g) * Box(FOURCHE_BRAS, 2 * FOURCHE_LARGE, g, align=MIN)
        f += Pos(xc, 0, 0) * Rot(0, 90, 0) * Cylinder(FOURCHE_LARGE, FOURCHE_BRAS, align=C)
        f -= Pos(s * (x1 - ROULEMENT[1] / 2 + 0.005), 0, 0) * Rot(0, 90, 0) * Cylinder(ROULEMENT[0] / 2 + 0.05, ROULEMENT[1] + 0.01, align=C)   # fond à x1 − 5
        f -= Pos(xc, 0, 0) * Rot(0, 90, 0) * Cylinder(4.5, 2 * FOURCHE_BRAS, align=C)   # entretoise Ø8
        bras = Location(Plane(origin=(xc, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0)))
        f -= bras * Pos(0, -R_GOUPILLE, 0) * Cylinder(1.6, 3 * FOURCHE_BRAS, align=C)     # blocage
        f -= bras * fente_arc(R_GOUPILLE, 90 - BUTEE, 90 + BUTEE, 3.3, 3 * FOURCHE_BRAS)   # butée ±20°
    f -= Pos(0, 0, -g - hb) * Cylinder(TUBE[0] / 2 + 0.05, EMMANCHEMENT, align=MIN)       # poteau
    f -= Pos(x1 / 2 + 3, 0, -g - hb) * Box(x1, 2, hb - 4, align=MIN)                       # fente de serrage
    f -= Pos(x1 - 6, 0, -g - hb / 2 - 2) * Rot(90, 0, 0) * Cylinder(1.7, 2 * FOURCHE_LARGE + 2, align=C)
    return f


# ---------------------------------------------------------------- RW-08 plateau supérieur : l'étage des ESC
def dans_octogone(x, y, r):
    return all(x * math.cos(math.radians(a)) + y * math.sin(math.radians(a)) <= r for a in range(0, 360, 45))


def reperes():
    """Points gravés : k points (module k) dans le coin de son moteur, au rayon R_REPERES."""
    out = []
    for k, a in enumerate(ANGLES_ROUES, 1):
        d, t = axes_roue(a)
        for i in range(k):
            s = (i - (k - 1) / 2) * 4.0
            out.append((R_REPERES * d[0] + s * t[0], R_REPERES * d[1] + s * t[1]))
    return out


def emprises_esc(marge=0.0):
    """Boîtes (xmin, xmax, ymin, ymax) des 4 ESC avec leurs joues, dans le repère du dispositif (faces à 0, 90, 180,
    270° : les boîtes restent alignées sur les axes)."""
    e, _, _, jeu = SUPPORT_ESC
    demi = ESC[2] / 2 + jeu + e + marge
    out = []
    for a in ESC_FACE:
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        pts = [(x * c - y * s, x * s + y * c) for x in (ESC_A - demi, ESC_A + demi) for y in (-ESC[0] / 2 - marge, ESC[0] / 2 + marge)]
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        out.append((min(xs), max(xs), min(ys), max(ys)))
    return out


def _dans_encoche(x, y, marge):
    for c in ESC_COIN_MOTEUR:
        r = math.radians(c)
        xl, yl = x * math.cos(r) + y * math.sin(r), -x * math.sin(r) + y * math.cos(r)
        if xl >= ENCOCHE_COIN[1] - marge and abs(yl) <= ENCOCHE_COIN[0] / 2 + marge:
            return True
    return False


def passe_colliers():
    """Centres et sens (True : tunnel selon X) des passe-colliers, sur une grille au pas de 10 mm en damier, hors des
    ESC et de leurs fentes de collier, des encoches, du BNO055, de la flèche, du bornier, des vis et des repères."""
    w, _, l, pas = PASSE_COLLIER
    cercles = [(x, y, 6.0) for x, y in vis_plateau()] + [(x, y, 3.8) for x, y in POS_ENTRETOISES] + \
              [(x, y, 3.0) for x, y in PIONS_BORNIER] + [(x, y, 3.0) for x, y in reperes()]
    rects = [(-BNO_LOGEMENT[0] / 2 - 2, BNO_LOGEMENT[0] / 2 + 2, -BNO_LOGEMENT[1] / 2 - 2, BNO_LOGEMENT[1] / 2 + 2),
             (FLECHE[0] - 1, FLECHE[0] + FLECHE[2] + 1, FLECHE[1] - 5, FLECHE[1] + 5),
             (-99, BORNIER_X[1] + 1.5, -26, 26)] + emprises_esc(SANGLE_ESC[1] + 3.0)
    out = []
    for i in range(-8, 9):
        for j in range(-8, 9):
            x, y, selon_x = i * pas, j * pas, (i + j) % 2 == 0
            hx, hy = (l / 2 + 1, w / 2 + 1) if selon_x else (w / 2 + 1, l / 2 + 1)
            coins = [(x + sx * hx, y + sy * hy) for sx in (-1, 1) for sy in (-1, 1)] + [(x, y)]
            if not all(dans_octogone(cx, cy, R_PAROI - 3) for cx, cy in coins):
                continue
            if any(x + hx > a and x - hx < b and y + hy > c and y - hy < d for a, b, c, d in rects):
                continue
            if any(_dans_encoche(cx, cy, 2.0) for cx, cy in coins):
                continue
            if any(math.hypot(max(abs(cx - x) - hx, 0), max(abs(cy - y) - hy, 0)) < r for cx, cy, r in cercles):
                continue
            out.append((x, y, selon_x))
    return out


def plateau():
    """L'étage : il ferme le corps (4 vis M3) et porte le BNO055 au centre, les 4 ESC debout en couronne autour, entre
    deux joues, tenus chacun par deux colliers, et le bornier sur le bord −X. Dans chaque coin, une encoche ouverte sur
    le bord laisse monter les fils moteur et descendre les fils d'alimentation vers les XT60 sous
    le plateau. Passe-colliers dans l'épaisseur pour les câbles de signal, dessus, et les XT60 et le nœud, dessous."""
    z0, z1 = Z_PLATEAU, Z_PLATEAU + E_PLATEAU
    p = octogone(R_PAROI, z0, z1)
    e, h, l, jeu = SUPPORT_ESC
    for a in ESC_FACE:                                                   # joues des ESC
        for s in (-1, 1):
            xw = ESC_A + s * (ESC[2] / 2 + jeu + e / 2)
            p += Rot(0, 0, a) * Pos(xw, 0, z1) * Box(e, l, h, align=MIN)
    trous = [Pos(x, y, z0) * Cylinder(1.7, 3 * E_PLATEAU, align=C) for x, y in vis_plateau() + POS_ENTRETOISES]
    trous += [Pos(x, y, z0) * Cylinder(1.65, 3 * E_PLATEAU, align=C) for x, y in PIONS_BORNIER]
    lx, ly = BNO_LOGEMENT
    trous.append(Pos(0, 0, z1 - 1.0) * Box(lx, ly, 2.0, align=MIN))
    trous.append(Pos(-1.0, 0, z0) * Box(lx - 2, ly - 4, 3 * E_PLATEAU, align=C))
    lf = FLECHE[2]
    fleche = Polygon((0, -2), (lf - 4, -2), (lf - 4, -4), (lf, 0), (lf - 4, 4), (lf - 4, 2), (0, 2), align=None)
    trous.append(Pos(FLECHE[0], FLECHE[1], z1 - 0.6) * extrude(fleche, 1))
    r0, r1 = ENCOCHE_COIN[1], R_PAROI + 10.0
    for c in ESC_COIN_MOTEUR:                                            # encoches des coins, ouvertes sur le bord
        trous.append(Rot(0, 0, c) * Pos((r0 + r1) / 2, 0, z0 - 1.0) * Box(r1 - r0, ENCOCHE_COIN[0], E_PLATEAU + 2, align=MIN))
    for a in ESC_FACE:                                                   # fentes des colliers des ESC
        for s in (-1, 1):
            xs = ESC_A + s * (ESC[2] / 2 + jeu + e + 1.0 + SANGLE_ESC[1] / 2)
            for ys in (-SANGLE_ESC[2], SANGLE_ESC[2]):
                trous.append(Rot(0, 0, a) * Pos(xs, ys, z0) * Box(SANGLE_ESC[1], SANGLE_ESC[0], 3 * E_PLATEAU, align=C))
    for x, y in reperes():
        trous.append(Pos(x, y, z1 - 0.6) * Cylinder(1.0, 1.0, align=MIN))
    w, hh, l2, _ = PASSE_COLLIER
    for x, y, selon_x in passe_colliers():
        R = Pos(x, y, z0 + 1.2) * Rot(0, 0, 0 if selon_x else 90)
        trous.append(R * Box(l2, w, hh, align=MIN))
        for s in (-1, 1):
            trous.append(R * Pos(s * (l2 / 2 - 1.25), 0, 0) * Box(2.5, w, E_PLATEAU, align=MIN))
    return p.cut(*trous)


# ---------------------------------------------------------------- RW-11 bornier à deux rangées (repère du dispositif)
def bornier():
    """Bloc vissé sur le bord −X du plateau, lèvre en porte-à-faux hors du corps qui tient deux barrettes mâles 1 × 15 à
    broches longues : rangée intérieure pour les prises des 4 ESC (S + −), rangée extérieure pour les 4 capteurs de
    vitesse (V G D). Les fils Dupont vers la breadboard partent dessous, le long de la face −X."""
    z0 = Z_PLATEAU + E_PLATEAU
    z1 = z0 + BORNIER_H
    long_ = BORNIER_N * 2.54
    ly = long_ + 6
    b = Pos((BORNIER_X[0] + BORNIER_X[1]) / 2, 0, z0) * Box(BORNIER_X[1] - BORNIER_X[0], ly, BORNIER_H, align=MIN)
    xl = BORNIER_LEVRE[0]
    b += Pos((xl + BORNIER_X[0]) / 2, 0, z1 - BORNIER_LEVRE[1]) * Box(BORNIER_X[0] - xl, ly, BORNIER_LEVRE[1], align=MIN)
    trous = []
    for xb in X_BARRETTES:
        trous.append(Pos(xb, 0, z1 - 2.6) * Box(2.7, long_ + 0.3, 3, align=MIN))          # corps plastique
        trous.append(Pos(xb, 0, z1) * Box(1.6, long_ - 0.6, 3 * BORNIER_H, align=C))       # broches
    xv, yv = vis_plateau()[2]                                                           # vis M3 du plateau en −X
    trous.append(Pos(xv, yv, z0) * Cylinder(1.7, 3 * BORNIER_H, align=C))
    trous.append(Pos(xv, yv, z1 - 3.5) * Cylinder(3.25, 4, align=MIN))                  # tête CHC
    b = b.cut(*trous)
    for x, y in PIONS_BORNIER:                                                          # pions d'orientation Ø3
        b += Pos(x, y, z0 - 3) * Cylinder(1.5, 3, align=MIN)
    return b


# ---------------------------------------------------------------- RW-09 berceau de batterie (phase batterie, hors montage)
def berceau():
    lx, ly, e = BERCEAU
    z0 = Z_PLATEAU + E_PLATEAU + ENTRETOISE
    b = Pos(0, 0, z0) * Box(lx, ly, e, align=MIN)
    for s in (-1, 1):
        b += Pos(0, s * (ly / 2 - 1), z0 + e) * Box(BATTERIE[0] + 2, 2, 6, align=MIN)        # rebords latéraux
        b -= Pos(s * 30, 0, z0) * Box(3, 24, 3 * e, align=C)                                   # sangle 20 mm
        b += Pos(s * (lx / 2 - 1.5), 0, z0 + e) * Box(3, ly, 25, align=MIN)                   # flasques d'extrémité
    b -= Pos(lx / 2 - 1.5, 0, z0 + e + 13) * Box(6, 16.2, 8.4, align=C)                       # XT60 femelle
    b -= Pos(-lx / 2 + 1.5, 0, z0 + e + 13) * Box(6, 19.2, 13.2, align=C)                     # interrupteur KCD1
    for x, y in POS_ENTRETOISES:
        b -= Pos(x, y, z0) * Cylinder(1.7, 3 * e, align=C)
    return b


# ---------------------------------------------------------------- RW-10 socle (dessus du plateau à z = 0)
def socle():
    lx, ly, e = SOCLE
    d, h = MOYEU_SOCLE
    s = Pos(0, 0, -e) * Box(lx, ly, e, align=MIN)
    s += Cylinder(d / 2, h, align=MIN)
    for k in range(4):
        s += Pos(0, 0, 0) * Rot(0, 0, 45 + 90 * k) * Pos(55, 0, 0) * Box(lx * 0.5, 6, 25, align=MIN) \
            - Rot(0, 0, 45 + 90 * k) * Pos(55, 0, 25) * Rot(0, 30, 0) * Box(200, 20, 60, align=(Align.MIN, Align.CENTER, Align.MIN))
    s -= Pos(0, 0, -e) * Cylinder(TUBE[0] / 2 + 0.05, h + e, align=MIN)
    s -= Pos(d / 4 + 4, 0, 8) * Box(d / 2, 2, h, align=MIN)                                    # fente de serrage
    for z in (h - 12, h - 32):
        s -= Pos(d / 2 - 6, 0, z) * Rot(90, 0, 0) * Cylinder(2.2, d + 4, align=C)              # 2 vis M4
    for sx in (-1, 1):                                                                         # colliers des câbles (±X)
        s -= Pos(sx * (d / 2 - 4), 0, h - NAPPE_SOCLE) * Box(2.0, d + 4, 3.2, align=C)
    for sx in (-1, 1):
        for sy in (-1, 1):
            s -= Pos(sx * (lx / 2 - 12), sy * (ly / 2 - 12), -e) * Cylinder(3.25, 3 * e, align=C)
    return s


# ---------------------------------------------------------------- composants du commerce (volumes simples)
def roulement():
    return Cylinder(ROULEMENT[0] / 2, ROULEMENT[1], align=MIN) - Cylinder(ROULEMENT[2] / 2, ROULEMENT[1], align=MIN)


def boite(dim):
    return Box(*dim, align=MIN)


def vis_epaulee():
    """ISO 7379 Ø5 × 10, M4 : tête Ø8,5 × 4 (z < 0), épaulement Ø5 (z 0 à 10), filetage Ø4 × 6."""
    return (Pos(0, 0, -4) * Cylinder(4.25, 4, align=MIN) + Cylinder(D_TIGE / 2, 10, align=MIN)
            + Pos(0, 0, 10) * Cylinder(2.0, 6, align=MIN) - Pos(0, 0, -4) * Cylinder(1.5, 2.5, align=MIN))


def entretoise_roulis():
    return Cylinder(4.0, 4, align=MIN) - Cylinder(2.55, 4, align=MIN)


def bno055():
    """GY-BNO055 côté inscriptions en haut (comme sur la photo) : composants dessous, barrette 8 broches (VIN, GND,
    SCL, SDA, ADD, INT, BOOT, RST) le long d'un grand côté, broches vers le haut."""
    lx, ly, e = BNO055
    yb = -ly / 2 + 1.5
    b = Box(lx, ly, e, align=MIN) + Pos(0, 0, -1.1) * Box(5.2, 3.8, 1.1, align=MIN)
    b += Pos(0, yb, e) * Box(8 * 2.54, 2.5, 2.5, align=MIN)
    b += Pos(0, yb, -3.0) * Box(8 * 2.54 - 0.6, 0.64, 3.0 + e + 2.5 + 6.0, align=MIN)
    return b


def tcrt():
    """Carte TCRT5000 du commerce (repère : trou de fixation à l'origine, face des composants à z = 0, composants vers
    +z, dos à z = −e) : boîtier du capteur au bout +x, barrette de 4 broches couchée au bout −x (VCC, GND, D0, A0)."""
    lx, ly, e = TCRT_CARTE
    b = Pos(0, 0, -e) * Box(lx, ly, e, align=MIN) - Cylinder(1.6, 3 * e, align=C)
    bl, bw, bh = TCRT_BOITIER
    b += Pos(lx / 2 - bl / 2, 0, 0) * Box(bl, bw, bh, align=MIN)
    b += Pos(-lx / 2 + 2.5, 0, 0) * Box(5.0, 10.2, 2.5, align=MIN)            # corps de la barrette
    b += Pos(-lx / 2 - 3.0, 0, 1.25) * Box(6.0, 8.2, 0.64, align=C)            # broches couchées
    return b


def carte_xt60():
    """Carte de distribution XT60 1 vers 4 achetée (Jonronfey), encombrement : dessous de la carte à z = 0, entrée mâle
    coudée côté +X, 4 sorties femelles droites sur l'axe, LED de polarité, 4 trous M3."""
    lx, ly, e = PDB
    t, l = XT60_SECTION
    c = Box(lx, ly, e, align=MIN)
    for x, y in PDB_TROUS:
        c -= Pos(x, y, 0) * Cylinder(1.6, 3 * e, align=C)
    for x in PDB_SORTIES:
        c += Pos(x, 0, e) * (Box(t, l, XT60_DOUILLE_H, align=MIN) - Pos(0, 0, 4.0) * Box(t - 2.4, l - 2.4, XT60_DOUILLE_H, align=MIN))
    x0, x1, h = PDB_ENTREE
    c += Pos((x0 + x1) / 2, 0, e) * Box(x1 - x0, l, h, align=MIN)
    c += Pos(PDB_LED[0], PDB_LED[1], e) * Cylinder(1.5, 4.0, align=MIN)
    return c


def fiche_xt60(longueur):
    """Fiche XT60 de câble (boîtier seul), longueur selon +z."""
    return Box(XT60_SECTION[0], XT60_SECTION[1], longueur, align=MIN)


def entretoise_m3():
    """Entretoise hexagonale M3 F/F, 5,5 mm sur plats."""
    return Cylinder(5.5 / math.sqrt(3), ENTRETOISE, align=MIN) - Cylinder(1.25, ENTRETOISE, align=MIN)


def barrette():
    """Barrette mâle 1 × 15 au pas de 2,54 à broches longues (20 mm) : corps de z 0 à 2,5, broches de −11,5 à 8,5."""
    n = BORNIER_N
    b = Box(n * 2.54, 2.5, 2.5, align=MIN)
    for k in range(n):
        b += Pos((k - (n - 1) / 2) * 2.54, 0, -11.5) * Box(0.64, 0.64, 20, align=MIN)
    return b


COMMERCE = {"RW-20_Roulement-625": roulement,
            "RW-21_Tige-5x200": lambda: Cylinder(D_TIGE / 2, TIGE, align=C),
            "RW-22_Vis-epaulee-5x10-M4": vis_epaulee,
            "RW-23_Entretoise-roulis-8x4": entretoise_roulis,
            "RW-24_Goupille-3x16": lambda: Cylinder(1.5, 16, align=MIN),
            "RW-25_Tube-12x1": lambda: Cylinder(TUBE[0] / 2, TUBE[2], align=MIN) - Cylinder(TUBE[0] / 2 - TUBE[1], TUBE[2], align=MIN),
            "RW-26_Entretoise-M3x35": entretoise_m3,
            "RW-30_Batterie-LiPo-3S": lambda: Box(*BATTERIE, align=MIN),
            "RW-31_ESC-30A": lambda: Box(ESC[0], ESC[1], ESC[2], align=MIN),
            "RW-32_BNO055": bno055,
            "RW-33_TCRT5000": tcrt,
            "RW-34_XT60": lambda: Box(16.0, 16.0, 8.2, align=C),
            "RW-35_Interrupteur": lambda: Box(10.0, 19.0, 13.0, align=C),
            "RW-36_Barrette-1x15": barrette,
            "RW-37_Carte-XT60-1x4": carte_xt60,
            "RW-38_Fiche-XT60": lambda: fiche_xt60(XT60_FICHE_H),
            "RW-39_Fiche-XT60-alim": lambda: fiche_xt60(FICHE_ENTREE),
            "RW-40_Tige-filetee-M6x60": tige_equilibrage,
            "RW-41_Ecrou-M6": ecrou_m6}


PIECES = {"RW-01_Moyeu": moyeu, "RW-02_Platine-moteur": platine, "RW-03_Carter": carter, "RW-04_Palier": palier,
          "RW-05_Collier": collier, "RW-06_Croisillon": croisillon, "RW-07_Fourche": fourche,
          "RW-08_Plateau": plateau, "RW-09_Berceau": berceau, "RW-10_Socle": socle, "RW-11_Bornier": bornier,
          "RW-12_Porte-capteur": porte_capteur}


if __name__ == "__main__":
    sortie = sys.argv[1]
    os.makedirs(sortie, exist_ok=True)
    seules = set(sys.argv[2:])
    for nom, f in {**PIECES, **COMMERCE}.items():
        if seules and nom not in seules:
            continue
        p = f()
        export_step(p, os.path.join(sortie, nom + ".step"))
        b = p.bounding_box()
        print(f"{nom:24s} {p.volume / 1000:7.1f} cm3  {b.min.X:7.1f} {b.min.Y:7.1f} {b.min.Z:7.1f}  {b.max.X:7.1f} {b.max.Y:7.1f} {b.max.Z:7.1f}"
              f"  valide={p.is_valid}", flush=True)
