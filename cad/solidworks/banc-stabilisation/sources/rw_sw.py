"""Construit le banc de stabilisation dans SolidWorks (dossier Banc_stabilisation), à partir des STEP de cao/ :
pièces (corps importés), puis trois assemblages contraints au strict minimum (contraindre.py, une pièce fixe par
assemblage) :
- Module_roue : platine moteur fixe, carter, A2212, disque d'origine (sous-ensemble disque_vis d'origine, pivot libre),
  potence du capteur (sur le carter) et carte TCRT5000 ; monté 4 fois ;
- Dispositif : corps central fixe, 4 modules, plateau supérieur avec les 4 ESC debout, le bornier et ses deux
  barrettes, le BNO055 et, sur 4 entretoises, la carte de distribution XT60 1 vers 4 achetée et ses fiches ; tout le câblage
  (rw_cables.py, une pièce par famille de câbles) ; paliers de tangage et leurs roulements, à la hauteur d'équilibre
  (contrainte de distance nommée, réglable dans les lumières des paliers) ; les 4 tiges d'équilibrage M6, leurs écrous
  de serrage et les paquets d'écrous de réglage (une distance nommée par paquet) ; l'ESP32 et le régulateur restent
  sur la table ;
- Banc_stabilisation : socle fixe, poteau, fourche, roulements, croisillon (pivot de roulis), vis épaulées, tige,
  colliers, goupilles de butée et le dispositif (pivot de tangage), avec deux butées d'angle à ±20°.
Les pièces de la phase batterie (berceau, entretoises, LiPo, embase XT60, interrupteur) sont créées mais pas montées.
Les fichiers d'origine (A2212 BLDC Motor v1.step, disque_vis) ne sont que lus.

Usage : python -I rw_sw.py   (SolidWorks fermé ; Python système avec pywin32)
"""
import os
import sys

import numpy as np
import pythoncom
import win32com.client

sys.stdout.reconfigure(encoding="utf-8")
ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from contraindre import contraindre
from liaisons import COAX, DIST, A, trouver
from rw_outils_sw import ID, ajouter, butee, composant, nouvel_assemblage, ouvrir, rapport, repere, transform
from rw_params import *  # noqa: F401,F403
from swbuild import PieceImportee, application

DOSSIER = os.path.dirname(ICI)                       # Banc_stabilisation
CAO = os.path.join(DOSSIER, "cao")
ORIGINE = os.path.dirname(DOSSIER)                   # dossier SOLIDWORKS des fichiers d'origine
STEP_A2212 = os.path.join(ORIGINE, "A2212 BLDC Motor v1.step")
DISQUE_VIS = os.path.join(ORIGINE, "disque_vis.SLDASM")
ZP = Z_PIVOT_EQUILIBRE                               # pivot monté : rangée +24, paliers remontés dans leurs lumières

