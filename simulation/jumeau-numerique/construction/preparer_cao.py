"""Données CAO communes aux deux jumeaux numériques du banc de stabilisation, version 3 (Simscape et Webots).

Écrit :
- ../geometrie/*.stl : un maillage par pièce, dans le repère de la pièce, en mm ;
- cao_jumeau.json : pour chaque pièce, sa masse, son centre de masse et son tenseur d'inertie ; pour chaque instance,
  son groupe rigide, sa rotation et sa translation ; les grandeurs de contrôle (masse, centre de gravité, inertie).

Sources : la CAO du banc (Crysteo/SOLIDWORKS/Banc_stabilisation/sources : rw_params, rw_pieces, rw_cables), qui a
produit les pièces SolidWorks ; le moteur A2212 et le disque d'origine : relevé SolidWorks du 05/11/2026
(cao_moteur_disque.json), décalé à la nouvelle distance du moteur.

Groupes rigides et leur repère :
- bati : repère fixe (origine = centre du corps au repos pour le pivot de la CAO, Z vers le haut, X roulis, Y tangage) ;
- croisillon, paliers : repère du pivot (centre du croisillon) ;
- dispositif, module1 à module4 : repère du dispositif (centre du corps, hauteur des axes des moteurs) ;
- roue1 à roue4 : repère de la roue (Z = axe du moteur vers l'extérieur, origine au centre du dispositif).

Usage : python preparer_cao.py   (Python avec build123d)
"""
import json
import math
import os
import sys

import numpy as np
from build123d import Compound, Location, Pos, Rot, export_stl
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

sys.stdout.reconfigure(encoding="utf-8")
ICI = os.path.dirname(os.path.abspath(__file__))
BANC = next(os.path.normpath(p) for p in (                       # sources de la CAO du banc : dossier de travail, ou dépôt public
    os.path.join(ICI, "..", "..", "Crysteo", "SOLIDWORKS", "Banc_stabilisation", "sources"),
    os.path.join(ICI, "..", "..", "..", "cad", "solidworks", "banc-stabilisation", "sources")) if os.path.isdir(p))
sys.path.insert(0, BANC)
import rw_cables as K
import rw_pieces as P
from rw_params import *  # noqa: F401,F403

GEO = os.path.normpath(os.path.join(ICI, "..", "geometrie"))
ZP = Z_PIVOT_DEFAUT
ECROUS, POSITIONS = EQ_ECROUS, EQ_POSITIONS
ID = np.eye(3)
Z = np.array([0.0, 0.0, 1.0])
IMPRIME = ("PLA imprimé, 2 parois et 15 % de remplissage (hypothèse de conception), 800 kg/m³", 800.0)
PLEIN = ("PLA plein (hypothèse de conception), 1240 kg/m³", 1240.0)
ACIER = ("acier, 7850 kg/m³", 7850.0)
ALU = ("aluminium, 2700 kg/m³", 2700.0)


def repere(z_dir, x_dir):
    """Rotation (vecteurs colonnes) dont les axes locaux x et z vont selon x_dir et z_dir ; y = z × x."""
    z = np.asarray(z_dir, float) / np.linalg.norm(z_dir)
    x = np.asarray(x_dir, float) / np.linalg.norm(x_dir)
    return np.column_stack([x, np.cross(z, x), z])


def de_location(loc):
    """Rotation et translation (mm) d'une Location build123d."""
    T = loc.wrapped.Transformation()
    R = np.array([[T.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)])
    t = np.array([T.Value(i, 4) for i in (1, 2, 3)])
    return R, t


def proprietes(forme, masse_kg=None, rho=None):
    """Masse (kg), centre de masse (m) et tenseur d'inertie au centre de masse (kg·m², axes de la pièce)."""
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(forme.wrapped, p)
    vol = p.Mass()                                       # mm³
    if masse_kg is None:
        masse_kg = vol * 1e-9 * rho
    k = masse_kg / vol                                   # kg/mm³
    g = p.CentreOfMass()
    M = p.MatrixOfInertia()                              # mm⁵, au centre de masse, tenseur (produits négatifs)
    I = [[M.Value(i, j) * k * 1e-6 for j in (1, 2, 3)] for i in (1, 2, 3)]
    return masse_kg, [g.X() / 1000, g.Y() / 1000, g.Z() / 1000], I


