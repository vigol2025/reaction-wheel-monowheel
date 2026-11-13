"""Construit le jumeau Webots du banc de stabilisation (version 3) à partir des mêmes données CAO que le jumeau Simscape.

Entrée : cao_jumeau.json (preparer_cao.py) et ../geometrie/*.stl.
Sorties : ../webots/worlds/banc_stabilisation.wbt (le monde) et ../webots/controllers/pont_simulink/banc.json
(masse, centre de masse et inertie du dispositif pour chaque position du pivot, lus par le contrôleur).

Mêmes corps et mêmes liaisons que le jumeau Simscape : bâti fixe, croisillon (roulis, axe X), dispositif (tangage, axe Y),
4 roues (axe du moteur, sur les diagonales). Les modèles d'ESC, de moteur et de capteurs sont dans le contrôleur
pont_simulink, qui reçoit tous ses réglages de MATLAB.

Usage : python construire_webots.py
"""
import json
import math
import os
import struct

import numpy as np

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
GEO = os.path.join(RACINE, "geometrie")
MONDE = os.path.join(RACINE, "webots", "worlds", "banc_stabilisation.wbt")
DONNEES = os.path.join(RACINE, "webots", "controllers", "pont_simulink", "banc.json")
PAS_MS = 1                                                 # pas de calcul de Webots


def f(x):
    """Nombre au format du fichier monde."""
    x = float(x)
    return "0" if abs(x) < 1e-12 else f"{x:.9g}"


def vec(v):
    return " ".join(f(x) for x in v)


def axe_angle(R):
    """Matrice de rotation vers (axe, angle) de Webots."""
    R = np.asarray(R, float)
    c = max(-1.0, min(1.0, (np.trace(R) - 1) / 2))
    a = math.acos(c)
    if a < 1e-9:
        return (0.0, 0.0, 1.0, 0.0)
    if math.pi - a < 1e-6:
        d = np.sqrt(np.maximum((np.diag(R) + 1) / 2, 0))
        k = int(np.argmax(d))
        e = d.copy()
        for j in range(3):
            if j != k and R[k, j] + R[j, k] < 0:
                e[j] = -e[j]
        e = e / np.linalg.norm(e)
        return (e[0], e[1], e[2], math.pi)
    e = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * math.sin(a))
    return (e[0], e[1], e[2], a)


def sommets_stl(chemin):
    """Sommets d'un STL binaire (mm)."""
    d = open(chemin, "rb").read()
    n = struct.unpack_from("<I", d, 80)[0]
    assert len(d) == 84 + 50 * n, f"{chemin} : STL binaire attendu"
    t = np.frombuffer(d, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
    return t["v"].reshape(-1, 3).astype(float)


def Rk(angle_deg):
    """Repère d'une roue dans le dispositif : Z = axe du moteur, du centre vers l'extérieur, sur la diagonale."""
    a = math.radians(angle_deg)
    return np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]]) @ np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])


class Monde:
    def __init__(self, cao):
        self.cao = cao
        self.lignes = []
        self.maillages = set()

    def e(self, niveau, texte):
        self.lignes.append("  " * niveau + texte)

    def forme(self, niveau, inst, decalage=(0, 0, 0)):
        """Une pièce de la CAO : son maillage STL (mm), posé dans le repère de son corps."""
        s = self.cao["solides"][inst["solide"]]
        t = (np.array(inst["t_mm"], float) + np.array(decalage, float)) / 1000.0
        c = s["couleur"].lstrip("#")
        rgb = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        nom = "M_" + "".join(ch if ch.isalnum() else "_" for ch in inst["solide"])
        if nom in self.maillages:
            geo = f"USE {nom}"
        else:
            self.maillages.add(nom)
            geo = f'DEF {nom} Mesh {{ url [ "../../geometrie/{s["stl"]}" ] }}'
        metal = 0.6 if rgb[0] == rgb[1] == rgb[2] else 0.0
        self.e(niveau, f"Transform {{ translation {vec(t)} rotation {vec(axe_angle(inst['R']))} scale 0.001 0.001 0.001 children [ Shape {{ "
                       f"appearance PBRAppearance {{ baseColor {vec(rgb)} roughness 0.6 metalness {f(metal)} }} geometry {geo} }} ] }}  # {inst['nom']}")

    def formes(self, niveau, groupes, decalage=(0, 0, 0)):
        for i in self.cao["instances"]:
            if i["groupe"] in groupes:
                self.forme(niveau, i, decalage)

    def physique(self, niveau, m, G, I, nom=None):
        """Masse (kg), centre de masse (m) et tenseur d'inertie au centre de masse (kg.m²), dans le repère du corps."""
        d = f"DEF {nom} " if nom else ""
        self.e(niveau, f"physics {d}Physics {{ density -1 mass {f(m)} centerOfMass [ {vec(G)} ] "
                       f"inertiaMatrix [ {f(I[0, 0])} {f(I[1, 1])} {f(I[2, 2])}, {f(I[0, 1])} {f(I[0, 2])} {f(I[1, 2])} ] }}")