DESIGNATIONS = {
    "RW-01_Moyeu": ("Corps central octogonal", "PLA imprimé"), "RW-02_Platine-moteur": ("Platine moteur", "PLA imprimé"),
    "RW-03_Carter": ("Carter de disque", "PLA imprimé (PETG conseillé)"), "RW-04_Palier": ("Palier de tangage", "PLA imprimé"),
    "RW-05_Collier": ("Collier de blocage", "PLA imprimé, 100 %"), "RW-06_Croisillon": ("Croisillon", "PLA imprimé 100 %"),
    "RW-07_Fourche": ("Fourche de roulis", "PLA imprimé"), "RW-08_Plateau": ("Plateau supérieur, étage des ESC", "PLA imprimé"),
    "RW-09_Berceau": ("Berceau de batterie (phase batterie, hors montage)", "PLA imprimé"), "RW-10_Socle": ("Socle", "PLA imprimé"),
    "RW-11_Bornier": ("Bornier à deux rangées (ESC et capteurs de vitesse)", "PLA imprimé"),
    "RW-12_Porte-capteur": ("Potence du capteur de vitesse", "PLA imprimé"),
    "RW-20_Roulement-625": ("Roulement 625-2Z (5 × 16 × 5)", "Acier, commerce"), "RW-21_Tige-5x200": (f"Tige Ø5 h6 × {TIGE:.0f}", "Acier rectifié, commerce"),
    "RW-22_Vis-epaulee-5x10-M4": ("Vis épaulée ISO 7379 Ø5 × 10, M4", "Acier, commerce"),
    "RW-23_Entretoise-roulis-8x4": ("Entretoise Ø8 / Ø5 × 4", "Laiton ou acier, commerce"),
    "RW-24_Goupille-3x16": ("Goupille cylindrique Ø3 × 16 (ISO 8734)", "Acier, commerce"),
    "RW-25_Tube-12x1": (f"Tube Ø12 × 1, L {TUBE[2]:.0f}", "Aluminium, commerce"),
    "RW-26_Entretoise-M3x35": ("Entretoise hexagonale M3 × 35 F/F, sous la carte de distribution", "Laiton, commerce"),
    "RW-30_Batterie-LiPo-3S": ("Batterie LiPo 3S 2200 mAh (phase batterie, encombrement)", "Commerce"),
    "RW-31_ESC-30A": ("ESC 30 A 2-4S, BEC 5 V / 2 A (encombrement)", "Commerce"), "RW-32_BNO055": ("Module GY-BNO055 et sa barrette (encombrement)", "Commerce"),
    "RW-33_TCRT5000": ("Carte capteur réfléchissant TCRT5000 (encombrement)", "Commerce"),
    "RW-34_XT60": ("Embase XT60 femelle (phase batterie)", "Commerce"),
    "RW-35_Interrupteur": ("Interrupteur à bascule KCD1 (phase batterie)", "Commerce"),
    "RW-36_Barrette-1x15": ("Barrette mâle 1 × 15, pas 2,54, broches longues", "Commerce"),
    "RW-37_Carte-XT60-1x4": ("Carte de distribution XT60 1 vers 4, Jonronfey (encombrement)", "Achetée"),
    "RW-38_Fiche-XT60": ("Fiche XT60 d'un ESC, branchée sur la carte (encombrement)", "Câblage existant"),
    "RW-39_Fiche-XT60-alim": ("Fiche XT60 du câble d'alimentation, branchée sur l'entrée de la carte", "Câblage existant"),
    "RW-40_Tige-filetee-M6x60": ("Tige filetée M6 × 60 d'équilibrage (DIN 976)", "Acier zingué, commerce"),
    "RW-41_Ecrou-M6": ("Écrou hexagonal M6 (ISO 4032), serrage et réglage de l'équilibrage", "Acier zingué, commerce"),
    "RW-50_Fils-moteur": ("Fils moteur, 3 × 16 AWG silicone, 180 mm (× 4)", "Câblage existant"),
    "RW-51_Fils-alim-ESC": ("Fils d'alimentation des ESC, 2 × 16 AWG silicone, 130 mm (× 4)", "Câblage existant"),
    "RW-52_Cable-alimentation": ("Câble d'alimentation vers l'entrée de la carte de distribution", "Câblage existant"),
    "RW-53_Cables-commande-ESC": ("Câbles de commande des ESC, 3 fils (× 4)", "Câblage existant"),
    "RW-54_Cables-capteurs": ("Câbles des capteurs de vitesse, 3 fils Dupont (× 4)", "Commerce"),
    "RW-55_Cable-BNO055": ("Câble du BNO055, 4 fils Dupont", "Commerce"),
    "RW-56_Nappe-signaux": ("Nappe des signaux vers la breadboard", "Commerce"),
    "A2212": ("Moteur A2212 (modèle du commerce)", "Commerce")}
CABLES = {"RW-50_Fils-moteur": (40, 90, 200), "RW-51_Fils-alim-ESC": (200, 40, 40), "RW-52_Cable-alimentation": (150, 30, 30),
          "RW-53_Cables-commande-ESC": (227, 119, 194), "RW-54_Cables-capteurs": (23, 190, 207),
          "RW-55_Cable-BNO055": (60, 170, 90), "RW-56_Nappe-signaux": (150, 110, 190)}       # couleurs des câbles
MATIERES = {"PLA": ("PLA", "ABS", "Nylon 6/10"), "Acier": ("Acier allié", "Alloy Steel", "AISI 1020"),
            "Alu": ("Alliage 6061", "6061 Alloy", "6061-T6 (SS)")}


def chemin(nom):
    return os.path.join(DOSSIER, nom + (".SLDASM" if nom in ("Module_roue", "Dispositif", "Banc_stabilisation") else ".SLDPRT"))


