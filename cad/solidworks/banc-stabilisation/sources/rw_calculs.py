"""Calculs de dimensionnement du banc de stabilisation, repris dans la documentation technique (rw_documents.py).
Toutes les hypothèses sont écrites ici ; les masses et positions viennent du modèle (rw_verif.dispositif).

Usage : python rw_calculs.py   (Python avec build123d) : imprime le bilan
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rw_pieces as P
import rw_verif as V
from rw_params import *  # noqa: F401,F403

G = 9.81
# ---------------------------------------------------------------- hypothèses (sources dans la documentation)
KV = 1400.0                    # A2212 de la fiche E-S Motor du dossier crystof (modèle moteur_A2212.slx)
V_BAT = 11.1                   # LiPo 3S nominale
I_MAX_MOTEUR = 19.0            # A2212 1400 KV, courant maxi annoncé (decisions-techniques.md)
I_CONTINU = 10.0
J_ROUE = 1.62e-4               # disque + vis + rotor, estimation du TP1 (kg·m²)
M_VIS = 0.008                  # vis M6 et écrou d'équilibrage (kg)
R_VIS = 0.055                  # rayon des trous Ø7 du disque (m)
LIGAMENT = 1.5e-3              # matière entre le trou Ø7 et le bord du disque (60 − 55 − 3,5 mm)
E_DISQUE = 4.5e-3
TAU_PLA = 20.0                 # résistance au cisaillement du PLA imprimé, prudente (MPa)
ROULEMENT_C, ROULEMENT_C0 = 1.7e3, 0.67e3   # 625 : charges dynamique et statique de base usuelles (N)
MU_ROULEMENT = 0.0015          # coefficient de frottement équivalent d'un roulement à billes (formule simplifiée SKF)
E_ACIER, RE_ACIER = 210e3, 400.0           # MPa
RE_ALU = 150.0                 # tube 6060
CAPACITE = 2.2                 # Ah (phase batterie)
I_VIDE = 0.8                   # courant à vide d'un A2212 en rotation, ordre de grandeur (A)
RHO_PLA = 1.24                 # g/cm3, PLA plein
DEBIT_IMPRESSION = 20.0        # g/h, ordre de grandeur Bambu Lab A1, profil standard 0,2 mm


def elements():
    d = V.dispositif(V.moteur_equivalent())
    lc, lm = V.cardan(Z_PIVOT_EQUILIBRE)
    return {**d, **lm, **lc}


def masse_centre():
    el = elements()
    M = sum(V.masse(*v) for v in el.values())
    Gc = sum(V.masse(*v) * np.array(tuple(v[0].center())) for v in el.values()) / M
    return M / 1000.0, Gc


def inertie_roulis(zp):
    """Moment d'inertie du dispositif autour de l'axe de roulis (X) passant par le pivot : masses ponctuelles,
    plus l'inertie propre des disques (axe à 45° de leur axe : 0,375 m R²)."""
    I = 0.0
    for nom, v in elements().items():
        m = V.masse(*v) / 1000.0
        c = np.array(tuple(v[0].center())) / 1000.0
        I += m * (c[1] ** 2 + (c[2] - zp / 1000.0) ** 2)
        if nom.startswith("disque"):
            I += 0.375 * m * (DISQUE[2] / 1000.0) ** 2
    return I


def vitesse(offset_us):
    """Vitesse à vide du disque (tr/min) pour un écart d'impulsion autour du neutre de 1500 µs."""
    return KV * V_BAT * offset_us / 500.0


def vis_centrifuge(tr_min):
    w = tr_min * 2 * math.pi / 60
    F = M_VIS * R_VIS * w ** 2
    tau = F / (2 * LIGAMENT * E_DISQUE) / 1e6
    v = R_VIS * w
    return F, tau, v, 0.5 * M_VIS * v ** 2