def inertie(cao, groupes, decalage_mm=None):
    """Masse, centre de masse et tenseur d'inertie au centre de masse des pièces des groupes cités, dans leur repère
    commun. decalage_mm : translation ajoutée à certains groupes (les paliers suivent le pivot)."""
    decalage_mm = decalage_mm or {}
    M, MG, pieces = 0.0, np.zeros(3), []
    for i in cao["instances"]:
        if i["groupe"] not in groupes:
            continue
        s = cao["solides"][i["solide"]]
        R = np.array(i["R"], float)
        t = (np.array(i["t_mm"], float) + np.array(decalage_mm.get(i["groupe"], (0, 0, 0)), float)) / 1000.0
        p = R @ np.array(s["G"], float) + t
        pieces.append((s["m"], p, R @ np.array(s["I"], float) @ R.T))
        M += s["m"]
        MG += s["m"] * p
    G = MG / M
    I = sum(Ic + m * (np.dot(p - G, p - G) * np.eye(3) - np.outer(p - G, p - G)) for m, p, Ic in pieces)
    return M, G, I


def main():
    cao = json.load(open(os.path.join(ICI, "cao_jumeau.json"), encoding="utf-8"))
    zp = cao["z_pivot_cao"]                                # pivot de la CAO : hauteur du centre de rotation dans le repère fixe
    angles = [cao["angles_roues"][str(k)] for k in (1, 2, 3, 4)]
    MODULES = ("module1", "module2", "module3", "module4")
    CORPS = ("dispositif",) + MODULES + ("paliers",)

    # hauteur de la table : le dessous du bâti
    z_bas = 1e9
    for i in cao["instances"]:
        if i["groupe"] == "bati":
            v = sommets_stl(os.path.join(GEO, cao["solides"][i["solide"]]["stl"]))
            z_bas = min(z_bas, float((v @ np.array(i["R"], float).T + np.array(i["t_mm"], float))[:, 2].min()))
    z0 = -z_bas / 1000.0                                   # le repère fixe du banc est à cette hauteur au-dessus de la table

    # masse et inertie du dispositif pour chaque position du pivot (les paliers se vissent à la hauteur du pivot)
    pivots = {}
    for p in cao["z_pivots"]:
        m, G, I = inertie(cao, CORPS, {"paliers": (0, 0, p)})
        pivots[f"{p:g}"] = {"m": m, "G": G.tolist(), "I": [[I[0, 0], I[1, 1], I[2, 2]], [I[0, 1], I[0, 2], I[1, 2]]]}

    w = Monde(cao)
    e = w.e
    e(0, "#VRML_SIM R2025a utf8")
    e(0, "# Jumeau Webots du banc de stabilisation à 4 roues de réaction (version 3).")
    e(0, "# Fichier généré par construction/construire_webots.py à partir de la CAO : ne pas le modifier à la main.")
    e(0, "")
    e(0, "DEF MONDE WorldInfo {")
    e(1, 'title "Banc de stabilisation à 4 roues de réaction (version 3)"')
    e(1, 'info [ "Jumeau numérique piloté par Simulink (jumeau_banc_rw.slx, procédé : Jumeau Webots)." '
         '"Entrée : 4 impulsions d\'ESC ; sorties : BNO055 et 4 vitesses de roue. Tous les réglages viennent de MATLAB." ]')
    e(1, f"basicTimeStep {PAS_MS}")
    e(1, "FPS 30")
    e(1, "gravity 9.81")
    e(0, "}")
    # vue : trois quarts avant, au-dessus
    pos = np.array([0.66, -0.56, z0 + 0.30])
    cible = np.array([0.0, 0.0, z0 - 0.02])
    av = (cible - pos) / np.linalg.norm(cible - pos)
    ga = np.cross([0, 0, 1], av)
    ga /= np.linalg.norm(ga)
    ha = np.cross(av, ga)
    e(0, f"Viewpoint {{ orientation {vec(axe_angle(np.column_stack([av, ga, ha])))} position {vec(pos)} near 0.01 }}")
    e(0, "Background { skyColor [ 0.93 0.95 0.98 ] luminosity 1.3 }")
    e(0, "DirectionalLight { direction -0.5 0.4 -1 intensity 2.2 ambientIntensity 1 }")
    e(0, "DirectionalLight { direction 0.6 -0.5 -0.5 intensity 1.2 }")
    e(0, 'Solid { translation 0 0 -0.01 name "table" children [ Shape { appearance PBRAppearance { baseColor 0.78 0.71 0.58 roughness 0.9 metalness 0 } '
         "geometry Box { size 0.7 0.7 0.02 } } ] }")
    e(0, "DEF BANC Robot {")
    e(1, f"translation 0 0 {f(z0)}")
    e(1, 'name "banc_stabilisation"')
    e(1, 'controller "pont_simulink"')
    e(1, "supervisor TRUE")
    e(1, "children [")
    e(2, "# ---------------- bâti fixe : socle, poteau, fourche")
    w.formes(2, ("bati",))
    e(2, "# ---------------- roulis : pivot du croisillon dans la fourche, axe X")
    e(2, "DEF ROULIS HingeJoint {")
    e(3, f"jointParameters HingeJointParameters {{ axis 1 0 0 anchor 0 0 {f(zp / 1000)} }}")
    e(3, 'device [ RotationalMotor { name "moteur_roulis" maxTorque 1000 maxVelocity 1000 } PositionSensor { name "angle_roulis" } ]')
    e(3, "endPoint DEF CROISILLON Solid {")
    e(4, f"translation 0 0 {f(zp / 1000)}")
    e(4, 'name "croisillon"')
    m, G, I = inertie(cao, ("croisillon",))
    w.physique(4, m, G, I)
    e(4, "children [")
    w.formes(5, ("croisillon",))
    e(5, "# ---------------- tangage : pivot du dispositif sur le croisillon, axe Y")
    e(5, "DEF TANGAGE HingeJoint {")
    e(6, "jointParameters HingeJointParameters { axis 0 1 0 anchor 0 0 0 }")
    e(6, 'device [ RotationalMotor { name "moteur_tangage" maxTorque 1000 maxVelocity 1000 } PositionSensor { name "angle_tangage" } ]')
    e(6, "endPoint DEF DISPOSITIF Solid {")
    e(7, f"translation 0 0 {f(-zp / 1000)}  # origine du dispositif : centre du corps, à la hauteur des axes des moteurs")
    e(7, 'name "dispositif"')
    p0 = pivots[f"{zp:g}"]
    Ip = np.array([[p0["I"][0][0], p0["I"][1][0], p0["I"][1][1]], [p0["I"][1][0], p0["I"][0][1], p0["I"][1][2]], [p0["I"][1][1], p0["I"][1][2], p0["I"][0][2]]])
    w.physique(7, p0["m"], p0["G"], Ip, "PHYSIQUE_DISPOSITIF")
    e(7, "children [")
    e(8, f"DEF PALIERS Pose {{ translation 0 0 {f(zp / 1000)} children [")
    w.formes(9, ("paliers",))
    e(8, "] }")
    w.formes(8, ("dispositif",) + MODULES)
    b = np.array(cao["bno_mm"]) / 1000.0
    e(8, "# ---------------- BNO055 : orientation, gyroscope, accéléromètre à l'emplacement de la carte")
    e(8, f'InertialUnit {{ translation {vec(b)} name "bno055_orientation" }}')
    e(8, f'Gyro {{ translation {vec(b)} name "bno055_gyroscope" }}')
    e(8, f'Accelerometer {{ translation {vec(b)} name "bno055_accelerometre" }}')
    for k, a in enumerate(angles, 1):
        ax = (math.cos(math.radians(a)), math.sin(math.radians(a)), 0)
        e(8, f"# ---------------- roue {k} : axe du moteur sur la diagonale à {a:g}°")
        e(8, f"DEF ROUE{k} HingeJoint {{")
        e(9, f"jointParameters HingeJointParameters {{ axis {vec(ax)} anchor 0 0 0 }}")
        e(9, f'device [ RotationalMotor {{ name "moteur_roue_{k}" maxTorque 100 maxVelocity 100000 }} PositionSensor {{ name "angle_roue_{k}" }} ]')
        e(9, "endPoint Solid {")
        e(10, f"rotation {vec(axe_angle(Rk(a)))}")
        e(10, f'name "roue {k}"')
        m, G, I = inertie(cao, (f"roue{k}",))
        w.physique(10, m, G, I)
        e(10, "children [")
        w.formes(11, (f"roue{k}",))
        e(10, "]")
        e(9, "}")
        e(8, "}")
    e(7, "]")
    e(6, "}")
    e(5, "}")
    e(4, "]")
    e(3, "}")
    e(2, "}")
    e(1, "]")
    e(0, "}")
    os.makedirs(os.path.dirname(MONDE), exist_ok=True)
    os.makedirs(os.path.dirname(DONNEES), exist_ok=True)
    open(MONDE, "w", encoding="utf-8", newline="\n").write("\n".join(w.lignes) + "\n")
    json.dump({"version": cao["version"], "pas_ms": PAS_MS, "pivot_monde_mm": zp, "pivots": pivots, "angles_roues_deg": angles,
               "hauteur_repere_m": z0}, open(DONNEES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = pivots[f"{zp:g}"]
    print(f"monde : {MONDE}")
    print(f"  {sum(1 for l in w.lignes if 'Shape' in l) - 1} pièces, {len(w.maillages)} maillages, repère du banc à {z0 * 1000:.1f} mm au-dessus de la table")
    print(f"  dispositif : {md['m'] * 1000:.1f} g, G = {np.round(np.array(md['G']) * 1000, 2)} mm ; pivots : {', '.join(pivots)}")


if __name__ == "__main__":
    main()