# ---------------------------------------------------------------- pièces
def pieces(sw, seules=()):
    sources = [(os.path.join(CAO, n + ".step"), n) for n in DESIGNATIONS if n != "A2212"] + [(STEP_A2212, "A2212")]
    for step, nom in sources:
        if seules and nom not in seules:
            continue
        p = PieceImportee(sw, step)
        if nom.startswith("RW") and nom not in CABLES:   # nos pièces : un seul corps solide, sinon l'import a échoué
            solides = list(A(p.d, "GetBodies2", 0, False) or ())
            surfaces = list(A(p.d, "GetBodies2", 1, False) or ())
            assert len(solides) == 1 and not surfaces, f"{nom} : import incomplet ({len(solides)} solides, {len(surfaces)} surfaces)"
        des, mat = DESIGNATIONS[nom]
        p.proprietes(Designation=des, Reference=nom.split("_")[0] if nom.startswith("RW") else nom, Matiere=mat,
                     Projet="Banc de stabilisation à 4 roues de réaction")
        cle = "PLA" if nom[:5] in {f"RW-{k:02d}" for k in range(1, 13)} else ("Acier" if nom[:5] in ("RW-20", "RW-21", "RW-22", "RW-24", "RW-40", "RW-41") else
                                                                           ("Alu" if nom.startswith("RW-25") else None))
        if cle:
            p.matiere(MATIERES[cle])
        if nom in CABLES:
            r, g, b = CABLES[nom]
            p.d.MaterialPropertyValues = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                                                                 [r / 255, g / 255, b / 255, 1.0, 1.0, 0.4, 0.3, 0.0, 0.0])
        p.enregistrer(chemin(nom))
        p.fermer()
        print("pièce", nom, flush=True)


# ---------------------------------------------------------------- réglages nommés (contraintes spéciales)
def _centre(F):
    return np.mean([(f.lo + f.hi) / 2 for f in F if f.lo is not None], 0)


def reglage_pivot(FM, FP, refs=()):
    """Palier de tangage : hauteur de son axe au-dessus du plan des axes des roues (plan de face du dispositif). Ses 2 vis
    passent dans des lumières : la hauteur se règle de ±PALIER_REGLAGE autour de la rangée d'inserts choisie."""
    axe = max((f for f in FM if f.kind == "cyl" and abs(f.r - 3.25) < 0.05), key=lambda f: f.aire)   # passage de la tige
    face = next(f for f in refs if f.kind == "refplan" and abs(f.n[2]) > 0.99)
    rangee = min(Z_PIVOTS, key=lambda z: abs(z - ZP))
    cote = "+Y" if _centre(FM)[1] > 0 else "−Y"
    return [(DIST, axe, face, abs(float(axe.p[2])),
             f"Hauteur du pivot de tangage, palier {cote} (rangée {rangee:+.0f} : de {rangee - PALIER_REGLAGE:+.0f} "
             f"à {rangee + PALIER_REGLAGE:+.0f} mm)")]


def _face_eq(c):
    """Face ±X ±Y portant la tige d'équilibrage la plus proche du point c : indice, normale sortante."""
    k = int(np.argmax([c[0] * math.cos(math.radians(a)) + c[1] * math.sin(math.radians(a)) for a in EQ_FACES]))
    a = math.radians(EQ_FACES[k])
    return k, np.array([math.cos(a), math.sin(a), 0.0])


def reglage_tige(FM, FP, refs=()):
    """Tige d'équilibrage : longueur engagée à l'intérieur du corps, comptée depuis la face intérieure de la paroi."""
    k, n = _face_eq(_centre(FM))
    bout = trouver(FM, "plan", n=-n)
    paroi = trouver(FP, "plan", n=-n, p=(R_PAROI - E_PAROI) * n + np.array([-n[1], n[0], 0.0]) * EQ_DECALAGE + (0, 0, EQ_Z))
    if not (bout and paroi):
        print(f"  ! tige {FACES_EQ[k]} : bout {len(bout)}, paroi {len(paroi)}", flush=True)
        return []
    b = min(bout, key=lambda f: f.p @ n)
    return [(DIST, b, paroi[0], abs((b.p - paroi[0].p) @ n), f"Tige d'équilibrage {FACES_EQ[k]} : longueur à l'intérieur du corps")]