def bilan():
    M, Gc = masse_centre()
    poids = M * G
    out = {"masse": M, "zG": Gc[2], "G": [float(x) for x in Gc], "poids": poids}
    out["equilibre"] = {"zp": Z_PIVOT_EQUILIBRE, "h": Gc[2] - Z_PIVOT_EQUILIBRE}
    kt = 60 / (2 * math.pi * KV)
    out["kt"] = kt
    out["couple_continu"] = kt * I_CONTINU
    out["couple_max"] = kt * I_MAX_MOTEUR
    out["couple_axe_continu"] = 4 * kt * I_CONTINU * C45
    out["couple_axe_max"] = 4 * kt * I_MAX_MOTEUR * C45
    out["pivots"] = []
    for zp in Z_PIVOTS:
        h = (Gc[2] - zp) / 1000.0
        I = inertie_roulis(zp)
        # h > 2 mm : instable (pendule inversé), constante de temps de la chute ; sinon presque neutre ou stable
        out["pivots"].append({"zp": zp, "h": h * 1000, "I": I, "c5": poids * h * math.sin(math.radians(5)),
                              "c10": poids * h * math.sin(math.radians(10)),
                              "tau": math.sqrt(I / (poids * h)) if h > 0.002 else None,
                              "alpha": out["couple_axe_continu"] / I, "d_imu": Z_PLATEAU + E_PLATEAU - 1.0 - zp})
    # roulements et axes
    out["charge_roulement"] = poids / 2
    out["s0"] = ROULEMENT_C0 / out["charge_roulement"]
    out["frottement_roulement"] = 0.5 * MU_ROULEMENT * out["charge_roulement"] * 5.0      # N·mm
    out["frottement_lisse"] = 0.5 * 0.3 * out["charge_roulement"] * 5.0                  # PLA sur acier, μ ≈ 0,3
    porte = R_PAROI + PALIER[2] - ROULEMENT[1] / 2 - CROIX / 2                             # du croisillon au roulement
    Mf = out["charge_roulement"] * porte
    W = math.pi * D_TIGE ** 3 / 32
    I5 = math.pi * D_TIGE ** 4 / 64
    out["tige"] = {"porte": porte, "M": Mf, "sigma": Mf / W, "fleche": out["charge_roulement"] * porte ** 3 / (3 * E_ACIER * I5),
                   "securite": RE_ACIER / (Mf / W)}
    bras = CROIX / 2 + FOURCHE_JEU + FOURCHE_BRAS - ROULEMENT[1] / 2 - CROIX / 2
    out["vis_epaulee"] = {"bras": bras, "sigma": out["charge_roulement"] * bras / W}
    h_max = (Gc[2] - (min(Z_PIVOTS) - PALIER_REGLAGE)) / 1000.0     # pivot au plus bas : rangée −8, bas des lumières
    excentr = h_max * math.sin(math.radians(BUTEE)) * 1000
    Wt = math.pi * (TUBE[0] ** 4 - (TUBE[0] - 2 * TUBE[1]) ** 4) / (32 * TUBE[0])
    out["tube"] = {"excentricite": excentr, "M": poids * excentr, "sigma": poids * excentr / Wt,
                   "securite": RE_ALU / (poids * excentr / Wt)}
    out["energie_chute"] = poids * h_max * (1 - math.cos(math.radians(BUTEE)))
    # roues
    out["vitesses"] = []
    for off in (100, 125, 200, 300, 500):
        n = vitesse(off)
        F, tau, v, E = vis_centrifuge(n)
        out["vitesses"].append({"offset": off, "n": n, "F": F, "tau": tau, "v": v, "E": E, "securite": TAU_PLA / tau})
    n_lim = vitesse(125)
    out["H_roue"] = J_ROUE * n_lim * 2 * math.pi / 60
    out["H_axe"] = 4 * out["H_roue"] * C45
    out["autonomie"] = [(i, 0.8 * CAPACITE / i * 60) for i in (2.0, 5.0, 10.0)]          # phase batterie
    # alimentation de labo : courant d'un moteur pour tenir la gravité à 5° (position la plus dure), avec le courant à vide
    c_moteur = max(p["c5"] for p in out["pivots"]) / (4 * C45)
    out["courant_tenue"] = c_moteur / kt + I_VIDE
    out["courant_pointe"] = 4 * I_MAX_MOTEUR
    out["energie_roue"] = 0.5 * J_ROUE * (n_lim * 2 * math.pi / 60) ** 2
    out["excentricite_admise"] = 0.2 * max(p["c5"] for p in out["pivots"]) / poids * 1000   # 20 % du couple à 5° (mm)
    # impression
    out["impression"] = []
    nb = {"RW-01_Moyeu": 1, "RW-02_Platine-moteur": 4, "RW-03_Carter": 4, "RW-04_Palier": 2, "RW-05_Collier": 2,
          "RW-06_Croisillon": 1, "RW-07_Fourche": 1, "RW-08_Plateau": 1, "RW-09_Berceau": 0, "RW-10_Socle": 1,
          "RW-11_Bornier": 1, "RW-12_Porte-capteur": 4}    # berceau : phase batterie, pas imprimé maintenant
    plein = {"RW-05_Collier", "RW-06_Croisillon"}
    for nom, f in P.PIECES.items():
        if not nb[nom]:
            continue
        vol = f().volume / 1000.0
        rho = RHO_PLA if nom in plein else RHO_IMPRIME
        m = vol * rho
        out["impression"].append({"nom": nom, "nb": nb[nom], "volume": vol, "masse": m, "masse_tot": m * nb[nom],
                                  "heures": m * nb[nom] / DEBIT_IMPRESSION})
    vol_e = math.pi * (4.0 ** 2 - 2.55 ** 2) * 4 / 1000.0
    out["impression"].append({"nom": "RW-23_Entretoise-roulis", "nb": 2, "volume": vol_e, "masse": vol_e * RHO_PLA,
                              "masse_tot": 2 * vol_e * RHO_PLA, "heures": 0.1})
    out["pla_total"] = sum(p["masse_tot"] for p in out["impression"]) * 1.1      # 10 % de purge et de pertes
    out["heures_total"] = sum(p["heures"] for p in out["impression"])
    return out


if __name__ == "__main__":
    import json
    b = bilan()
    print(json.dumps(b, indent=1, default=float, ensure_ascii=False))