SOLIDES, INSTANCES = {}, []


def solide(cle, forme, couleur, source, masse_g=None, matiere=None, tol=0.05):
    if matiere is not None:
        m, G, I = proprietes(forme, rho=matiere[1])
        source = matiere[0]
    else:
        m, G, I = proprietes(forme, masse_kg=masse_g / 1000.0)
    export_stl(forme, os.path.join(GEO, cle + ".stl"), tolerance=tol, angular_tolerance=0.3)
    SOLIDES[cle] = {"stl": cle + ".stl", "m": m, "G": G, "I": I, "source": source, "couleur": couleur}


def instance(nom, cle, groupe, R=ID, t=(0, 0, 0)):
    INSTANCES.append({"nom": nom, "solide": cle, "groupe": groupe, "R": np.asarray(R, float).tolist(),
                      "t_mm": [float(v) for v in t]})


def main():
    os.makedirs(GEO, exist_ok=True)
    zt = Z_PLATEAU + E_PLATEAU                             # dessus du plateau
    zc = zt + ENTRETOISE                                   # dessous de la carte de distribution
    x1 = CROIX / 2 + FOURCHE_JEU + FOURCHE_BRAS

    # ------------------------------------------------------------ pièces imprimées et du commerce (CAO du banc)
    solide("RW-01_Moyeu", P.moyeu(), "#4C72B0", "", matiere=IMPRIME)
    solide("RW-02_Platine-moteur", P.platine(), "#DD8452", "", matiere=IMPRIME)
    solide("RW-03_Carter", P.carter(), "#BBBBBB", "", matiere=IMPRIME)
    solide("RW-04_Palier", P.palier(), "#DD8452", "", matiere=IMPRIME)
    solide("RW-05_Collier", P.collier(), "#DD8452", "", matiere=PLEIN)
    solide("RW-06_Croisillon", P.croisillon(), "#E8A33D", "", matiere=PLEIN)
    solide("RW-07_Fourche", P.fourche(), "#937860", "", matiere=IMPRIME)
    solide("RW-08_Plateau", P.plateau(), "#6A8FC8", "", matiere=IMPRIME)
    solide("RW-10_Socle", P.socle(), "#937860", "", matiere=IMPRIME)
    solide("RW-11_Bornier", P.bornier(), "#DD8452", "", matiere=IMPRIME)
    solide("RW-12_Potence-capteur", P.porte_capteur(), "#E8A33D", "", matiere=IMPRIME)
    C = P.COMMERCE
    solide("RW-20_Roulement-625", C["RW-20_Roulement-625"](), "#A0A0A0", "roulement 625, catalogue, 4,4 g répartis sur le volume de la CAO", masse_g=MASSES["roulement"])
    solide("RW-21_Tige-5x200", C["RW-21_Tige-5x200"](), "#333333", "", matiere=ACIER)
    solide("RW-22_Vis-epaulee-5x10-M4", C["RW-22_Vis-epaulee-5x10-M4"](), "#888888", "vis épaulée ISO 7379, catalogue, 3 g répartis sur le volume de la CAO", masse_g=MASSES["vis_epaulee"])
    solide("RW-23_Entretoise-roulis-8x4", C["RW-23_Entretoise-roulis-8x4"](), "#DD8452", "", matiere=IMPRIME)
    solide("RW-24_Goupille-3x16", C["RW-24_Goupille-3x16"](), "#505050", "", matiere=ACIER)
    solide("RW-25_Tube-12x1", C["RW-25_Tube-12x1"](), "#999999", "", matiere=ALU)
    solide("RW-26_Entretoise-M3x35", C["RW-26_Entretoise-M3x35"](), "#C9A227",
           "entretoise hexagonale M3 × 35, 1,5 g (nylon ; en laiton elle pèserait 6,3 g)", masse_g=MASSES["entretoise"])
    solide("RW-31_ESC-30A", C["RW-31_ESC-30A"](), "#8172B3", "ESC 30 A, fiche, 28 g répartis sur l'enveloppe de 80 × 32 × 14 mm", masse_g=MASSES["esc"])
    solide("RW-32_BNO055", C["RW-32_BNO055"](), "#2CA02C", "GY-BNO055, fiche, 3 g répartis sur le volume de la CAO", masse_g=MASSES["bno055"])
    solide("RW-33_TCRT5000", C["RW-33_TCRT5000"](), "#1F6E43", "carte TCRT5000, estimée, 3 g répartis sur le volume de la CAO", masse_g=MASSES["tcrt"])
    solide("RW-36_Barrette-1x15", C["RW-36_Barrette-1x15"](), "#222222", "barrette 1 × 15, estimée, 1 g répartis sur le volume de la CAO", masse_g=MASSES["barrette"])
    m_carte = MASSES["pdb"] + 4 * MASSES["xt60"] / 2 + MASSES["xt60"]
    solide("RW-37_Carte-XT60-1x4", C["RW-37_Carte-XT60-1x4"](), "#2B2B2B",
           f"carte de distribution XT60 1 vers 4 (Jonronfey), estimée : carte 20 g, 4 embases 20 g, entrée 10 g, soit {m_carte:.0f} g répartis sur le volume de la CAO", masse_g=m_carte)
    solide("RW-38_Fiche-XT60", C["RW-38_Fiche-XT60"](), "#E8C547", "fiche XT60 d'un ESC, estimée, 5 g", masse_g=MASSES["xt60"] / 2)
    solide("RW-39_Fiche-XT60-alim", C["RW-39_Fiche-XT60-alim"](), "#E8C547", "fiche XT60 du câble d'alimentation, estimée, 5 g", masse_g=MASSES["xt60"] / 2)
    solide("RW-40_Tige-filetee-M6x60", C["RW-40_Tige-filetee-M6x60"](), "#9A9A9A", "tige filetée M6 × 60 en acier, 10,6 g (0,177 g/mm)", masse_g=MASSES["tige_m6"])
    solide("RW-41_Ecrou-M6", C["RW-41_Ecrou-M6"](), "#C9A227", "écrou hexagonal M6 en acier, 2,4 g", masse_g=MASSES["ecrou_m6"])

    # ------------------------------------------------------------ câblage : une pièce par famille (repère du dispositif)
    S = K.solides()
    coul = {"moteur": "#2E5FD0", "alim": "#D03030", "faisceau": "#A02020", "commande": "#E377C2", "capteur": "#17BECF",
            "bno": "#2CA02C", "nappe": "#9467BD"}
    texte = {"moteur": "4 faisceaux de 3 fils 16 AWG silicone de 180 mm, 54 g/m",
             "alim": "4 paires de fils 16 AWG silicone de 130 mm, 36 g/m",
             "faisceau": "câble d'alimentation, 2 fils 16 AWG, partie portée par le dispositif, 36 g/m",
             "commande": "4 câbles de commande à 3 fils, 10 g/m", "capteur": "4 câbles de capteur à 3 fils Dupont, 9 g/m",
             "bno": "4 fils Dupont du BNO055, partie portée par le dispositif, 12 g/m",
             "nappe": "nappe des signaux, partie portée par le dispositif, 45 g/m"}
    for fam, fichier in K.FAMILLES.items():
        corps = [s for f, s, _, _ in S.values() if f == fam]
        masse = sum(m for f, _, _, m in S.values() if f == fam)
        solide(fichier, Compound(children=corps), coul[fam], texte[fam], masse_g=masse, tol=0.1)
        instance(fichier, fichier, "dispositif")

    # ------------------------------------------------------------ moteur A2212 et disque d'origine (relevé SolidWorks)
    ref = json.load(open(os.path.join(ICI, "cao_moteur_disque.json"), encoding="utf-8"))
    for cle, s in ref["solides"].items():
        SOLIDES[cle] = {k: s[k] for k in ("stl", "m", "G", "I", "source", "couleur")}
    recul = R_APPUI - ref["r_appui_v1_mm"]                 # le moteur est plus loin du centre qu'en version 1
    roue_ref = [i for i in ref["instances"] if i["groupe"] == "roue1"]

    # ------------------------------------------------------------ bâti (repère fixe)
    zs = ZP + Z_SOCLE
    instance("Socle", "RW-10_Socle", "bati", t=(0, 0, zs))
    instance("Poteau", "RW-25_Tube-12x1", "bati", t=(0, 0, zs - SOCLE[2] + 4))
    instance("Fourche", "RW-07_Fourche", "bati", t=(0, 0, ZP))
    for k, s in enumerate((1, -1), 1):
        instance(f"Roulement de roulis {k}", "RW-20_Roulement-625", "bati", repere((s, 0, 0), (0, 1, 0)), (s * (x1 - ROULEMENT[1]), 0, ZP))

    # ------------------------------------------------------------ croisillon (repère du pivot)
    instance("Croisillon", "RW-06_Croisillon", "croisillon")
    instance("Tige de tangage", "RW-21_Tige-5x200", "croisillon", repere((0, 1, 0), (1, 0, 0)))
    for k, s in enumerate((1, -1), 1):
        instance(f"Entretoise de roulis {k}", "RW-23_Entretoise-roulis-8x4", "croisillon", repere((s, 0, 0), (0, 1, 0)), (s * CROIX / 2, 0, 0))
        instance(f"Vis épaulée {k}", "RW-22_Vis-epaulee-5x10-M4", "croisillon", repere((-s, 0, 0), (0, 1, 0)), (s * x1, 0, 0))
        instance(f"Collier {k}", "RW-05_Collier", "croisillon", repere((0, s, 0), (-s, 0, 0)), (0, s * (R_PAROI + PALIER[2] + 0.5), 0))
    instance("Goupille de butée de roulis", "RW-24_Goupille-3x16", "croisillon", repere((1, 0, 0), (0, 1, 0)), (CROIX / 2 - 6, 0, R_GOUPILLE))
    instance("Goupille de butée de tangage", "RW-24_Goupille-3x16", "croisillon", repere((0, 1, 0), (1, 0, 0)), (0, R_PAROI + 2.5, R_GOUPILLE))

    # ------------------------------------------------------------ paliers (repère du pivot, axes du dispositif)
    for k, s in enumerate((1, -1), 1):
        Rp = repere((0, s, 0), (-s, 0, 0))
        o = np.array([0, s * R_PAROI, 0.0])
        instance(f"Palier {k}", "RW-04_Palier", "paliers", Rp, o)
        instance(f"Roulement de tangage {k}", "RW-20_Roulement-625", "paliers", Rp, o + Rp @ np.array([0, 0, PALIER[2] - ROULEMENT[1]]))

    # ------------------------------------------------------------ dispositif (repère du dispositif)
    instance("Corps central", "RW-01_Moyeu", "dispositif")
    instance("Plateau", "RW-08_Plateau", "dispositif")
    instance("Bornier", "RW-11_Bornier", "dispositif")
    instance("BNO055", "RW-32_BNO055", "dispositif", repere(Z, (0, -1, 0)), (0, 0, zt - 1.0))
    for k, xb in enumerate(X_BARRETTES, 1):
        instance(f"Barrette {k}", "RW-36_Barrette-1x15", "dispositif", repere(Z, (0, 1, 0)), (xb, 0, zt + BORNIER_H - 2.6))
    for k, a in enumerate(ESC_FACE, 1):
        r = math.radians(a)
        d, t = np.array([math.cos(r), math.sin(r), 0.0]), np.array([-math.sin(r), math.cos(r), 0.0])
        instance(f"ESC {k}", "RW-31_ESC-30A", "dispositif", repere(d, t), (ESC_A - ESC[2] / 2) * d + (zt + ESC[1] / 2) * Z)
    for k, (x, y) in enumerate(POS_ENTRETOISES, 1):
        instance(f"Entretoise de la carte {k}", "RW-26_Entretoise-M3x35", "dispositif", t=(x, y, zt))
    instance("Carte de distribution XT60", "RW-37_Carte-XT60-1x4", "dispositif", t=(0, 0, zc))
    for k in range(4):
        instance(f"Fiche XT60 de l'ESC {k + 1}", "RW-38_Fiche-XT60", "dispositif", t=(PDB_SORTIES[PDB_SORTIE_ESC[k]], 0, zc + PDB[2] + XT60_DOUILLE_H))
    instance("Fiche XT60 de l'alimentation", "RW-39_Fiche-XT60-alim", "dispositif", repere((1, 0, 0), (0, 0, 1)),
             (PDB_ENTREE[1], 0, zc + PDB[2] + PDB_ENTREE[2] / 2))

    # ------------------------------------------------------------ équilibrage : 4 tiges filetées, écrous de serrage et de réglage
    he = EQ_ECROU[1]
    for k, a in enumerate(EQ_FACES, 1):
        L = Location(P.plan_tige_equilibrage(a))
        R, t = de_location(L)
        instance(f"Tige d'équilibrage {k}", "RW-40_Tige-filetee-M6x60", "dispositif", R, t)
        for nom, z in (("intérieur", -E_PAROI - he / 2), ("extérieur", he / 2)):
            Re, te = de_location(L * Pos(0, 0, z))
            instance(f"Écrou de serrage {nom} {k}", "RW-41_Ecrou-M6", "dispositif", Re, te)
        n = ECROUS[k - 1]
        for j in range(n):                                 # paquet d'écrous de réglage, centré à POSITIONS[k] du centre du corps
            Re, te = de_location(L * Pos(0, 0, POSITIONS[k - 1] - R_PAROI + (j - (n - 1) / 2) * he))
            instance(f"Écrou de réglage {k}.{j + 1}", "RW-41_Ecrou-M6", "reglage", Re, te)

    # ------------------------------------------------------------ modules de roue et roues
    for k, a in enumerate(ANGLES_ROUES, 1):
        R, t = de_location(Location(P.plan_roue(a)))
        for cle, nom in (("RW-02_Platine-moteur", "Platine"), ("RW-03_Carter", "Carter"), ("RW-12_Potence-capteur", "Potence")):
            instance(f"{nom} {k}", cle, f"module{k}", R, t)
        Rc, tc = de_location(Location(P.plan_roue(a)) * Pos(0, TCRT_V, W_CARTE) * Rot(180, 0, 0))
        instance(f"Carte TCRT5000 {k}", "RW-33_TCRT5000", f"module{k}", Rc, tc)
        Rs, ts = de_location(Location(P.plan_roue(a, R_APPUI + 2.0)))
        instance(f"A2212 stator {k}", "A2212_stator", f"module{k}", Rs, ts)
        for i in roue_ref:                                 # repère de la roue : mêmes poses, reculées le long de l'axe
            t0 = np.array(i["t_mm"]) + np.array([0, 0, recul])
            instance(f"{i['nom']} (roue {k})", i["solide"], f"roue{k}", i["R"], t0)

    # ------------------------------------------------------------ grandeurs de contrôle
    def ensemble(groupes, origine_mm, zp=ZP):
        """Masse, centre de masse (m) et tenseur d'inertie au point origine (repère du dispositif) des groupes cités,
        le pivot étant à la hauteur zp sur le corps."""
        M, MG, pieces = 0.0, np.zeros(3), []
        for i in INSTANCES:
            g = i["groupe"]
            if not g.startswith(tuple(groupes)):
                continue
            s = SOLIDES[i["solide"]]
            R, t = np.array(i["R"]), np.array(i["t_mm"]) / 1000.0
            if g.startswith("roue"):                       # repère de la roue vers le repère du dispositif
                a = math.radians(ANGLES_ROUES[int(g[-1]) - 1])
                Rk = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]]) @ np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
                R, t = Rk @ R, Rk @ t
            if g in ("paliers", "croisillon"):             # repère du pivot vers le repère du dispositif
                t = t + np.array([0, 0, zp / 1000.0])
            p = R @ np.array(s["G"]) + t
            pieces.append((s["m"], p, R @ np.array(s["I"]) @ R.T))
            M += s["m"]
            MG += s["m"] * p
        G = MG / M
        o = np.asarray(origine_mm, float) / 1000.0
        I = sum(Ic + m * (np.dot(p - o, p - o) * np.eye(3) - np.outer(p - o, p - o)) for m, p, Ic in pieces)
        return M, G, I

    DISPOSITIF = ("dispositif", "module", "roue", "paliers", "reglage")
    if "--equilibrer" in sys.argv:
        equilibrer(ensemble, DISPOSITIF)
        return
    Md, Gd, Id = ensemble(DISPOSITIF, (0, 0, ZP))
    Mc, Gc, Ic = ensemble(("croisillon",), (0, 0, ZP))
    Mr, Gr, Ir = ensemble(("roue1",), (0, 0, 0))
    a = math.radians(ANGLES_ROUES[0])
    axe = np.array([math.cos(a), math.sin(a), 0.0])
    J = float(axe @ Ir @ axe)
    controle = {"z_pivot_mm": ZP, "m_disp": Md, "G_disp": Gd.tolist(), "I_disp_pivot": Id.tolist(), "m_croix": Mc,
                "G_croix": Gc.tolist(), "Ixx_croix_pivot": float(Ic[0, 0]), "m_roue": Mr, "J_roue": J}
    bno = next(i for i in INSTANCES if i["solide"] == "RW-32_BNO055")
    p_bno = np.array(bno["R"]) @ (np.array(SOLIDES["RW-32_BNO055"]["G"]) * 1000) + np.array(bno["t_mm"])
    for i in INSTANCES:                                    # les écrous de réglage font partie du dispositif
        if i["groupe"] == "reglage":
            i["groupe"] = "dispositif"
    Me, Ge, _ = ensemble(DISPOSITIF[:-1], (0, 0, Z_PIVOT_EQUILIBRE), zp=Z_PIVOT_EQUILIBRE)
    controle["z_pivot_equilibre_mm"] = Z_PIVOT_EQUILIBRE
    controle["G_disp_equilibre"] = Ge.tolist()
    json.dump({"version": "banc v3", "solides": SOLIDES, "instances": INSTANCES,
               "angles_roues": {str(k): a for k, a in enumerate(ANGLES_ROUES, 1)}, "z_pivot_cao": ZP, "z_pivots": list(Z_PIVOTS) + [Z_PIVOT_EQUILIBRE],
               "z_socle": Z_SOCLE, "butee_deg": BUTEE, "bno_mm": p_bno.tolist(), "controle": controle,
               "rayons_disque": 4, "longueurs_cables_mm": {n: l for n, (_, _, l, _) in S.items()}},
              open(os.path.join(ICI, "cao_jumeau.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(SOLIDES)} pièces, {len(INSTANCES)} instances")
    print(f"dispositif (roues et paliers compris) : {Md * 1000:.1f} g, G = {np.round(Gd * 1000, 2)} mm")
    print(f"croisillon (tige, colliers, vis, goupilles) : {Mc * 1000:.1f} g")
    print(f"partie mobile : {(Md + Mc) * 1000:.1f} g ; roue : {Mr * 1000:.1f} g, J = {J:.4g} kg·m² autour de son axe")
    h = Gd[2] * 1000 - ZP
    print(f"pivot {ZP:+.0f} mm : h = {h:.2f} mm ; I au pivot (roulis, tangage, lacet) = {np.round(np.diag(Id), 6)} kg·m²")
    print(f"BNO055 : {np.round(p_bno, 1)} mm")
    reste = np.array([Ge[0], (Me * Ge[1] + Mc * Gc[1]) / (Me + Mc), Ge[2] - Z_PIVOT_EQUILIBRE / 1000.0]) * 1000
    print(f"pivot d'équilibre {Z_PIVOT_EQUILIBRE:+.2f} mm : centre de masse à {reste[0]:+.3f} mm (tangage, selon x), "
          f"{reste[1]:+.3f} mm (roulis, selon y, croisillon compris), {reste[2]:+.3f} mm en hauteur")


def equilibrer(ensemble, groupes):
    """Cherche le nombre et la position des écrous de réglage qui amènent le centre de masse sur le pivot, puis la
    hauteur du pivot. Tangage : le dispositif seul doit avoir son centre de masse sur l'axe (x = 0). Roulis : le dispositif
    et le croisillon ensemble (y = 0). Affiche les valeurs à reporter dans rw_params.py."""
    m, he = MASSES["ecrou_m6"] / 1000.0, EQ_ECROU[1]
    base = [g for g in groupes if g != "reglage"]
    M0, G0, _ = ensemble(base, (0, 0, ZP))
    Mc, Gc, _ = ensemble(("croisillon",), (0, 0, ZP))
    cx, cy = -M0 * G0[0], -(M0 * G0[1] + Mc * Gc[1])        # moments à apporter (kg·m)
    dec = EQ_DECALAGE / 1000.0
    dehors = EQ_TIGE[1] - E_PAROI - EQ_INTERIEUR             # longueur de tige hors du corps

    def bornes(n):
        return (R_PAROI + he + 1.0 + n * he / 2) / 1000.0, (R_PAROI + dehors - n * he / 2) / 1000.0

    meilleur = None
    for total in range(0, 17):
        for n in np.ndindex(5, 5, 5, 5):
            if sum(n) != total:
                continue
            # x : m (n1 p1 - n3 p3) + m dec (n4 - n2) = cx ;  y : m (n2 p2 - n4 p4) + m dec (n1 - n3) = cy
            sol = []
            for (na, nb, cible) in ((n[0], n[2], cx / m - dec * (n[3] - n[1])), (n[1], n[3], cy / m - dec * (n[0] - n[2]))):
                (a0, a1), (b0, b1) = bornes(na), bornes(nb)
                trouve = None
                for pb in np.linspace(b0, b1, 41) if nb else [0.0]:
                    if na:
                        pa = (cible + nb * pb) / na
                        if a0 <= pa <= a1:
                            trouve = (pa, pb if nb else (b0 + b1) / 2)
                            break
                    elif abs(cible + nb * pb) < 1e-4 / 41:   # aucun écrou de ce côté : il faut tomber juste
                        trouve = ((a0 + a1) / 2, pb)
                        break
                if trouve is None:
                    break
                sol.append(trouve)
            if len(sol) == 2:
                meilleur = (n, (sol[0][0], sol[1][0], sol[0][1], sol[1][1]))
                break
        if meilleur:
            break
    assert meilleur, "pas de réglage possible avec 4 écrous au plus par tige"
    n, p = meilleur
    Mn = M0 + m * sum(n)
    zn = (M0 * G0[2] + m * sum(n) * EQ_Z / 1000.0) / Mn      # avec les paliers à la rangée ZP
    Mp, Gp, _ = ensemble(("paliers",), (0, 0, ZP))
    zp = (Mn * zn - Mp * Gp[2] + Mp * (Gp[2] - ZP / 1000.0)) / (Mn - Mp) * 1000   # les paliers montent avec le pivot
    print(f"sans écrou de réglage : {M0 * 1000:.1f} g, centre de masse x {G0[0] * 1000:+.3f}, y {G0[1] * 1000:+.3f}, z {G0[2] * 1000:.3f} mm")
    print(f"EQ_ECROUS = {tuple(int(v) for v in n)}")
    print(f"EQ_POSITIONS = {tuple(round(float(v) * 1000, 1) for v in p)}")
    print(f"Z_PIVOT_EQUILIBRE = {zp:.2f}     (rangée {ZP:+.0f} mm, paliers décalés de {zp - ZP:+.2f} mm)")


if __name__ == "__main__":
    main()