def reglage_ecrou(FM, FP, refs=()):
    """Écrous d'équilibrage. Le premier écrou de chaque paquet de réglage est placé par une distance nommée, de sa face
    intérieure à la face extérieure de la paroi : la modifier déplace tout le paquet, les autres écrous du paquet
    s'appuyant sur lui. Les écrous de serrage s'appuient sur la paroi (contraintes trouvées seules)."""
    alesage = max((f for f in FM if f.kind == "cyl"), key=lambda f: f.aire)
    c = (alesage.lo + alesage.hi) / 2
    k, n = _face_eq(c)
    s = float(c @ n - R_PAROI)
    premier = [z for kk, a, z, role, j in ecrous_equilibrage() if kk == k and role == "reglage" and j == 0]
    if not premier or abs(s - premier[0]) > 0.05:
        return []
    face = trouver(FM, "plan", n=-n)
    paroi = trouver(FP, "plan", n=n, p=R_PAROI * n + np.array([-n[1], n[0], 0.0]) * EQ_DECALAGE + (0, 0, EQ_Z))
    if not (face and paroi):
        print(f"  ! écrou {FACES_EQ[k]} : face {len(face)}, paroi {len(paroi)}", flush=True)
        return []
    nb = EQ_ECROUS[k]
    return [(DIST, face[0], paroi[0], s - EQ_ECROU[1] / 2,
             f"Équilibrage {FACES_EQ[k]} : position du paquet de {nb} écrou{'s' if nb > 1 else ''} (distance à la paroi)")]


def reglage_tube(FM, FP):
    bas = trouver(FM, "plan", n=(0, 0, -1))
    dessous = trouver(FP, "plan", n=(0, 0, -1))
    b, d = min(bas, key=lambda f: f.p[2]), min(dessous, key=lambda f: f.p[2])
    return [(DIST, b, d, abs(b.p[2] - d.p[2]), f"Poteau : bas du tube à {abs(b.p[2] - d.p[2]):.0f} mm du dessous du socle")]


# ---------------------------------------------------------------- assemblages
def module_roue(sw):
    sub = ouvrir(sw, DISQUE_VIS, lecture=True)
    dk = composant(sub, "disque-")
    m = np.array(A(A(dk, "Transform2"), "ArrayData"))
    t_disque = m[9:12] * 1000.0                      # disque dans son sous-ensemble (rotation nulle)
    assert np.allclose(m[:9], [1, 0, 0, 0, 1, 0, 0, 0, 1], atol=1e-6), m[:9]
    sw.CloseDoc(A(sub, "GetTitle"))
    t_moteur = np.array([0, 0, E_PLATINE + 2.0])
    comps = [("RW-02_Platine-moteur", ID, (0, 0, 0)), ("RW-03_Carter", ID, (0, 0, 0)), ("A2212", ID, t_moteur),
             (DISQUE_VIS, ID, t_moteur + np.array([0, 0, 30.7]) - t_disque),
             ("RW-12_Porte-capteur", ID, (0, 0, 0)),
             ("RW-33_TCRT5000", repere((0, 0, -1), (1, 0, 0)), (0, TCRT_V, W_CARTE))]      # composants vers le disque
    regles = [("RW-03_Carter", ("RW-02",), None, None, None), ("A2212", ("RW-02",), None, None, None),
              ("disque_vis", ("A2212",), ("disque",), ((0, 0, 40.0), (0, 0, 1)), None),
              ("RW-12", ("RW-03",), None, None, None), ("RW-33", ("RW-12",), None, None, None)]
    return construire(sw, comps, "Module_roue", "RW-02_Platine-moteur", regles)


def dispositif(sw):
    comps = [("RW-01_Moyeu", ID, (0, 0, 0))]
    for a in ANGLES_ROUES:
        r = math.radians(a)
        d, t = (math.cos(r), math.sin(r), 0.0), (-math.sin(r), math.cos(r), 0.0)
        comps.append(("Module_roue", repere(d, t), (R_PAROI * d[0], R_PAROI * d[1], 0.0)))
    zt = Z_PLATEAU + E_PLATEAU
    Z = (0, 0, 1)
    comps += [("RW-08_Plateau", ID, (0, 0, 0)), ("RW-11_Bornier", ID, (0, 0, 0)),
              ("RW-32_BNO055", repere(Z, (0, -1, 0)), (0, 0, zt - 1.0))]
    comps += [("RW-36_Barrette-1x15", repere(Z, (0, 1, 0)), (xb, 0, zt + BORNIER_H - 2.6)) for xb in X_BARRETTES]
    zz = np.array(Z, float)
    for k, a in enumerate(ESC_FACE):                         # ESC debout sur le plateau, en couronne
        r = math.radians(a)
        d, t = np.array([math.cos(r), math.sin(r), 0.0]), np.array([-math.sin(r), math.cos(r), 0.0])
        comps.append(("RW-31_ESC-30A", repere(d, t), (ESC_A - ESC[2] / 2) * d + (zt + ESC[1] / 2) * zz))
    zc = zt + ENTRETOISE                                     # carte de distribution XT60 sur 4 entretoises
    comps += [("RW-26_Entretoise-M3x35", ID, (x, y, zt)) for x, y in POS_ENTRETOISES]
    comps.append(("RW-37_Carte-XT60-1x4", ID, (0, 0, zc)))
    comps += [("RW-38_Fiche-XT60", ID, (x, 0, zc + PDB[2] + XT60_DOUILLE_H)) for x in PDB_SORTIES]   # fiches des ESC
    comps.append(("RW-39_Fiche-XT60-alim", repere((1, 0, 0), (0, 0, 1)), (PDB_ENTREE[1], 0, zc + PDB[2] + PDB_ENTREE[2] / 2)))
    comps += [(n, ID, (0, 0, 0)) for n in CABLES]            # câblage : tubes dans le repère du dispositif
    for s in (1, -1):
        Rp = repere((0, s, 0), (-s, 0, 0))
        o = np.array([0, s * R_PAROI, ZP])
        comps += [("RW-04_Palier", Rp, o), ("RW-20_Roulement-625", Rp, o + Rp @ np.array([0, 0, PALIER[2] - ROULEMENT[1]]))]
    for a in EQ_FACES:                                       # équilibrage : tiges M6, puis leurs écrous dans l'ordre de montage
        n, Rt, o = _repere_tige(a)
        comps.append(("RW-40_Tige-filetee-M6x60", Rt, o))
    for k, a, z, role, j in ecrous_equilibrage():
        n, Rt, o = _repere_tige(a)
        comps.append(("RW-41_Ecrou-M6", Rt, o + z * n))
    regles = [("Module_roue", ("RW-01",), ("RW-02",), None, None), ("RW-08_Plateau", ("RW-01",), None, None, None),
              ("RW-11", ("RW-08",), None, None, None), ("RW-36", ("RW-11",), None, None, None),
              ("RW-32", ("RW-08",), None, None, None), ("RW-31", ("RW-08",), None, None, None),
              ("RW-26", ("RW-08",), None, None, None), ("RW-37", ("RW-26",), None, None, None),
              ("RW-38", ("RW-37",), None, None, None), ("RW-39", ("RW-37",), None, None, None),
              ("RW-5", ("RW-01",), None, None, None),
              ("RW-04_Palier", ("RW-01",), None, None, reglage_pivot), ("RW-20", ("RW-04",), None, None, None),
              ("RW-40", ("RW-01",), None, None, reglage_tige),
              ("RW-41", ("RW-01", "RW-40", "RW-41"), None, None, reglage_ecrou, ordre_ecrou)]
    return construire(sw, comps, "Dispositif", "RW-01_Moyeu", regles)


def ordre_ecrou(R, t):
    """Écrous posés tige par tige, de l'intérieur vers l'extérieur : chaque écrou d'un paquet s'appuie sur le précédent."""
    k, n = _face_eq(t)
    return (k, float(t @ n))


def _repere_tige(a):
    """Tige d'équilibrage de la face d'angle a : normale sortante n, rotation (z le long de la tige) et origine sur la face
    extérieure de la paroi (même repère que rw_pieces.plan_tige_equilibrage)."""
    r = math.radians(a)
    n, t = np.array([math.cos(r), math.sin(r), 0.0]), np.array([-math.sin(r), math.cos(r), 0.0])
    return n, repere(n, t), R_PAROI * n + EQ_DECALAGE * t + np.array([0.0, 0.0, EQ_Z])


def banc(sw):
    zs = ZP + Z_SOCLE
    comps = [("RW-10_Socle", ID, (0, 0, zs)), ("RW-25_Tube-12x1", ID, (0, 0, zs - SOCLE[2] + 4)),
             ("RW-07_Fourche", ID, (0, 0, ZP)), ("RW-06_Croisillon", ID, (0, 0, ZP))]
    x1 = CROIX / 2 + FOURCHE_JEU + FOURCHE_BRAS
    for s in (1, -1):
        comps += [("RW-20_Roulement-625", repere((s, 0, 0), (0, 1, 0)), (s * (x1 - ROULEMENT[1]), 0, ZP)),
                  ("RW-23_Entretoise-roulis-8x4", repere((s, 0, 0), (0, 1, 0)), (s * CROIX / 2, 0, ZP)),
                  ("RW-22_Vis-epaulee-5x10-M4", repere((-s, 0, 0), (0, 1, 0)), (s * x1, 0, ZP)),
                  ("RW-05_Collier", repere((0, s, 0), (-s, 0, 0)), (0, s * (R_PAROI + PALIER[2] + 0.5), ZP))]
    comps += [("RW-21_Tige-5x200", repere((0, 1, 0), (1, 0, 0)), (0, 0, ZP)),
              ("RW-24_Goupille-3x16", repere((1, 0, 0), (0, 1, 0)), (CROIX / 2 - 6, 0, ZP + R_GOUPILLE)),
              ("RW-24_Goupille-3x16", repere((0, 1, 0), (1, 0, 0)), (0, R_PAROI + 2.5, ZP + R_GOUPILLE)),
              ("Dispositif", ID, (0, 0, 0))]
    regles = [("RW-25", ("RW-10",), None, None, reglage_tube), ("RW-07", ("RW-25",), None, None, None),
              ("RW-20", ("RW-07",), None, None, None),
              ("RW-06", ("RW-20", "RW-07"), None, ((0, 0, ZP), (1, 0, 0)), None),
              ("RW-23", ("RW-06",), None, None, None), ("RW-22", ("RW-06", "RW-20"), None, None, None),
              ("RW-21", ("RW-06",), None, None, None), ("RW-05", ("RW-21", "RW-06"), None, None, None),
              ("RW-24", ("RW-06", "RW-05"), None, None, None),
              ("Dispositif", ("RW-21", "RW-05"), ("RW-04", "RW-20"), ((0, 0, ZP), (0, 1, 0)), None)]
    butees = [("RW-06_Croisillon", "RW-07_Fourche", (1, 0, 0), (-BUTEE, BUTEE), f"Butées de roulis (±{BUTEE:.0f}°)"),
              ("Dispositif-1/RW-01_Moyeu", "RW-06_Croisillon", (0, 1, 0), (-BUTEE, BUTEE), f"Butées de tangage (±{BUTEE:.0f}°)")]
    return construire(sw, comps, "Banc_stabilisation", "RW-10_Socle", regles, butees)


def construire(sw, comps, nom, base, regles, butees=(), souples=()):
    asm = nouvel_assemblage(sw)
    for fichier, R, t in comps:
        ch = fichier if os.path.isabs(fichier) else chemin(fichier)
        assert os.path.exists(ch), ch
        ajouter(sw, asm, ch, R, t)
    L, bilan = contraindre(sw, asm, base, regles, souples=souples, bavard=os.environ.get("LIAISONS_BAVARD") == nom)
    for mobile, ref, axe, lim, nb in butees:
        butee(L, asm, mobile, ref, axe, lim, nb)
    A(asm, "EditRebuild3")
    assert not rapport(L, nom), f"{nom} : un composant a bougé"
    dest = chemin(nom)
    assert asm.SaveAs3(dest, 0, 1) == 0, dest
    asm.SaveAs3(os.path.join(CAO, nom + ".step"), 0, 3)
    print(f"enregistré {os.path.basename(dest)} : {len(asm.GetComponents(True))} composants au premier niveau,"
          f" {len(asm.GetComponents(False))} en tout", flush=True)
    sw.CloseAllDocuments(True)
    return dest


def main():
    sw = application()
    sw.CloseAllDocuments(True)
    try:
        args = sys.argv[1:]
        if args[:1] == ["pieces"]:                     # rw_sw.py pieces RW-25_Tube-12x1 … : ces pièces, puis les assemblages
            pieces(sw, set(args[1:]))
        elif args != ["assemblages"]:
            pieces(sw)
        module_roue(sw)
        dispositif(sw)
        banc(sw)
    finally:
        sw.CloseAllDocuments(True)


if __name__ == "__main__":
    main()
