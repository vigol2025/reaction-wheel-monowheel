"""Produit les deux documents PDF du banc de stabilisation, à la racine de Banc_stabilisation :
- Documentation-technique_banc-stabilisation.pdf : chaque composant (fonction, rôle, caractéristiques, dimensionnement,
  fabrication, approvisionnement), câblage, réglages, sécurité, contrôles ;
- Carnet-de-commandes_banc-stabilisation.pdf : impression en PLA, liste d'achats avec fournisseurs et prix indicatifs,
  budgets.
Configuration de la phase de test : le câblage existant est repris tel quel (ESC à XT60, carte de distribution
XT60 1 vers 4, alimentation de labo), l'ESP32 et le régulateur restent sur la table, sur la breadboard.
Mise en page HTML imprimée en PDF par Edge ; sommaire paginé et numéros de page ajoutés avec pypdf.

Usage : python rw_documents.py   (Python avec build123d, matplotlib et pypdf ; lancer rw_rendus.py avant)
"""
import io
import math
import os
import subprocess
import sys
import tempfile
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pypdf import PdfReader, PdfWriter

sys.stdout.reconfigure(encoding="utf-8")
ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import rw_cables as K
import rw_calculs as C
import rw_pieces as P
from rw_params import *  # noqa: F401,F403

DOSSIER = os.path.dirname(ICI)
RENDUS = os.path.join(DOSSIER, "rendus")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DATE = "13/11/2026"
VERSION = "3.1"
ESC_GPIO = (25, 26, 27, 32)
CAPTEUR_GPIO = (36, 39, 34, 35)      # entrées seules de l'ESP32 : capteurs de vitesse des roues 1 à 4
# résultats des contrôles SolidWorks (verif_liaisons.py, rw_interferences.py) du 13/11/2026
SW_LIAISONS = ("0 contrainte en erreur, une seule pièce fixe par assemblage ; 168 contraintes au strict minimum (Module_roue 11, "
               "Dispositif 125, Banc 32, dont les 2 butées) ; seul le disque est sous-contraint (libre en rotation, voulu). Réglages "
               "nommés : hauteur du pivot sur chaque palier, position de chaque paquet d'écrous d'équilibrage")
SW_INTERFERENCES = ("Rien à corriger, câbles, tiges et écrous compris. Recouvrements voulus : goupilles emmanchées Ø3 dans des trous Ø2,9 (2 × 2,8 mm³) ; la "
                    "vis vis20-2 chevauche le disque de 22 mm³ dans le sous-ensemble disque_vis d'origine (× 4).")


# ---------------------------------------------------------------- mise en forme des nombres
def f(x, n=1):
    s = f"{x:,.{n}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def euros(x):
    return f(x, 2) + " €"


def mm(zp):
    return f"{zp:+.0f} mm".replace("-", "−")


# ---------------------------------------------------------------- images des pièces (les vues d'ensemble viennent de rw_rendus.py)
def rendre_pieces():
    os.makedirs(os.path.join(RENDUS, "pieces"), exist_ok=True)
    for nom, fn in P.PIECES.items():
        sortie = os.path.join(RENDUS, "pieces", nom + ".png")
        forme = fn()
        v, fa = forme.tessellate(0.3, 0.3)
        V = np.array([[p.X, p.Y, p.Z] for p in v])
        T = np.array([V[list(t)] for t in fa])
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        lum = 0.45 + 0.55 * np.abs(n @ np.array([0.35, -0.55, 0.76]))
        rgba = np.tile(matplotlib.colors.to_rgba("#E07B39"), (len(T), 1))
        rgba[:, :3] *= lum[:, None]
        fig = plt.figure(figsize=(4.2, 3.2))
        ax = fig.add_subplot(projection="3d")
        ax.add_collection3d(Poly3DCollection(T, facecolors=rgba, edgecolors="none", linewidths=0))
        lo, hi = V.min(0), V.max(0)
        c, r = (lo + hi) / 2, (hi - lo).max() / 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
        ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=24, azim=-58); ax.set_axis_off()
        fig.subplots_adjust(0, 0, 1, 1)
        fig.savefig(sortie, dpi=110, transparent=True)
        plt.close(fig)


def url(chemin):
    return "file:///" + chemin.replace("\\", "/")


# ---------------------------------------------------------------- briques HTML
CSS = """
@page { size: A4; margin: 15mm 15mm 17mm 15mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.6pt; line-height: 1.42; color: #1d1d1b; }
h1 { font-size: 24pt; color: #1b3a5c; margin: 0 0 3mm; }
h2 { font-size: 15pt; color: #1b3a5c; border-bottom: 2px solid #1b3a5c; padding-bottom: 1mm; margin: 0 0 3mm;
     break-before: page; }
h3 { font-size: 11.5pt; color: #1b3a5c; margin: 5mm 0 2mm; break-after: avoid; }
p { margin: 0 0 2.2mm; }
table { border-collapse: collapse; width: 100%; margin: 1.5mm 0 3.5mm; font-size: 8.8pt; break-inside: auto; }
th { background: #e3ebf4; color: #1b3a5c; text-align: left; padding: 1.4mm 1.8mm; border: 0.3mm solid #b8c7d8; }
td { padding: 1mm 1.8mm; border: 0.3mm solid #cfd8e3; vertical-align: top; }
tr { break-inside: avoid; }
td.n, th.n { text-align: right; white-space: nowrap; }
.total td { font-weight: 600; background: #f3f6fa; }
.fiche { border: 0.4mm solid #b8c7d8; border-radius: 1.5mm; margin: 0 0 4mm; break-inside: avoid; }
.fiche .tete { background: #1b3a5c; color: #fff; padding: 1.6mm 2.5mm; font-weight: 600; font-size: 10.5pt; }
.fiche .tete span { font-weight: 400; opacity: 0.85; margin-left: 2mm; }
.fiche .corps { display: flex; gap: 3mm; padding: 2mm 2.5mm; }
.fiche .corps img { width: 42mm; height: 32mm; object-fit: contain; flex: none; }
.fiche table { margin: 0; font-size: 8.6pt; }
.fiche td.l { width: 31mm; color: #1b3a5c; font-weight: 600; background: #f3f6fa; }
.note { background: #fff6e5; border-left: 1.2mm solid #e0a030; padding: 2mm 3mm; margin: 2mm 0 3.5mm; break-inside: avoid; }
.alerte { background: #fdecea; border-left: 1.2mm solid #c0392b; padding: 2mm 3mm; margin: 2mm 0 3.5mm; break-inside: avoid; }
.garde { text-align: center; padding-top: 30mm; }
.garde .sous { font-size: 13pt; color: #444; margin-bottom: 6mm; }
.garde img { width: 150mm; margin: 6mm 0; }
.garde .meta { color: #555; font-size: 10pt; }
.sommaire td { border: none; border-bottom: 0.2mm dotted #aab; padding: 1.3mm 1mm; font-size: 10pt; }
figure { margin: 2mm 0 4mm; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; }
figcaption { font-size: 8.4pt; color: #555; margin-top: 1mm; }
ul { margin: 0 0 2.5mm; padding-left: 5mm; } li { margin-bottom: 0.8mm; }
.coche { font-size: 11pt; }
"""


def tableau(entetes, lignes, num=(), classe_derniere=None):
    t = ["<table><tr>" + "".join(f"<th{' class=n' if i in num else ''}>{h}</th>" for i, h in enumerate(entetes)) + "</tr>"]
    for k, l in enumerate(lignes):
        cl = f" class='{classe_derniere}'" if classe_derniere and k == len(lignes) - 1 else ""
        t.append(f"<tr{cl}>" + "".join(f"<td{' class=n' if i in num else ''}>{c}</td>" for i, c in enumerate(l)) + "</tr>")
    return "".join(t) + "</table>"


def fiche(ref, titre, champs, image=None):
    img = f"<img src='{url(image)}'>" if image and os.path.exists(image) else ""
    lignes = "".join(f"<tr><td class=l>{k}</td><td>{v}</td></tr>" for k, v in champs)
    return f"<div class=fiche><div class=tete>{ref}<span>{titre}</span></div><div class=corps>{img}<table>{lignes}</table></div></div>"


def document(titre, garde, sections):
    """sections : [(titre de section, html)] ; le sommaire reçoit des marques {{p0}}, {{p1}}… remplacées après rendu."""
    som = "".join(f"<tr><td>{t}</td><td class=n>{{{{p{k}}}}}</td></tr>" for k, (t, _) in enumerate(sections))
    corps = "".join(f"<h2>{t}</h2>{h}" for t, h in sections)
    return (f"<!doctype html><html lang=fr><head><meta charset=utf-8><title>{titre}</title><style>{CSS}</style></head><body>"
            f"{garde}<h2 style='break-before: page'>Sommaire</h2><table class=sommaire>{som}</table>{corps}</body></html>")


def imprimer(html, sortie, pied, sections):
    tmp = tempfile.mkdtemp()
    chemin_html = os.path.join(tmp, "doc.html")
    brut = os.path.join(tmp, "brut.pdf")

    def edge(h):
        open(chemin_html, "w", encoding="utf-8").write(h)
        if os.path.exists(brut):
            os.remove(brut)
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
                        "--allow-file-access-from-files", "--user-data-dir=" + os.path.join(tmp, "profil-edge"),
                        f"--print-to-pdf={brut}", url(chemin_html)], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=240)
        taille = -1
        for _ in range(120):                      # Edge peut rendre la main avant d'avoir fini d'écrire le PDF
            time.sleep(1)
            t = os.path.getsize(brut) if os.path.exists(brut) else -1
            if t > 0 and t == taille:
                break
            taille = t
        return PdfReader(brut)

    def normal(s):
        return " ".join(s.split())

    r = edge(html.replace("{{p", "<!--").replace("}}", "-->"))   # première passe : repérer les pages des sections
    textes = [normal(p.extract_text() or "") for p in r.pages]
    pages = []
    debut = 2
    for t, _ in sections:
        cle = normal(t)
        k = next((i for i in range(debut, len(textes)) if cle in textes[i]), None)
        pages.append(k + 1 if k is not None else "")
        if k is not None:
            debut = k
    h2 = html
    for k, p in enumerate(pages):
        h2 = h2.replace("{{p%d}}" % k, str(p))
    r = edge(h2)
    n = len(r.pages)
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        for i in range(n):
            fig = plt.figure(figsize=(8.27, 11.69))
            if i > 0:
                fig.text(0.5, 0.018, f"{pied}  ·  page {i + 1} / {n}", ha="center", fontsize=7, color="#777777")
            pdf.savefig(fig, transparent=True)
            plt.close(fig)
    buf.seek(0)
    sur = PdfReader(buf)
    w = PdfWriter()
    for i, p in enumerate(r.pages):
        p.merge_page(sur.pages[i])
        w.add_page(p)
    w.add_metadata({"/Title": pied, "/Author": "Projet Monowheel", "/Subject": "Banc de stabilisation à 4 roues de réaction"})
    with open(sortie, "wb") as fo:
        w.write(fo)
    print("écrit", sortie, n, "pages ; sommaire :", pages)


# ---------------------------------------------------------------- données communes
B = None


def img_piece(nom):
    return os.path.join(RENDUS, "pieces", nom + ".png")


def impression(nom):
    return next(p for p in B["impression"] if p["nom"] == nom)


def ligne_masse(nom):
    p = impression(nom)
    return f"Volume {f(p['volume'])} cm³, masse imprimée ≈ {f(p['masse'], 0)} g par pièce"



# ================================================================ DOCUMENT 1 : DOCUMENTATION TECHNIQUE
def doc_technique_debut():
    piv = B["pivots"]
    p0, p1, pn = piv[0], piv[1], piv[-1]
    tau_min = min(p["tau"] for p in piv if p["tau"])
    a_imu = [p["d_imu"] / 1000 * 10.0 for p in (p0, pn)]          # accélération parasite d·α à 10 rad/s² (m/s²)
    ri = R_PAROI - E_PAROI
    n_ins_corps = 2 * len(ANGLES_ROUES) + len(VIS_PLATEAU) + 2 * 2 * len(Z_PIVOTS)
    v125 = next(v for v in B["vitesses"] if v["offset"] == 125)
    v200 = next(v for v in B["vitesses"] if v["offset"] == 200)
    n_pc = len(P.passe_colliers())
    couple_mm = B["poids"]                      # N·mm par mm de décalage latéral du centre de gravité
    eq, G = B["equilibre"], B["G"]
    n_ecrous = sum(EQ_ECROUS) + 2 * len(EQ_FACES)
    garde = (f"<div class=garde><h1>Banc de stabilisation à 4 roues de réaction</h1>"
             f"<div class=sous>Documentation technique des composants</div>"
             f"<img src='{url(os.path.join(RENDUS, 'vue_iso.png'))}' style='width:120mm'>"
             f"<div class=meta>Projet Monowheel · {DATE} · version {VERSION}<br>Phase de test : câblage existant, "
             f"ESP32 sur breadboard, alimentation de labo<br>Modèle SolidWorks : "
             f"Banc_stabilisation.SLDASM, dans le dossier du banc</div></div>")
    S = []

    # 1. Objet
    S.append(("1. Objet et principe de fonctionnement", f"""
<div class=note><b>Version 3 ({DATE}), d'après les mesures du matériel.</b> ESC de 78 mm, 18 cm de fil entre le moteur et l'ESC, 13 cm entre
l'ESC et sa XT60, fil silicone 16 AWG 200 °C (Ø 3,0 mm). Les ESC ne tenaient pas dans le corps : ils passent sur un
<b>étage</b>, le plateau supérieur, debout en couronne autour du BNO055, tout est visible et accessible. La carte de distribution XT60 1 vers 4
est au centre, sur 4 entretoises, juste au-dessus des ESC : chaque ESC s'y branche par sa XT60. Le capteur de vitesse de chaque roue monte sur une potence, en haut du carter,
avec de la place autour, et lit directement les rayons du disque. <b>Tout le câblage est dessiné</b> dans SolidWorks, câble
par câble, au diamètre et à la longueur réels (section 7).</div>
<div class=note><b>Version 3.1 ({DATE}) : banc équilibré.</b> Le centre de gravité est amené sur l'axe de tangage par
<b>4 tiges filetées M6</b> qui sortent des faces ±X et ±Y du corps, sous l'axe des roues : des écrous vissés dessus servent
de masses réglables, leur nombre pour le réglage grossier, leur position pour le réglage fin. Les <b>paliers de tangage ont
des lumières</b> : la hauteur du pivot se règle en continu de ±{f(PALIER_REGLAGE, 0)} mm autour de chaque rangée d'inserts.
Dans le modèle, le pivot est à {mm(eq['zp'])} (rangée +24, paliers remontés de 1 mm) et les {n_ecrous} écrous sont à leur
place (section 8). Tout est monté et contraint dans SolidWorks : distances nommées, à modifier pour régler.</div>
<p>Le banc sert à mettre au point la stabilisation du monowheel avant le robot complet. Le dispositif de stabilisation (4 moteurs
A2212 avec leurs disques, leurs ESC et leurs capteurs de vitesse, la centrale inertielle BNO055 et la distribution de puissance) est monté sur un cardan
qui le laisse s'incliner librement en roulis (autour de X) et en tangage (autour de Y), de −20° à +20° sur chaque axe. La
rotation autour de la verticale (lacet) est bloquée par le cardan : la configuration à 4 roues à ±45° ne peut pas la commander.</p>
<p><b>Principe d'une roue de réaction.</b> Quand un moteur accélère son disque, le disque exerce sur le moteur, donc sur le dispositif,
un couple égal et opposé : c'est ce couple qui redresse le dispositif. Les 4 axes moteurs sont horizontaux, sur les diagonales :
chaque roue agit à cos 45° ≈ 0,707 sur le roulis et sur le tangage. Une roue ne produit un couple que tant que sa vitesse change :
quand le disque atteint sa vitesse maximale, la roue est saturée et ne peut plus corriger. D'où les capteurs de vitesse : la
commande voit approcher la saturation et peut ramener chaque roue vers une vitesse moyenne (désaturation).</p>
<p><b>Phase de test.</b> Le banc reprend le câblage existant tel quel : ESC aux fils moteur soudés et à prise XT60, carte de distribution XT60
de distribution, alimentation de labo. Le microcontrôleur n'est pas sur le dispositif : l'ESP32 reste sur la breadboard, sur la
table, en attendant la carte imprimée de la version suivante. Le dispositif ne porte que ce qui doit bouger avec lui ; il est relié
à la table par deux câbles souples.</p>
<p><b>Progression des essais.</b> On bloque d'abord un axe (goupille de blocage) pour le test à un axe, puis on libère les deux.
Le centre de rotation se règle sur 5 rangées d'inserts, plus ±{f(PALIER_REGLAGE, 0)} mm dans les lumières des paliers : au
pivot équilibré, le dispositif reste où on le pose ; plus le pivot descend sous le centre de gravité, plus le dispositif
« tombe » vite et plus la commande doit être bonne.</p>
<figure><img src='{url(os.path.join(RENDUS, 'vue_inclinee.png'))}' style='width:95mm'>
<figcaption>Dispositif incliné de +20° en roulis et de +20° en tangage, en butée sur les deux axes.</figcaption></figure>
"""))

    # 2. Architecture
    S.append(("2. Architecture : ce qui bouge, ce qui reste sur la table", f"""
<p><b>Repère</b> (celui du premier montage « Système de stabilisation.SLDASM ») : Z vers le haut, X = axe de roulis, Y = axe de
tangage, origine au centre du corps central à la hauteur des axes des moteurs. Les moteurs sont sur les diagonales : moteur 1 à 45°
(+X, +Y), moteur 2 à 135°, moteur 3 à 225°, moteur 4 à 315°.</p>
{tableau(["Où", "Éléments", "Liaison avec l'autre côté"], [
 ["Sur le dispositif (bouge)", "4 modules de roue (A2212, disque, carter, capteur de vitesse TCRT5000 sur sa potence) sur les faces "
  "diagonales ; sur l'étage (plateau supérieur) : les 4 ESC debout en couronne, le BNO055 au centre, le bornier à deux rangées sur le "
  "bord −X ; au centre, sur 4 entretoises, la carte de distribution XT60 1 vers 4 où se branchent les 4 ESC", "—"],
 ["Sur la table (fixe)", "ESP32 sur la breadboard, régulateur LM2596 à afficheur, alimentation de labo, PC (USB)", "—"],
 ["Entre les deux, face −X", "Nappe des signaux (fils Dupont) : 4 commandes d'ESC et 1 masse ; 4 sorties de capteur de vitesse, "
  "leur 3,3 V et leur masse ; 4 fils du BNO055", "Attachée au corps puis au socle, boucle de mou"],
 ["Entre les deux, face +X", "Câble d'alimentation, de l'entrée de la carte de distribution à l'alimentation de labo", "Attaché au corps puis au socle, boucle de mou"]])}
<p>Les deux câbles sortent par des faces opposées : leurs masses s'équilibrent, et les fils de l'I2C restent loin du courant des
moteurs.</p>
{tableau(["Assemblage SolidWorks", "Contenu", "Mobilités"], [
 ["Banc_stabilisation", "Socle (fixe), poteau, fourche, croisillon, tige de tangage, roulements, colliers, goupilles de butée, dispositif",
  "Roulis et tangage libres, butées à ±20°"],
 ["Dispositif", "Corps central (fixe), 4 modules de roue, plateau supérieur, 4 ESC, bornier et ses 2 barrettes, BNO055, carte de "
  "distribution XT60 sur 4 entretoises et ses 5 fiches, 7 pièces de câblage (une par famille de câbles), paliers de tangage, "
  f"4 tiges d'équilibrage M6 et leurs {n_ecrous} écrous", "Aucune (rigide)"],
 ["Module_roue (×4)", "Platine moteur (fixe), carter, A2212, disque, potence du capteur, TCRT5000", "Disque libre en rotation"]])}
<p>Chaque assemblage n'a qu'une pièce fixe ; toutes les autres sont tenues par le strict minimum de contraintes prises sur leur
géométrie. Les ESC, la carte de distribution et les fiches XT60 sont représentés par leur encombrement ; chaque câble est un tube à son
diamètre et à sa longueur.</p>
<figure><img src='{url(os.path.join(RENDUS, 'etage.png'))}' style='width:118mm'>
<figcaption>Le dispositif câblé : sur l'étage, les 4 ESC (violet) debout autour du BNO055 (vert), le bornier (orange) sur le bord −X ;
fils moteur (bleu), fils d'alimentation (rouge), câbles de commande (rose), câbles des capteurs (bleu clair), câble du BNO055
(vert), nappe vers la table (violet).</figcaption></figure>
<figure><img src='{url(os.path.join(RENDUS, 'distribution.png'))}' style='width:100mm'>
<figcaption>Le centre de l'étage : la carte de distribution XT60 1 vers 4 (noir) sur ses 4 entretoises (laiton), au-dessus du BNO055
(vert) et des ESC (violet). Chaque ESC monte vers sa sortie avec ses 13 cm de fil d'alimentation (rouge) ; le câble d'alimentation
part de l'entrée, côté +X, par-dessus l'ESC +X.</figcaption></figure>
<figure><img src='{url(os.path.join(RENDUS, 'corps.png'))}' style='width:85mm'>
<figcaption>Le corps sans son plateau : contre chaque face diagonale, la boucle des fils moteur (bleu), qui range le mou des
18 cm ; rien ne traverse le centre, place du cardan.</figcaption></figure>
<figure><img src='{url(os.path.join(RENDUS, 'cardan_coupe.png'))}' style='width:125mm'>
<figcaption>Coupe du cardan par le plan XZ, de face et en perspective : croisillon (jaune) au centre du corps, fourche de roulis
(brun) sur le poteau, paliers et colliers de tangage (orange), BNO055 (vert) sur le plateau, à la verticale du centre de rotation.</figcaption></figure>
<h3>Chaîne des liaisons</h3>
{tableau(["Liaison", "Entre", "Réalisation"], [
 ["Encastrement", "Socle et poteau", "Tube Ø12 serré dans le moyeu du socle (2 vis M4)"],
 ["Encastrement", "Poteau et fourche", "Tube engagé de 18 mm, vis de serrage M3"],
 ["Pivot de roulis (axe X)", "Fourche et croisillon", "2 vis épaulées Ø5 vissées dans le croisillon, dans 2 roulements 625 de la fourche"],
 ["Encastrement", "Croisillon et tige", "Tige Ø5 serrée par une vis sans tête M3"],
 ["Pivot de tangage (axe Y)", "Tige et dispositif", "Tige dans 2 roulements 625 portés par les paliers vissés sur le corps"],
 ["Butées ±20°", "Chaque pivot", "Goupille Ø3 emmanchée qui court dans une lumière en arc"],
 ["Blocage", "Chaque pivot", "Goupille Ø3 amovible dans deux trous alignés au repos"]])}
"""))

    # 3. Synthèse
    def tau(p):
        return f(p["tau"] * 1000, 0) + " ms" if p["tau"] else "presque neutre"
    lignes_piv = [[mm(p["zp"]), f(p["h"]), f(p["c5"] * 1000, 0) + " N·mm", f(p["c10"] * 1000, 0) + " N·mm",
                   f(p["I"] * 1e3, 1) + "·10⁻³", tau(p), f(p["alpha"], 0), f(p["d_imu"], 0)] for p in piv]
    S.append(("3. Synthèse du dimensionnement", f"""
<p>Les masses et positions viennent du modèle ; les pièces imprimées sont comptées à 0,8 g/cm³ (2 parois, 15 % de remplissage),
le croisillon et les colliers pleins (1,24 g/cm³), les câbles par leur masse linéique, la carte de distribution et les
fiches par des masses estimées. Ce sont des estimations :
peser le dispositif monté.</p>
{tableau(["Grandeur", "Valeur", "Commentaire"], [
 ["Masse du dispositif (cardan et câblage compris)", f"{f(B['masse'] * 1000, 0)} g", "Poids " + f(B['poids'], 2) + " N"],
 ["Centre de gravité", f"x {f(G[0], 2)}, y {f(G[1], 2)}, z +{f(B['zG'])} mm",
  f"Ramené sur l'axe de tangage par les tiges d'équilibrage : {f(eq['h'], 1)} mm au-dessus du pivot équilibré ({mm(eq['zp'])})"],
 ["Couple d'un décalage latéral du centre de gravité", f"{f(couple_mm, 1)} N·mm par mm", f"Permanent ; pour 1 mm, plus que la gravité à 5° au pivot {mm(p1['zp'])} ({f(p1['c5'] * 1000, 1)} N·mm). D'où l'équilibrage statique (section 8)"],
 ["Constante de couple de l'A2212 (1400 KV)", f"{f(B['kt'] * 1000, 2)} mN·m/A", "kt = 60 / (2π · KV)"],
 ["Couple d'un moteur", f"{f(B['couple_continu'], 3)} N·m à 10 A ; {f(B['couple_max'], 3)} N·m à 19 A", "Courant maxi annoncé 19 A"],
 ["Couple disponible par axe (4 roues × cos 45°)", f"{f(B['couple_axe_continu'], 2)} à {f(B['couple_axe_max'], 2)} N·m", "Selon le courant"],
 ["Couple de gravité à 5°", f"{f(p0['c5'] * 1000, 0)} à {f(pn['c5'] * 1000, 0)} N·mm", f"Selon la position du pivot : au moins {f(B['couple_axe_continu'] / pn['c5'], 0)} fois moins que le couple disponible à 10 A"],
 ["Courant pour tenir la gravité à 5°", f"≈ {f(B['courant_tenue'], 1)} A par moteur", "Pivot le plus bas, courant à vide compris ; quelques ampères au total en équilibre"],
 ["Moment cinétique d'une roue à 3 900 tr/min", f"{f(B['H_roue'], 3)} N·m·s", "J ≈ 1,62·10⁻⁴ kg·m² (disque, vis et rotor, estimation du TP1)"],
 ["Réserve de moment cinétique par axe", f"{f(B['H_axe'], 3)} N·m·s", f"Tient {f(B['H_axe'] / pn['c5'], 1)} s contre la gravité à 5° dans la position la plus dure"],
 ["Énergie d'un disque à 3 900 tr/min", f"{f(B['energie_roue'], 1)} J", "Rendue à l'alimentation quand l'ESC freine (section 9)"],
 ["Débattement", "±20° en roulis et en tangage", "Butées mécaniques"],
 ["Charge par roulement", f"{f(B['charge_roulement'], 1)} N", f"Sécurité statique C0/P ≈ {f(B['s0'], 0)}"],
 ["Frottement d'un pivot sur roulements", f"≈ {f(B['frottement_roulement'], 2)} N·mm", f"Un pivot lisse PLA sur acier ferait ≈ {f(B['frottement_lisse'], 1)} N·mm"],
 ["Contrainte dans la tige Ø5", f"{f(B['tige']['sigma'], 0)} MPa, flèche {f(B['tige']['fleche'], 3)} mm", f"Sécurité ≈ {f(B['tige']['securite'], 0)}"],
 ["Contrainte dans le poteau Ø12 × 1", f"{f(B['tube']['sigma'], 1)} MPa", "En butée, pivot le plus bas"],
 ["Vitesse maximale conseillée des disques", f"≈ {f(v125['n'], 0)} tr/min (1375 à 1625 µs)", f"Sécurité {f(v125['securite'], 1)} sur la tenue des vis d'équilibrage (section 9)"],
 ["Mesure de la vitesse des roues", "4 impulsions par tour", f"≈ {f(v125['n'] * 4 / 60, 0)} Hz à {f(v125['n'], 0)} tr/min : un TCRT5000 par roue (section 7)"],
 ["PLA à prévoir", f"≈ {f(B['pla_total'], 0)} g, ≈ {f(B['heures_total'], 0)} h d'impression", "Détail dans le carnet de commandes"]])}
<h3>Selon la position du centre de rotation</h3>
<p>h est la hauteur du centre de gravité au-dessus du centre de rotation. Sans la batterie, au pivot {mm(p0['zp'])},
h ≈ {f(p0['h'])} mm et le dispositif est presque neutre (il reste où on le pose, ou bascule vers le côté lourd). I est le moment
d'inertie autour de l'axe de roulis passant par le pivot. τ = √(I / m g h) est la constante de temps de la chute libre : plus elle
est courte, plus la commande doit être rapide (une boucle à 200 Hz, 5 ms, reste au moins {f(tau_min / 0.005, 0)} fois plus rapide).
α est l'accélération angulaire que donnent les roues à 10 A. d est la hauteur du BNO055 au-dessus du pivot.</p>
{tableau(["Pivot", "h (mm)", "Gravité à 5°", "à 10°", "I (kg·m²)", "τ", "α (rad/s²)", "d (mm)"], lignes_piv, num=range(1, 8))}
"""))

    # 4. Pièces imprimées
    fiches = []
    f0, f1 = P.fenetre_x()
    fiches.append(fiche("RW-01 · Corps central", "1 pièce, imprimée", [
        ("Fonction", "Caisson central du dispositif : il porte les roues et le cardan, et abrite les boucles des fils moteur."),
        ("Rôle dans le banc", "Porte les 4 modules de roue sur ses faces diagonales et les 2 paliers de tangage sur ses faces ±Y ; abrite le croisillon du cardan. Il ne porte plus d'électronique : les ESC sont sur l'étage. Chaque faisceau de fils moteur entre par une fente ouverte vers le haut (les fils, soudés au moteur et à l'ESC, s'y posent par-dessus, plateau retiré), fait sa boucle contre la face intérieure et monte vers l'étage par l'encoche du coin. Fermé en haut par le plateau supérieur ; ses faces ±X portent les points d'attache des deux câbles qui descendent vers la table."),
        ("Caractéristiques", f"Octogone de {f(2 * R_PAROI, 0)} mm sur plats, parois de {f(E_PAROI, 0)} mm, {f(Z_HAUT - Z_BAS, 0)} mm de haut (z {f(Z_BAS, 0)} à +{f(Z_HAUT, 0)}), rebord bas de {f(REBORD_BAS, 0)} mm. "
         f"{n_ins_corps} inserts M3 : 8 pour les platines, 4 pour le plateau (bossages des faces ±X et ±Y), 20 pour les paliers (5 positions). "
         f"Sur chaque face diagonale : croix de l'A2212 (4 trous Ø3,4), trou Ø14 du bout d'arbre, fente des fils moteur de {f(FENTE_FILS[0], 0)} mm de large, à côté du moteur, <b>ouverte vers le haut</b> (de z +{f(FENTE_FILS[1], 0)} au bord). "
         f"Lumière de la tige sur ±Y, fenêtre d'accès de {f(FENETRE_X[0], 0)} × {f(f1 - f0, 0)} mm aux goupilles de roulis sur ±X, 2 fentes de collier par face ±X à z −20. "
         f"4 passages Ø6,4 des tiges d'équilibrage, un par face ±X et ±Y, à z {f(EQ_Z, 0)} et à {f(EQ_DECALAGE, 0)} mm du milieu de la face, en moulin (+X côté +Y, +Y côté −X, −X côté −Y, −Y côté +X)."),
        ("Dimensionnement", f"Efforts faibles : poids du dispositif (≈ {f(B['poids'], 0)} N) par les paliers, couple de réaction d'un moteur ≤ 0,13 N·m repris par 4 vis M3 et 2 inserts. La largeur de 160 mm est gardée : elle donne {f(2 * ri * math.tan(math.radians(22.5)), 0)} mm de face intérieure par moteur pour la boucle de ses fils (rayon de courbure de {f(R_COURBURE, 0)} mm respecté) et laisse le centre libre pour le cardan. La hauteur couvre les 5 positions du pivot ; sous le plateau, il ne reste que les fils, hors d'atteinte du cardan (balayage contrôlé, section 10)."),
        ("Matière, fabrication", "PLA, 3 parois, 20 %, imprimé debout, rebord bas sur le plateau ; les bossages ont un dessous à 45° (pas de support). " + ligne_masse("RW-01_Moyeu") + "."),
        ("Où se le procurer", "À imprimer (Bambu Lab A1, PLA ; plateau de 256 mm).")], img_piece("RW-01_Moyeu")))
    fiches.append(fiche("RW-02 · Platine moteur", "4 pièces, imprimées", [
        ("Fonction", "Fixe un moteur A2212 sur le corps et porte son carter."),
        ("Rôle dans le banc", f"Interface entre la croix de fixation de l'A2212 (4 trous Ø3,4 en carré de 23,4 mm) et la face diagonale du corps. Place la face d'appui du moteur à {f(R_APPUI, 0)} mm du centre. Son coin haut est découpé au droit de la fente du corps, pour laisser passer les fils moteur."),
        ("Caractéristiques", f"Plaque de {f(E_PLATINE, 0)} mm, 41 × {f(Z_HAUT - Z_BAS, 0)} mm avec deux bras de {f(BARRE[0], 0)} mm, {f(2 * BARRE_R[1], 0)} mm de haut. Croix de l'A2212, trou Ø14, 2 trous Ø3,4 de fixation dans les inserts du corps, coin découpé au droit de la fente des fils moteur, 2 trous des barres du carter."),
        ("Dimensionnement", "Les fils moteur passent à l'abri, à travers la platine et la paroi : rien ne pend à côté du disque. Il reste plus de 50 mm entre deux carters voisins."),
        ("Matière, fabrication", "PLA, 4 parois, 30 %, à plat (face corps dessous). " + ligne_masse("RW-02_Platine-moteur") + ". <b>Attention à la chaleur :</b> la base d'un A2212 peut dépasser 60 °C en usage prolongé, au-delà de la transition vitreuse du PLA (≈ 60 °C). Surveiller la température des moteurs ou imprimer les platines en PETG pour les essais longs."),
        ("Où se le procurer", "À imprimer (PLA).")], img_piece("RW-02_Platine-moteur")))
    fiches.append(fiche("RW-12 · Potence du capteur de vitesse", "4 pièces, imprimées", [
        ("Fonction", "Tient la carte TCRT5000 devant le disque, côté extérieur, là où il y a de la place."),
        ("Rôle dans le banc", f"Vissée sur le bossage du haut du carter, elle descend devant la face extérieure du disque, en avant des écrous d'équilibrage. La carte se visse à plat sous son bras, capteur tourné vers le disque, à {f(math.hypot(TCRT_CARTE[0] / 2 - TCRT_BOITIER[0] / 2, TCRT_V), 1)} mm de l'axe : il voit passer les 4 rayons du disque. Rien n'est plus logé entre le corps et le disque."),
        ("Caractéristiques", f"Semelle de {f(PATTE_CARTER[0], 0)} × 3 mm sur le bossage, bras de {f(POTENCE[0], 0)} × {f(POTENCE[1], 0)} mm. 2 lumières pour vis M3 (inserts du carter) : elles règlent l'écart entre le capteur et le disque de ±2 mm autour de {f(TCRT_ECART, 0)} mm. 1 trou Ø3,2 pour la vis de la carte."),
        ("Dimensionnement", f"Le TCRT5000 fonctionne de 0,2 à 15 mm, au mieux vers 2,5 mm (fiche Vishay). Le boîtier du capteur reste à moins de {f(math.hypot(TCRT_CARTE[0] / 2, TCRT_V + TCRT_BOITIER[1] / 2), 0)} mm de l'axe, hors de la couronne des vis d'équilibrage (48 à 61 mm) ; la prise Dupont de la carte passe à {f(W_CARTE - 1.25 - 1.3 - E_PLATINE - VIS_DISQUE[1], 1)} mm en avant des écrous. Aucun contact au repos ni en rotation (section 10)."),
        ("Matière, fabrication", "PLA, 4 parois, 40 %, à plat sur le flanc. " + ligne_masse("RW-12_Porte-capteur") + "."),
        ("Où se le procurer", "À imprimer (PLA).")], img_piece("RW-12_Porte-capteur")))
    fiches.append(fiche("RW-03 · Carter de disque", "4 pièces, imprimées", [
        ("Fonction", "Protection autour de chaque disque."),
        ("Rôle dans le banc", "Évite le contact des doigts ou des câbles avec le disque en rotation et retient un fragment ou une vis d'équilibrage qui serait éjecté radialement. Tenu par 2 barres vissées sur les bras de la platine (2 inserts M3). Porte la potence du capteur de vitesse."),
        ("Caractéristiques", "Anneau Ø130 / Ø135 mm de 21,5 mm de large, lèvres de 2 mm jusqu'à Ø124, deux barres 10 × 8 mm. En haut de la bande, un bossage de 14 × 6,5 mm avec 2 inserts M3 reçoit la potence du capteur de vitesse."),
        ("Dimensionnement", f"Jeu radial de 4 mm avec l'enveloppe tournante (disque et vis jusqu'à 61 mm de l'axe), jeu axial d'au moins 3 mm. Énergie d'une vis M6 et de son écrou (8 g) éjectés : {f(v125['E'], 1)} J à {f(v125['n'], 0)} tr/min, {f(v200['E'], 1)} J à {f(v200['n'], 0)} tr/min. Une bande de PLA de 2,5 mm n'est pas faite pour retenir des énergies élevées : limiter la vitesse (section 9)."),
        ("Matière, fabrication", "PLA, 4 parois, 30 % (PETG si disponible, moins cassant). Imprimé lèvre extérieure sur le plateau, barres vers le haut, sans support. " + ligne_masse("RW-03_Carter") + "."),
        ("Où se le procurer", "À imprimer (PLA).")], img_piece("RW-03_Carter")))
    fiches.append(fiche("RW-04 · Palier de tangage", "2 pièces, imprimées", [
        ("Fonction", "Porte un roulement de l'axe de tangage."),
        ("Rôle dans le banc", f"Se visse sur une face ±Y du corps, sur l'une des 5 rangées d'inserts ; ses 2 vis passent dans des lumières verticales qui permettent de le monter ou de le descendre de ±{f(PALIER_REGLAGE, 0)} mm. C'est lui qui fixe la hauteur du centre de rotation : la rangée pour le réglage grossier, les lumières pour le réglage fin, jusqu'à mettre le pivot exactement au centre de gravité. Porte la lumière de butée de tangage et le trou de blocage."),
        ("Caractéristiques", f"Plaque 34 × 44 × 8 mm ; logement Ø16,1 × 5 mm du roulement 625 ; passage de tige Ø6,5 ; 2 lumières de 3,4 × {f(2 * PALIER_REGLAGE + 3.4, 1)} mm à 24 mm d'entraxe (vis M3) ; trou de blocage Ø3,2 et lumière en arc de ±20° au rayon 11,5 mm."),
        ("Dimensionnement", f"Charge {f(B['charge_roulement'], 1)} N par palier, reprise par 2 vis M3 serrées : l'adhérence sous les têtes suffit largement. Les rangées d'inserts sont espacées de 8 mm et les lumières font ±{f(PALIER_REGLAGE, 0)} mm : toute hauteur de {mm(min(Z_PIVOTS) - PALIER_REGLAGE)} à {mm(max(Z_PIVOTS) + PALIER_REGLAGE)} est atteignable. Le corps garde sa lumière de tige assez haute pour toute la course."),
        ("Matière, fabrication", "PLA, 5 parois, 40 %, à plat, logement vers le haut. " + ligne_masse("RW-04_Palier") + "."),
        ("Où se le procurer", "À imprimer (PLA).")], img_piece("RW-04_Palier")))
    fiches.append(fiche("RW-05 · Collier de blocage", "2 pièces, imprimées", [
        ("Fonction", "Arrêt axial de la tige de tangage, butée et blocage du tangage."),
        ("Rôle dans le banc", "Serré sur la tige par une vis sans tête M3, il tourne avec elle (donc avec le croisillon). Sa goupille emmanchée court dans la lumière du palier : c'est la butée de tangage. Une goupille amovible dans son trou du bas et celui du palier bloque le tangage."),
        ("Caractéristiques", "Disque Ø32 × 6 mm, alésage Ø5,05, portée Ø9 qui appuie seulement sur la bague intérieure du roulement, trou Ø2,9 (goupille de butée), trou Ø3,2 (blocage), insert M3 radial."),
        ("Dimensionnement", f"L'énergie d'une chute de 0 à 20° dans la position la plus dure n'est que {f(B['energie_chute'] * 1000, 0)} mJ : la goupille Ø3 en acier l'encaisse sans difficulté."),
        ("Matière, fabrication", "PLA plein (100 %), à plat. " + ligne_masse("RW-05_Collier") + "."),
        ("Où se le procurer", "À imprimer (PLA).")], img_piece("RW-05_Collier")))
    fiches.append(fiche("RW-06 · Croisillon", "1 pièce, imprimée", [
        ("Fonction", "Cœur du cardan : relie l'axe de roulis et l'axe de tangage."),
        ("Rôle dans le banc", "Les deux vis épaulées (roulis) s'y vissent et tournent dans la fourche ; la tige de tangage le traverse et y est serrée. Les deux axes se coupent en son centre : le centre de rotation est un point."),
        ("Caractéristiques", "Cube de 28 mm ; alésage Ø5,05 traversant (tige) ; 2 inserts M4 sur ±X (vis épaulées) ; trous de goupille Ø2,9 (butée) et Ø3,2 (blocage) au rayon 11,5 mm sur ±X ; insert M3 sur le dessus (vis sans tête de la tige)."),
        ("Dimensionnement", "Charges de l'ordre de 10 N. La taille de 28 mm vient de la place nécessaire : inserts M4 (Ø5,6 × 8) qui ne doivent pas déboucher dans l'alésage de la tige, goupilles au rayon 11,5 mm pour passer à côté des roulements Ø16."),
        ("Matière, fabrication", "PLA plein (100 %), ou aluminium usiné pour plus de rigidité. " + ligne_masse("RW-06_Croisillon") + "."),
        ("Où se le procurer", "À imprimer (PLA).")], img_piece("RW-06_Croisillon")))
    fiches.append(fiche("RW-07 · Fourche de roulis", "1 pièce, imprimée", [
        ("Fonction", "Support fixe de l'axe de roulis, en haut du poteau."),
        ("Rôle dans le banc", "Ses deux bras portent les roulements des vis épaulées ; son socle se serre sur le tube. Chaque bras a la lumière de butée de roulis et le trou de blocage."),
        ("Caractéristiques", "Socle 46 × 30 × 20 mm, bras de 8 mm à 1 mm du croisillon, sommet arrondi R15 ; logements Ø16,1 × 5 ; passages Ø9 des entretoises ; alésage Ø12,1 × 18 mm, fente et vis M3 de serrage."),
        ("Dimensionnement", f"Hauteur sous le pivot (20 mm) imposée par le balayage du croisillon en roulis (rayon 18 mm à ±20°). Les 5 positions du pivot ({mm(p0['zp'])} à {mm(pn['zp'])}) sont toutes sous le centre de gravité (z ≈ +{f(B['zG'])} mm) : plus haut, le dispositif deviendrait un pendule stable et ne testerait plus la commande."),
        ("Matière, fabrication", "PLA, 5 parois, 40 %, imprimé debout (socle sur le plateau). " + ligne_masse("RW-07_Fourche") + "."),
        ("Où se le procurer", "À imprimer (PLA).")], img_piece("RW-07_Fourche")))
    fiches.append(fiche("RW-08 · Plateau supérieur (étage des ESC)", "1 pièce, imprimée", [
        ("Fonction", "Ferme le corps par le haut et porte toute l'électronique du dispositif, visible et accessible."),
        ("Rôle dans le banc", "Porte le BNO055 au centre, exactement à la verticale du centre de rotation ; les 4 ESC debout autour, chacun entre deux joues et tenu par 2 colliers ; le bornier sur son bord −X. Au centre, 4 trous Ø3,4 reçoivent les entretoises M3 × 35 de la carte de distribution XT60. Dans chaque coin, une encoche ouverte sur le bord laisse monter les fils moteur vers leur ESC et le câble du capteur. Les câbles de signal font le tour par la bordure, entre les ESC et le bord."),
        ("Caractéristiques", f"Octogone de {f(2 * R_PAROI, 0)} mm × {f(E_PLATEAU, 0)} mm, 4 vis M3 dans les bossages des faces ±X, ±Y (la vis −X est celle du bornier). 4 emplacements d'ESC à {f(ESC_A, 0)} mm du centre : 2 joues de {f(SUPPORT_ESC[0], 0)} × {f(SUPPORT_ESC[1], 0)} × {f(SUPPORT_ESC[2], 0)} mm écartées de {f(ESC[2] + 2 * SUPPORT_ESC[3], 0)} mm, 4 fentes de collier. 4 encoches de coin de {f(ENCOCHE_COIN[0], 0)} mm de large, numérotées par 1 à 4 points gravés (numéro du moteur). <b>{n_pc} passe-colliers</b> : tunnels de 3,2 × 2 mm dans l'épaisseur, pour colliers de 2,5 mm, utilisables par-dessus et par-dessous. Logement du BNO055 de 22 × 28 × 1 mm (carte tournée de 90°, barrette côté −X), fenêtre sous la carte. Flèche +X gravée (axe de roulis). 2 trous Ø3,3 pour les pions du bornier."),
        ("Dimensionnement", f"Emplacement prévu pour un ESC de {f(ESC[0], 0)} × {f(ESC[1], 0)} × {f(ESC[2], 0)} mm (78 mm de long mesurés ; largeur et épaisseur prises larges, à mesurer) : un ESC plus mince se cale avec de la mousse, les colliers le serrent. L'ESC dépasse des joues de 10 mm à chaque bout : ses fils sortent librement, et le coude vers l'encoche respecte le rayon de {f(R_COURBURE, 0)} mm du 16 AWG. Le BNO055 est à {f(p0['d_imu'], 0)} mm au-dessus du pivot (position {mm(p0['zp'])}) et à {f(pn['d_imu'], 0)} mm (position {mm(pn['zp'])}) : à 10 rad/s², l'accélération parasite d·α vaut {f(a_imu[0], 1)} à {f(a_imu[1], 1)} m/s², soit {f(a_imu[0] / 9.81 * 100, 0)} à {f(a_imu[1] / 9.81 * 100, 0)} % de g ; la fusion s'appuie surtout sur le gyromètre et filtre cet effet. Les ESC en hauteur remontent le centre de gravité : les 5 positions du pivot ont été décalées d'autant."),
        ("Matière, fabrication", "PLA, 3 parois, 20 %, à plat, joues vers le haut (les tunnels se pontent sur 4 mm sans support). " + ligne_masse("RW-08_Plateau") + "."),
        ("Où se le procurer", "À imprimer (PLA).")], img_piece("RW-08_Plateau")))
    fiches.append(fiche("RW-11 · Bornier à deux rangées", "1 pièce, imprimée", [
        ("Fonction", "Point de raccordement entre le dispositif et la breadboard : câbles de commande des 4 ESC et câbles des 4 capteurs de vitesse."),
        ("Rôle dans le banc", "Tient deux barrettes mâles 1 × 15 au pas de 2,54 dans une lèvre en porte-à-faux hors du corps. <b>À quoi servent ces barrettes :</b> le câble de commande de chaque ESC finit par une prise femelle, et un fil Dupont vers la breadboard aussi : il faut entre les deux une broche mâle des deux côtés. La barrette est cette rallonge mâle-mâle, tenue dans une pièce fixe : les prises ne pendent pas et le dispositif se débranche de la table d'un geste. Rangée intérieure : les prises des 4 ESC, branchées sans modification. Rangée extérieure : les 4 capteurs de vitesse. Dessous, les fils Dupont vers la breadboard descendent le long de la face −X. Débrancher le dispositif prend quelques secondes."),
        ("Caractéristiques", f"Bloc de {f(BORNIER_X[1] - BORNIER_X[0], 0)} × {f(BORNIER_N * 2.54 + 6, 0)} × {f(BORNIER_H, 0)} mm posé sur le plateau, lèvre de {f(BORNIER_X[0] - BORNIER_LEVRE[0], 0)} × {f(BORNIER_LEVRE[1], 0)} mm. Deux logements de barrette 2,7 × 38,4 × 2,6 mm à {f(abs(X_BARRETTES[1] - X_BARRETTES[0]), 0)} mm d'entraxe, fentes des broches de 1,6 mm. Fixé par la vis M3 du plateau en −X (M3 × 16, tête noyée) et 2 pions Ø3 d'orientation. Dans chaque rangée, 4 groupes de 3 broches séparés par une broche vide : ESC (signal, +, −), capteurs (V, G, D)."),
        ("Dimensionnement", "Avec des broches de 20 mm (corps plastique poussé contre l'extrémité courte), il dépasse 6 mm de broche au-dessus pour les prises et 10 mm sous la lèvre pour les fils Dupont ; les prises du dessous pendent à plus de 2 mm de la face du corps. Les 6 mm entre rangées laissent la place à deux prises Dupont côte à côte. Les fils du BNO055 n'y passent pas : sa propre barrette mâle joue déjà ce rôle."),
        ("Matière, fabrication", "PLA, 4 parois, 40 %, lèvre en haut (imprimée à l'envers, sans support). Barrettes tenues par une goutte de colle cyanoacrylate. " + ligne_masse("RW-11_Bornier") + "."),
        ("Où se le procurer", "À imprimer (PLA). Barrettes : voir le carnet de commandes.")], img_piece("RW-11_Bornier")))
    fiches.append(fiche("RW-10 · Socle", "1 pièce, imprimée", [
        ("Fonction", "Pied du banc sur la table."),
        ("Rôle dans le banc", "Tient le poteau verticalement et à la bonne hauteur ; se bride ou se visse sur la table ou sur une planche. Son moyeu reçoit le deuxième point d'attache des deux câbles."),
        ("Caractéristiques", f"Plaque {f(SOCLE[0], 0)} × {f(SOCLE[1], 0)} × {f(SOCLE[2], 0)} mm, moyeu Ø{f(MOYEU_SOCLE[0], 0)} × {f(MOYEU_SOCLE[1], 0)} mm, 4 nervures ; alésage Ø12,1 traversant, fente et 2 vis M4 de serrage ; 4 trous Ø6,5 aux coins. Deux tunnels de 2 × 3,2 mm traversent le moyeu côté −X et côté +X, à 6 mm du haut, pour les colliers des câbles."),
        ("Dimensionnement", f"Le dessus du socle est à {f(-Z_SOCLE, 0)} mm sous le pivot (centre de rotation à {f(-Z_SOCLE + SOCLE[2], 0)} mm au-dessus de la table) : le point le plus bas du dispositif, en butée sur les deux axes, est à 141,0 mm sous le pivot (marge de 15 mm). Le centre de gravité du dispositif ne s'écarte au plus que de {f(B['tube']['excentricite'], 0)} mm de l'axe en butée : le banc ne peut pas basculer, mais un bridage évite qu'il glisse pendant les essais dynamiques. Les câbles s'attachent au socle et non au poteau : le bas du corps balaie la zone du poteau en butée."),
        ("Matière, fabrication", "PLA, 3 parois, 15 %, à plat. " + ligne_masse("RW-10_Socle") + f" : c'est la plus longue impression (environ {f(impression('RW-10_Socle')['heures'], 0)} h). Une planche de bois ou de MDF de {f(SOCLE[0], 0)} × {f(SOCLE[1], 0)} mm, percée Ø12 et avec un collier de serrage, peut le remplacer."),
        ("Où se le procurer", "À imprimer (PLA).")], img_piece("RW-10_Socle")))
    z_bat = Z_PLATEAU + E_PLATEAU + ENTRETOISE + BERCEAU[2] + BATTERIE[2] / 2
    dz_bat = MASSES["batterie"] / (B["masse"] * 1000 + MASSES["batterie"]) * (z_bat - B["zG"])
    fiches.append(fiche("RW-09 · Berceau de batterie", "phase batterie, pas imprimé maintenant", [
        ("Fonction", "Support de la LiPo 3S, de l'embase XT60 et d'un interrupteur, pour un dispositif autonome sans câble d'alimentation."),
        ("Rôle dans le banc", "Hors du montage pendant la phase de test sur alimentation de labo. <b>À reprendre pour la phase batterie</b> : les ESC occupent maintenant le dessus du plateau et montent à 32 mm ; le berceau devra passer au-dessus d'eux, sur des entretoises plus hautes."),
        ("Caractéristiques", "Plateau 130 × 40 × 3 mm, rebords de 6 mm, fentes de sangle de 20 mm, flasques d'extrémité avec découpes XT60 (16,2 × 8,4 mm) et KCD1 (19,2 × 13,2 mm)."),
        ("Dimensionnement", f"La batterie ({f(MASSES['batterie'], 0)} g) en haut remonte le centre de gravité d'environ {f(dz_bat, 0)} mm : les essais deviennent plus durs à pivot égal. Il faudra refaire l'équilibrage. Prévoir un fusible sur le + de la batterie (carnet de commandes)."),
        ("Matière, fabrication", "PLA, 3 parois, 20 %. Environ 18 g."),
        ("Où se le procurer", "À imprimer le jour de la phase batterie.")], img_piece("RW-09_Berceau")))
    S.append(("4. Pièces imprimées", "<p>Imprimante Bambu Lab A1, buse de 0,4 mm, couches de 0,2 mm, PLA. Les masses supposent 2 à 5 parois selon la pièce ; le trancheur donnera les valeurs exactes.</p>" + "".join(fiches)))

    # 5. Mécanique du commerce
    fm = []
    fm.append(fiche("RW-20 · Roulement 625-2Z", "4 pièces", [
        ("Fonction", "Guidage en rotation à très faible frottement."),
        ("Rôle dans le banc", "2 dans la fourche (roulis), 2 dans les paliers (tangage)."),
        ("Caractéristiques", "Roulement à billes à gorge profonde, 5 × 16 × 5 mm, 2 flasques métalliques (2Z ou ZZ) ; charges de base usuelles C ≈ 1,7 kN, C0 ≈ 0,67 kN."),
        ("Dimensionnement", f"Charge {f(B['charge_roulement'], 1)} N par roulement : sécurité statique ≈ {f(B['s0'], 0)}. Le critère qui compte est le frottement : ≈ {f(B['frottement_roulement'], 2)} N·mm (M = ½ μ P d, μ ≈ 0,0015), contre ≈ {f(B['frottement_lisse'], 1)} N·mm pour un pivot lisse PLA sur acier, alors que le couple de gravité à 5° n'est que de {f(p1['c5'] * 1000, 0)} N·mm au pivot {mm(p1['zp'])}. Un pivot lisse fausserait la mesure."),
        ("Matière, fabrication", "Acier, préférer 2Z (flasques métal, moins de frottement que 2RS à joints)."),
        ("Où se le procurer", "AliExpress ou eBay, lot de 10 : 5 à 9 €. Olimex : 0,63 € pièce par 10. 3DJake : lot de 8.")]))
    fm.append(fiche("RW-21 · Tige de tangage Ø5", "1 pièce", [
        ("Fonction", "Axe de tangage."),
        ("Rôle dans le banc", "Serrée dans le croisillon, elle tourne dans les roulements des paliers ; les colliers l'arrêtent axialement."),
        ("Caractéristiques", f"Axe linéaire Ø5 h6, acier chromé trempé, longueur {f(TIGE, 0)} mm."),
        ("Dimensionnement", f"Elle traverse le corps de {f(2 * R_PAROI, 0)} mm, les deux paliers et les deux colliers. Porte-à-faux de {f(B['tige']['porte'])} mm entre le croisillon et le roulement, {f(B['charge_roulement'], 1)} N : moment {f(B['tige']['M'], 0)} N·mm, contrainte {f(B['tige']['sigma'], 0)} MPa (sécurité ≈ {f(B['tige']['securite'], 0)}), flèche {f(B['tige']['fleche'], 3)} mm."),
        ("Matière, fabrication", f"Acier rectifié ; longueur standard de {f(TIGE, 0)} mm, sans coupe."),
        ("Où se le procurer", "AliExpress « axe linéaire 5 mm » (100 à 200 mm, 2 à 5 €), eBay, Ooznest (coupe à la longueur).")]))
    fm.append(fiche("RW-22 · Vis épaulée Ø5 × 10, M4", "2 pièces", [
        ("Fonction", "Tourillons de l'axe de roulis."),
        ("Rôle dans le banc", "Vissées dans les inserts M4 du croisillon, leur épaulement Ø5 tourne dans les roulements de la fourche."),
        ("Caractéristiques", "ISO 7379, épaulement Ø5 f9 × 10 mm, filetage M4 × 6, tête Ø8,5."),
        ("Dimensionnement", f"{f(B['charge_roulement'], 1)} N à {f(B['vis_epaulee']['bras'], 1)} mm du croisillon : contrainte ≈ {f(B['vis_epaulee']['sigma'], 1)} MPa. L'entretoise RW-23 serre la bague intérieure du roulement contre le croisillon."),
        ("Matière, fabrication", "Acier ou inox A2."),
        ("Où se le procurer", "eBay (vis épaulées inox M4, Ø5 × 10, environ 4 €), AliExpress « vis épaulée M4 5 mm », distributeurs professionnels (Lemu, HPC). Une vis CHC M4 et un tube Ø5/Ø4 peuvent dépanner.")]))
    fm.append(fiche("RW-23 · Entretoise Ø8 / Ø5 × 4", "2 pièces", [
        ("Fonction", "Cale entre la bague intérieure du roulement de roulis et le croisillon."),
        ("Rôle dans le banc", "Empêche le roulement de frotter contre le bras de la fourche."),
        ("Caractéristiques", "Tube Ø8 / Ø5,1, longueur 4 mm."),
        ("Dimensionnement", "Effort axial négligeable."),
        ("Matière, fabrication", "À imprimer en PLA plein (quelques minutes) ou laiton."),
        ("Où se le procurer", "À imprimer.")]))
    fm.append(fiche("RW-24 · Goupille Ø3 × 16", "4 pièces", [
        ("Fonction", "Butées et blocage des deux axes."),
        ("Rôle dans le banc", "2 goupilles de butée emmanchées (dans le croisillon pour le roulis, dans un collier pour le tangage), 2 goupilles de blocage amovibles."),
        ("Caractéristiques", "Goupille cylindrique acier Ø3 × 16 (ISO 2338 ou 8734) ; trous Ø2,9 (emmanchement) et Ø3,2 (glissant)."),
        ("Dimensionnement", f"Énergie de chute en butée ≤ {f(B['energie_chute'] * 1000, 0)} mJ : largement dans les capacités d'une goupille acier Ø3."),
        ("Matière, fabrication", "Acier ou inox."),
        ("Où se le procurer", "Bambu Lab Store (« D3 dowel pins », 3 × 16, lot de 20), Amazon ou AliExpress (lot de 50, 4 à 8 €).")]))
    fm.append(fiche("RW-25 · Poteau, tube Ø12 × 1", "1 pièce", [
        ("Fonction", "Colonne entre le socle et la fourche."),
        ("Rôle dans le banc", f"Place le centre de rotation à environ {f(-Z_SOCLE + SOCLE[2], 0)} mm au-dessus de la table ; sa hauteur se règle dans le collier du socle."),
        ("Caractéristiques", f"Tube aluminium rond Ø12 × 1 mm, longueur {f(TUBE[2], 0)} mm (bas à 4 mm de la table)."),
        ("Dimensionnement", f"En butée à 20° dans la position la plus dure, le centre de gravité est à {f(B['tube']['excentricite'], 1)} mm de l'axe : moment {f(B['tube']['M'], 0)} N·mm, contrainte {f(B['tube']['sigma'], 1)} MPa (sécurité ≈ {f(B['tube']['securite'], 0)})."),
        ("Matière, fabrication", f"Aluminium ; couper à {f(TUBE[2], 0)} mm, ébavurer."),
        ("Où se le procurer", "Brico Dépôt : tube rond aluminium brut 12 × 1 mm, 1 m, 6,09 € ; Castorama, Bricomarché.")]))
    dehors = EQ_TIGE[1] - E_PAROI - EQ_INTERIEUR
    m_tot = B["masse"] * 1000
    fin = MASSES["ecrou_m6"] * 10.0 / m_tot                       # déplacement du centre de gravité pour un écrou déplacé de 10 mm
    gros = MASSES["ecrou_m6"] * (R_PAROI + dehors - EQ_ECROU[1] / 2) / m_tot
    img_eq = os.path.join(RENDUS, "equilibrage.png")
    fm.append(fiche("RW-40 · Tige d'équilibrage, tige filetée M6 × 60", "4 pièces", [
        ("Fonction", "Porte les masses d'équilibrage (écrous) qui amènent le centre de gravité sur les axes du cardan."),
        ("Rôle dans le banc", f"Une tige par face ±X et ±Y du corps, à z {f(EQ_Z, 0)} (sous l'axe des roues), à {f(EQ_DECALAGE, 0)} mm du milieu de la face, en moulin : "
         "elles passent à côté des fenêtres d'accès (±X) et des paliers (±Y) dans toute leur course, et leurs masses s'annulent deux à deux. "
         f"Serrée sur la paroi par un écrou de chaque côté, elle dépasse de {f(EQ_INTERIEUR, 1)} mm à l'intérieur et de {f(dehors, 1)} mm à l'extérieur."),
        ("Caractéristiques", f"Tige filetée M6 (DIN 976), coupée à {f(EQ_TIGE[1], 0)} mm, {f(MASSES['tige_m6'], 1)} g ; passage Ø6,4 dans la paroi."),
        ("Dimensionnement", f"Un écrou M6 ({f(MASSES['ecrou_m6'], 1)} g) déplacé de 10 mm déplace le centre de gravité de ≈ {f(fin, 3)} mm (réglage fin) ; "
         f"un écrou ajouté au bout d'une tige, de ≈ {f(gros, 2)} mm (réglage grossier). Jeux vérifiés en CAO : 2,2 mm entre les écrous des tiges ±Y et les paliers "
         "au plus bas de leur course, 2,3 mm entre le bout de chaque tige et le carter voisin (pièces fixes l'une par rapport à l'autre), 9 mm au disque en rotation."),
        ("Matière, fabrication", "Acier zingué (ou inox A2). Couper à la scie à métaux, ébavurer et repasser un écrou sur chaque bout coupé."),
        ("Où se le procurer", "Quincaillerie ou Brico : tige filetée M6 de 1 m (≈ 2 €), à couper en 4 ; ou goujons M6 × 60.")], img_eq))
    fm.append(fiche("RW-41 · Écrou hexagonal M6", f"{n_ecrous} pièces dans le réglage du modèle", [
        ("Fonction", "Serrage des tiges d'équilibrage et masses de réglage."),
        ("Rôle dans le banc", f"2 écrous par tige la serrent sur la paroi, un de chaque côté. Les autres font la masse d'équilibrage : réglage du modèle "
         f"{', '.join(f'{n} sur {c}' for n, c in zip(EQ_ECROUS, FACES_EQ))}. Chaque paquet se bloque en serrant ses écrous l'un contre l'autre (contre-écrou)."),
        ("Caractéristiques", f"Écrou hexagonal M6 ISO 4032, {f(EQ_ECROU[0], 0)} mm sur plats, {f(EQ_ECROU[1], 0)} mm de haut, {f(MASSES['ecrou_m6'], 1)} g."),
        ("Dimensionnement", "Masse à l'unité : la répartition finale dépend du câblage réel, prévoir des écrous de réserve (4 par tige au plus)."),
        ("Matière, fabrication", "Acier zingué."),
        ("Où se le procurer", "Quincaillerie ou Brico, sachet de 20 à 50 (≈ 2 à 4 €).")], img_eq))
    vis = tableau(["Nb", "Article", "Emplacement"], [
        [str(n_ins_corps + 19), "Insert à chaud M3 × 5,7 (perçage Ø4)", f"Corps {n_ins_corps}, carters 16 (barres 8, bossages des potences 8), colliers 2, croisillon 1"],
        ["2", "Insert à chaud M4 (perçage Ø5,6)", "Croisillon (vis épaulées)"],
        ["16", "Vis CHC M3 × 14 et écrou Nylstop", "Croix A2212, platine et paroi du corps"],
        ["20", "Vis CHC M3 × 8", "Platines dans les inserts du corps (8) ; potences dans les inserts des carters (8) ; cartes TCRT5000 avec écrou (4)"],
        ["11", "Vis CHC M3 × 10", "Plateau (3), carters (8)"],
        ["4", "Vis CHC M3 × 12", "Paliers (4)"],
        ["2", "Vis CHC M3 × 16", "Bornier et plateau (1), serrage de la fourche avec écrou (1)"],
        ["3", "Vis sans tête M3 × 5", "Colliers (2), croisillon (1)"],
        ["2", "Vis M4 × 30 et écrou", "Serrage du tube dans le socle"],
        ["≈ 30", "Colliers de serrage de 2,5 mm", "ESC (8), boucles des fils moteur (4), câbles de signal sur la bordure (≈ 10), câbles vers la table (4), fils d'alimentation (4)"],
        ["4", "Entretoise hexagonale M3 × 35 F/F, vis M3 × 6 (4) et M3 × 8 (4)", "Carte de distribution XT60 (vis M3 × 6 dessus), plateau (vis M3 × 8 dessous)"],
        ["1", "Adhésif mousse double face", "BNO055 (tenue et amortissement des vibrations) ; cales des ESC si besoin"]])
    S.append(("5. Composants mécaniques du commerce", "".join(fm) + "<h3>Visserie et inserts</h3><p>Les inserts à chaud se posent au fer à souder, à la température d'impression plus 10 à 20 °C, avec un embout adapté.</p>" + vis))

    # 6. Actionneurs
    act = []
    act.append(fiche("A2212 · Moteur brushless", "4 pièces", [
        ("Fonction", "Actionneur de chaque roue de réaction."),
        ("Rôle dans le banc", "Accélère ou freine son disque ; le couple de réaction redresse le dispositif."),
        ("Caractéristiques", f"Moteur à rotor extérieur 28 × 27 mm, environ 58 g, croix de fixation à 4 trous M3 (carré de 23,4 mm), arbre Ø3,17. Version 1400 KV (fiche E-S Motor du dossier crystof) : vitesse à vide en 3S ≈ {f(C.KV * C.V_BAT, 0)} tr/min ; 2 à 3S ; courant maxi annoncé 19 A. Ses 3 fils sont soudés aux fils de l'ESC."),
        ("Dimensionnement", f"kt = 60 / (2π · KV) = {f(B['kt'] * 1000, 2)} mN·m/A, soit {f(B['couple_continu'], 3)} N·m à 10 A et {f(B['couple_max'], 3)} N·m à 19 A. Par axe : {f(B['couple_axe_continu'], 2)} à {f(B['couple_axe_max'], 2)} N·m, contre {f(pn['c5'], 3)} N·m de gravité à 5° dans la position la plus dure. Ce moteur, trop faible pour le robot complet de 6,5 kg (decisions-techniques.md), convient au banc."),
        ("Matière, fabrication", "Commerce. Fixé par 4 vis M3 × 14 à travers la croix, la platine et la paroi du corps. Orienter la sortie de ses fils vers le haut, face à la fente (voir section 8)."),
        ("Où se le procurer", "En stock (à vérifier : 4 moteurs identiques). Sinon AliExpress ou RobotShop, 8 à 12 € pièce ; prendre le même KV pour les 4.")]))
    act.append(fiche("Disque d'inertie", "4 pièces (conception existante)", [
        ("Fonction", "Volant d'inertie de chaque roue."),
        ("Rôle dans le banc", "Stocke le moment cinétique : plus il est grand, plus la roue peut corriger longtemps avant de saturer."),
        ("Caractéristiques", "Disque PLA Ø120 × 4,5 mm à 4 rayons (disque.SLDPRT), 4 vis M6 et écrous d'équilibrage dans des trous Ø7 au rayon 55 mm, monté sur l'arbre (sous-ensemble disque_vis)."),
        ("Dimensionnement", f"Inertie estimée avec le rotor et les vis : 1,62·10⁻⁴ kg·m² ; moment cinétique {f(B['H_roue'], 3)} N·m·s à {f(v125['n'], 0)} tr/min. Le point faible est la tenue des vis : il ne reste que 1,5 mm de PLA entre le trou Ø7 et le bord du disque. Voir la section 9 pour la vitesse admissible."),
        ("Matière, fabrication", "Déjà imprimé. Vis M6 avec écrous freinés (Nylstop) ou frein-filet."),
        ("Où se le procurer", "En stock (déjà conçu et imprimé).")]))
    act.append(fiche("ESC · Brushless 30 A, 2-4S, BEC 5 V / 2 A", "4 pièces (les tiens)", [
        ("Fonction", "Pilote un moteur brushless à partir d'une impulsion de commande."),
        ("Rôle dans le banc", "Reçoit de l'ESP32 une impulsion de 1000 à 2000 µs à 50 Hz (1500 µs = arrêt) et fait tourner son moteur dans un sens ou dans l'autre (fonctionnement bidirectionnel déjà testé sur le banc à un moteur)."),
        ("Caractéristiques", f"ESC sans capteur, 30 A, 2 à 4S, BEC 5 V / 2 A. Longueur mesurée : 78 mm ; enveloppe prise à {f(ESC[0], 0)} × {f(ESC[1], 0)} × {f(ESC[2], 0)} mm (largeur et épaisseur à mesurer). Câblage existant gardé tel quel : 3 fils moteur de 18 cm, en 16 AWG silicone, soudés aux fils du moteur ; alimentation rouge et noire de 13 cm, terminée par une XT60 ; câble de commande 3 fils (blanc = signal, rouge = 5 V du BEC, noir = masse) d'environ 25 cm, terminé par une prise femelle au pas de 2,54."),
        ("Dimensionnement", f"Courant maxi du moteur 19 A : marge de 1,6 avec 30 A. Debout sur l'étage, entre deux joues, à {f(ESC_A, 0)} mm du centre : bout moteur vers le coin de son moteur, bout alimentation et commande vers le coin précédent. À l'air libre, il refroidit bien. Les 4 BEC ne doivent pas être reliés entre eux ni au 5 V de la breadboard : la broche + de chaque groupe du bornier ne reçoit aucun fil dessous."),
        ("Matière, fabrication", "Commerce. Aucune modification du câblage. 2 colliers par ESC, passés dans les fentes du plateau."),
        ("Où se le procurer", "Déjà disponibles (nombre à vérifier). Sinon AliExpress ou eBay « ESC 30A brushless bidirectionnel » (9 à 15 €) ; RobotShop « Basic 30A ESC (forward/reverse) ». Vérifier « brushless » et « reverse » sur la fiche.")],
        os.path.join(RENDUS, "etage.png")))
    S.append(("6. Actionneurs : moteurs, disques, ESC", "<p>Image de la fiche ESC : le dispositif câblé, les 4 ESC (violet) debout sur l'étage.</p>" + "".join(act)))

    return garde, S, n_pc, couple_mm


def doc_technique():
    garde, S, n_pc, couple_mm = doc_technique_debut()
    piv = B["pivots"]
    eq = B["equilibre"]
    n_ecrous = sum(EQ_ECROUS) + 2 * len(EQ_FACES)
    n_ins_corps = 2 * len(ANGLES_ROUES) + len(VIS_PLATEAU) + 2 * 2 * len(Z_PIVOTS)
    e_cond = 0.5 * 2200e-6 * (16.0 ** 2 - 12.0 ** 2)          # énergie absorbée par 2 200 µF de 12 à 16 V (J)
    CK = K.cables()                                            # câblage dessiné : longueurs et diamètres
    LC = {n: K.longueur(pts, r) for n, (_, pts, _, r) in CK.items()}
    DC = {n: d for n, (_, _, d, _) in CK.items()}
    v125 = next(v for v in B["vitesses"] if v["offset"] == 125)
    v200 = next(v for v in B["vitesses"] if v["offset"] == 200)

    # 7. Électronique, câblage et alimentation
    el = []
    el.append(fiche("GY-BNO055 · Centrale inertielle", "sur le dispositif, au centre du plateau", [
        ("Fonction", "Mesure l'inclinaison et la vitesse de rotation du dispositif."),
        ("Rôle dans le banc", "Fournit le roulis, le tangage et les vitesses angulaires à la boucle de commande de l'ESP32, par l'I2C de la nappe des signaux."),
        ("Caractéristiques", "BNO055 (Bosch) : accéléromètre, gyromètre et magnétomètre avec fusion intégrée ; I2C (adresse 0x28 ou 0x29) ; 3 à 5 V. Carte GY-BNO055 avec sa barrette 8 broches soudée (VIN, GND, SCL, SDA, ADD, INT, BOOT, RST), encombrement pris à 27 × 21 mm (à mesurer)."),
        ("Dimensionnement", "Placé à la verticale du centre de rotation pour limiter les accélérations parasites (section 3). Posé côté inscriptions vers le haut comme sur la photo du module, broches vers le haut, barrette vers −X : les fils Dupont se branchent d'en haut et partent directement vers la sortie −X. La fusion sort à 100 Hz : une boucle à 200 Hz relit une fois sur deux la même valeur ; lire aussi le gyromètre brut, ou caler la boucle sur 100 Hz. <b>Mode conseillé : IMUPLUS</b> (gyromètre et accéléromètre) : les aimants des A2212, à 5 à 9 cm, faussent le magnétomètre utilisé par le mode NDOF. Avec 40 cm de fils, régler l'I2C à 100 kHz."),
        ("Matière, fabrication", "Tenu sur les trois appuis du logement par de l'adhésif mousse double face. Régler la correspondance des axes (AXIS_MAP_CONFIG et AXIS_MAP_SIGN) pour que la flèche gravée du plateau soit l'axe de roulis +X."),
        ("Où se le procurer", "Disponible. Sinon eBay ou AliExpress, 10 à 18 €.")]))
    n_max = C.vitesse(500)
    el.append(fiche("RW-33 · TCRT5000 · Capteur de vitesse de roue", "4 pièces, une par roue, sur la potence RW-12", [
        ("Fonction", "Mesure la vitesse de rotation de chaque disque."),
        ("Rôle dans le banc", "Placé devant la face extérieure du disque, il voit passer ses 4 rayons : le rayon renvoie l'infrarouge, le vide entre deux rayons ne renvoie rien. La carte sort une impulsion par rayon, sans rien coller sur le disque. La commande en tire la vitesse de chaque roue : elle voit venir la saturation, peut désaturer les roues et boucler sur l'état complet (angle, vitesse angulaire, vitesse des roues)."),
        ("Caractéristiques", f"Carte du commerce : TCRT5000 (LED infrarouge et phototransistor), comparateur LM393, potentiomètre de seuil, LED témoin, 4 broches (VCC, GND, D0, A0), 3,3 à 5 V. Encombrement pris à {f(TCRT_CARTE[0], 0)} × {f(TCRT_CARTE[1], 0)} mm, un trou M3 (à mesurer)."),
        ("Dimensionnement", f"4 rayons par tour : ≈ {f(v125['n'] * 4 / 60, 0)} impulsions par seconde à {f(v125['n'], 0)} tr/min, ≈ {f(n_max * 4 / 60, 0)} à la vitesse à vide maximale ({f(n_max, 0)} tr/min) : sans difficulté pour le capteur et l'ESP32. Au rayon de lecture, un rayon du disque fait environ 11 mm de large, bien plus que la tache du capteur. À 200 Hz de boucle, il ne tombe qu'une ou deux impulsions par période : <b>mesurer la durée entre deux fronts</b> (interruption et horodatage, ou compteur PCNT), pas le nombre d'impulsions par période. Le capteur ne voit pas le sens : on le prend dans le signe de la commande de l'ESC. <b>Alimenter en 3,3 V</b> (broche 3V3 de l'ESP32) : en 5 V, la sortie D0 monterait à 5 V sur une entrée qui n'en supporte que 3,6. Consommation ≈ 10 à 20 mA par carte. Si le PLA rouge du disque renvoie mal l'infrarouge, coller une bande d'adhésif aluminium ou blanc sur chaque rayon."),
        ("Matière, fabrication", f"Commerce. Vis M3 × 8 et écrou sous le bras de la potence, capteur vers le disque. Son câble (3 fils Dupont, {f(min(LC[f'capteur{k}'] for k in range(1, 5)) / 10, 0)} à {f(max(LC[f'capteur{k}'] for k in range(1, 5)) / 10, 0)} cm selon la roue) contourne le carter par le haut, rejoint l'étage et suit la bordure jusqu'à la rangée extérieure du bornier, sans entrer dans le corps. Régler le seuil au potentiomètre : en tournant le disque à la main, la LED témoin doit changer à chaque rayon."),
        ("Où se le procurer", "AliExpress ou Amazon « module TCRT5000 » (lot de 5 à 10, environ 1 € pièce, prix estimé).")],
        os.path.join(RENDUS, "module_roue.png")))
    el.append(fiche("RW-36 · Barrette mâle 1 × 15", "2 pièces, dans le bornier RW-11", [
        ("Fonction", "Raccords mâle-mâle entre les prises femelles (ESC, capteurs) et les fils Dupont de la nappe."),
        ("Rôle dans le banc", "Chaque broche traverse la lèvre du bornier : dessus, la prise de l'ESC ou le fil du capteur ; dessous, un fil Dupont femelle-mâle vers la breadboard. Aucun câble existant n'est modifié."),
        ("Caractéristiques", "Barrette mâle simple rangée au pas de 2,54 mm, broches longues d'environ 20 mm, coupée à 15 broches (4 groupes de 3 séparés par une broche vide)."),
        ("Dimensionnement", "Courants de quelques milliampères. Les broches longues laissent 6 mm de prise au-dessus et 10 mm dessous ; une barrette standard (3 mm côté court) tiendrait mal les fils Dupont. Sous la rangée des capteurs, les 4 broches V sont reliées entre elles par un fil nu soudé, de même pour les 4 broches G : un seul fil Dupont pour chacun vers la breadboard."),
        ("Matière, fabrication", "Commerce. Une goutte de colle cyanoacrylate dans le logement."),
        ("Où se le procurer", "AliExpress ou Amazon « barrette mâle 2,54 broches longues 20 mm » (lot de 10 barrettes de 40 broches, 2 à 4 €).")]))
    el.append(fiche("RW-37 · Carte de distribution XT60 1 vers 4", "la tienne (Jonronfey), au centre de l'étage", [
        ("Fonction", "Distribue l'alimentation aux 4 ESC."),
        ("Rôle dans le banc", f"Posée au centre de l'étage sur 4 entretoises M3 × 35 F/F, au-dessus du BNO055 et des ESC. Le câble d'alimentation de labo se branche sur son entrée XT60 mâle, côté +X ; chaque ESC se branche sur une de ses 4 sorties XT60 femelles, directement avec ses 13 cm de fil. La LED de polarité reste visible d'en haut. Sortie la plus à +X : ESC 2 ; puis ESC 1, ESC 3, ESC 4 : chaque fil part vers le coin de son ESC sans en croiser un autre."),
        ("Caractéristiques", f"Entrée XT60 mâle coudée, 4 sorties XT60 femelles droites en ligne, LED de polarité, 60 A annoncés. Carte prise à {f(PDB[0], 0)} × {f(PDB[1], 0)} mm (annonce Jonronfey), 4 trous M3, entraxe pris à 66 × 24 mm et position des sorties relevées sur la photo du vendeur : <b>à vérifier sur la carte</b>, puis corriger rw_params.py."),
        ("Dimensionnement", f"À plat entre les ESC, la fiche du câble d'alimentation branchée sur l'entrée (environ {f(PDB_ENTREE[1] - PDB[0] / 2 + FICHE_ENTREE, 0)} mm hors de la carte) aurait buté dans l'ESC +X : le carré libre au centre ne fait que {f(2 * (ESC_A - ESC[2] / 2 - SUPPORT_ESC[3] - SUPPORT_ESC[0]), 0)} mm. Sur ses entretoises, le dessous de la carte passe {f(ENTRETOISE - ESC[1], 0)} mm au-dessus des ESC et la fiche d'entrée passe par-dessus l'ESC +X. Les 13 cm de chaque ESC suffisent pour monter jusqu'à sa sortie, en diagonale au-dessus des ESC. Courant de quelques ampères en équilibre, jusqu'à la limite de l'alimentation en pointe : largement dans les capacités de la carte, des XT60 et du 16 AWG (environ 20 A en continu en silicone)."),
        ("Matière, fabrication", "Commerce. 4 vis M3 × 6 sur les entretoises ; les entretoises tenues sous le plateau par 4 vis M3 × 8."),
        ("Où se le procurer", "Déjà achetée (Amazon, Jonronfey « XT60 Male to 4 XT60 Female 1 to 4 Splitter », 12,50 €).")],
        os.path.join(RENDUS, "distribution.png")))
    el.append(fiche("Câbles vers la table", "nappe des signaux (−X) et câble d'alimentation (+X)", [
        ("Fonction", "Relient le dispositif, qui bouge, à la table."),
        ("Rôle dans le banc", "Nappe des signaux, 15 fils : 4 commandes d'ESC et 1 masse ; 4 sorties de capteur, leur 3,3 V et leur masse ; 4 fils du BNO055. Câble d'alimentation : de l'entrée de la carte de distribution XT60 vers l'alimentation de labo."),
        ("Caractéristiques", "Chaque câble descend sa face du corps, passe dans un collier tenu par 2 fentes à z −20, fait une boucle libre d'environ 10 cm, puis passe dans un collier tenu dans un tunnel du moyeu du socle, avant d'aller sur la table."),
        ("Dimensionnement", "Un câble tendu entre la table et le dispositif crée un couple parasite. Les points d'attache sont proches de l'axe et la boucle est souple : le couple reste petit et à peu près constant, et la commande le voit comme une perturbation. Fils souples (silicone, Dupont) ; ne pas serrer la boucle. <b>Ne pas torsader les fils de l'I2C avec les commandes des ESC</b> : les fronts des impulsions perturberaient SDA et SCL. Deux paquets dans le même collier : l'I2C (SDA torsadé avec GND, SCL avec VIN) d'un côté, les commandes et les capteurs de l'autre."),
        ("Matière, fabrication", "Fils Dupont femelle-mâle de 40 cm ; fil d'alimentation existant."),
        ("Où se le procurer", "Fils Dupont : AliExpress ou Amazon (lot de 40, 2 à 4 €).")]))
    el.append(fiche("ESP32 DevKit V1", "sur la table, sur la breadboard", [
        ("Fonction", "Calculateur du banc."),
        ("Rôle dans le banc", "Lit le BNO055 (I2C) et les 4 capteurs de vitesse, exécute la boucle de stabilisation à 200 Hz et commande les 4 ESC (PWM LEDC 50 Hz) ; liaison USB avec le PC. Il reste sur la breadboard jusqu'à la carte imprimée de la version suivante."),
        ("Caractéristiques", "Modèle 30 broches de 48,5 × 25,9 mm, double cœur 240 MHz, logique 3,3 V, alimenté par l'USB ou en 5 V par la broche VIN."),
        ("Dimensionnement", f"Charge de calcul faible pour 200 Hz. <b>Brochage :</b> I2C sur 21 (SDA) et 22 (SCL) ; ESC 1 à 4 sur {', '.join(map(str, ESC_GPIO))} ; capteurs de vitesse 1 à 4 sur {', '.join(map(str, CAPTEUR_GPIO))} (entrées seules, sans résistance de tirage interne : celle de la carte TCRT5000 suffit). Les entrées 36 et 39 peuvent voir de brèves impulsions parasites quand le convertisseur analogique ou le Wi-Fi est actif (errata Espressif) : garder le Wi-Fi coupé ou filtrer (filtre du compteur PCNT). Vérifier que le firmware n'utilise ni 21 ou 22 pour un ESC, ni 27 pour un capteur."),
        ("Matière, fabrication", "Breadboard posée près du banc (40 cm de fils au plus)."),
        ("Où se le procurer", "Disponible. Sinon 5 à 8 € (AliExpress, Amazon).")]))
    el.append(fiche("LM2596 à afficheur · Régulateur 5 V", "sur la table", [
        ("Fonction", "Abaisse la tension de l'alimentation à 5 V pour l'ESP32."),
        ("Rôle dans le banc", "Alimente l'ESP32 par sa broche VIN quand il tourne sans PC. Avec le PC branché en USB, l'USB suffit."),
        ("Caractéristiques", "Abaisseur réglable avec voltmètre à 3 chiffres et borniers à vis, environ 66 × 36 mm (à mesurer)."),
        ("Dimensionnement", "Consommation ≈ 0,35 A (ESP32 jusqu'à 240 mA, BNO055 12 mA, 4 TCRT5000 jusqu'à 80 mA sur le 3,3 V de l'ESP32). <b>Régler la sortie à 5,0 V avant de brancher l'ESP32</b> (afficheur, puis multimètre)."),
        ("Matière, fabrication", "Sur la table, à côté de la breadboard : il n'alourdit pas le dispositif."),
        ("Où se le procurer", "Disponible.")]))
    el.append(fiche("Alimentation de labo", "la tienne, sur la table", [
        ("Fonction", "Source d'énergie de la phase de test."),
        ("Rôle dans le banc", "Alimente les 4 ESC par le câble d'alimentation et la carte de distribution XT60, et le LM2596."),
        ("Caractéristiques", "Alimentation réglable avec limitation de courant (courant maximal à vérifier)."),
        ("Dimensionnement", f"Régler 12,0 V (entre la LiPo 3S nominale, 11,1 V, et chargée, 12,6 V). En équilibre, quelques ampères au total ; ≈ {f(B['courant_tenue'], 1)} A par moteur pour tenir la gravité à 5° au pivot le plus bas. La limite de courant borne les pointes et donc le couple disponible : la régler au maximum de l'alimentation (au moins 10 A conseillés). Voir la section 9 pour le freinage."),
        ("Matière, fabrication", "Sortie coupée pendant tout câblage."),
        ("Où se le procurer", "Disponible. Phase batterie : LiPo 3S 2200 mAh 40C (voir le carnet de commandes).")]))
    schema = """
<figure><svg width="172mm" viewBox="0 0 700 330" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Arial" font-size="12">
<defs><marker id="f" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#333"/></marker>
<marker id="r" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#c0392b"/></marker>
<marker id="v" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#2a7a2a"/></marker></defs>
<rect x="2" y="2" width="318" height="326" rx="8" fill="#f6f8fb" stroke="#b8c7d8"/><rect x="372" y="2" width="326" height="326" rx="8" fill="#fbf7f0" stroke="#d8c7a8"/>
<text x="160" y="320" text-anchor="middle" fill="#555">SUR LA TABLE</text><text x="535" y="320" text-anchor="middle" fill="#555">SUR LE DISPOSITIF (bouge)</text>
<g stroke="#1b3a5c" stroke-width="1.5" fill="#e3ebf4">
<rect x="14" y="16" width="128" height="46" rx="5"/><rect x="14" y="120" width="128" height="46" rx="5"/><rect x="14" y="236" width="128" height="40" rx="5"/>
<rect x="178" y="150" width="128" height="92" rx="5"/>
<rect x="386" y="16" width="104" height="46" rx="5"/><rect x="524" y="10" width="78" height="30" rx="5"/><rect x="524" y="48" width="78" height="30" rx="5"/>
<rect x="524" y="86" width="78" height="30" rx="5"/><rect x="524" y="124" width="78" height="30" rx="5"/><rect x="622" y="10" width="66" height="144" rx="5"/>
<rect x="386" y="190" width="104" height="44" rx="5"/></g>
<rect x="386" y="252" width="104" height="44" rx="5" stroke="#2a7a2a" stroke-width="1.5" fill="#e6f4e6"/>
<rect x="540" y="200" width="148" height="44" rx="5" stroke="#2a7a2a" stroke-width="1.5" fill="#e6f4e6"/>
<g text-anchor="middle" fill="#1d1d1b">
<text x="78" y="36">Alimentation</text><text x="78" y="52">de labo, 12 V</text><text x="78" y="140">LM2596</text><text x="78" y="156">5,0 V</text>
<text x="78" y="261">PC (USB)</text><text x="242" y="172">ESP32</text><text x="242" y="187">sur la breadboard</text><text x="242" y="203" font-size="10">PWM 25, 26, 27, 32</text><text x="242" y="217" font-size="10">I2C 21, 22</text><text x="242" y="231" font-size="10">Capteurs 36, 39, 34, 35</text>
<text x="438" y="36">Carte de</text><text x="438" y="52">distribution XT60</text>
<text x="563" y="30">ESC 1</text><text x="563" y="68">ESC 2</text><text x="563" y="106">ESC 3</text><text x="563" y="144">ESC 4</text>
<text x="655" y="78">4 × A2212</text><text x="655" y="94" font-size="10">fils soudés</text>
<text x="438" y="209">Bornier RW-11</text><text x="438" y="225" font-size="10">2 rangées 1 × 15</text>
<text x="438" y="271">BNO055</text><text x="438" y="287" font-size="10">centre du plateau</text><text x="614" y="219">4 × TCRT5000</text><text x="614" y="235" font-size="10">vitesse des roues</text></g>
<g stroke="#333" stroke-width="1.7" fill="none" marker-end="url(#f)">
<path d="M142,39 H384"/><path d="M78,62 V118"/><path d="M142,143 C160,143 160,170 176,170"/>
<path d="M490,39 C507,39 507,25 522,25"/><path d="M490,39 C507,39 507,63 522,63"/><path d="M490,39 C507,39 507,101 522,101"/><path d="M490,39 C507,39 507,139 522,139"/>
<path d="M602,25 H620"/><path d="M602,63 H620"/><path d="M602,101 H620"/><path d="M602,139 H620"/></g>
<path d="M142,256 C160,256 160,215 176,215" stroke="#888" stroke-width="1.5" fill="none" marker-end="url(#f)"/>
<text x="262" y="33" text-anchor="middle" font-size="10" fill="#333">câble d'alimentation, sortie +X</text>
<g stroke="#c0392b" stroke-width="1.4" fill="none" stroke-dasharray="5,3">
<path d="M306,195 H384" marker-end="url(#r)"/><path d="M470,190 C470,170 540,175 563,156" marker-end="url(#r)"/></g>
<text x="345" y="186" text-anchor="middle" font-size="10" fill="#c0392b">nappe −X</text>
<text x="525" y="183" font-size="10" fill="#c0392b">câbles de commande</text>
<path d="M386,272 C345,272 345,236 308,236" stroke="#2a7a2a" stroke-width="1.5" fill="none" marker-end="url(#v)"/>
<path d="M386,222 H308" stroke="#2a7a2a" stroke-width="1.5" fill="none" marker-end="url(#v)"/><path d="M540,222 H492" stroke="#2a7a2a" stroke-width="1.5" fill="none" marker-end="url(#v)"/>
<text x="347" y="216" text-anchor="middle" font-size="10" fill="#2a7a2a">capteurs</text>
<text x="330" y="292" text-anchor="middle" font-size="10" fill="#2a7a2a">I2C, nappe −X</text>
</svg><figcaption>Schéma de principe : puissance (noir), commande des ESC (rouge), mesures : BNO055 et capteurs de vitesse (vert). Les masses de l'alimentation, des ESC
et de l'ESP32 sont reliées.</figcaption></figure>"""
    lignes_b = []
    for rang, k in enumerate(K.ORDRE_ESC):
        b0 = 4 * rang + 1
        lignes_b += [[str(b0), f"ESC {k + 1}, signal (blanc)", "oui", f"GPIO {ESC_GPIO[k]}"],
                     [str(b0 + 1), f"ESC {k + 1}, + 5 V du BEC (rouge)", "<b>aucun fil</b>", "—"],
                     [str(b0 + 2), f"ESC {k + 1}, masse (noir)", "oui" if rang == 0 else "facultatif", "GND"]]
        if rang < 3:
            lignes_b.append([str(b0 + 3), "vide", "—", "—"])
    bornier = tableau(["Broche", "Dessus : prise de l'ESC", "Dessous : fil Dupont", "Breadboard"], lignes_b)
    origine = {"moteur": "mesurée (18 cm)", "alim": "mesurée (13 cm)", "principal": "sur le dispositif seulement, il continue vers la table",
               "commande": "relevée sur le modèle (câble existant : ≈ 25 cm)", "capteur": "relevée sur le modèle (fils Dupont à couper ou à choisir)",
               "bno": "sur le dispositif seulement, il continue vers la table", "nappe": "sur le dispositif seulement, elle continue vers la table"}
    noms_c = {"moteur": "Fils moteur {} (3 × 16 AWG)", "alim": "Alimentation de l'ESC {} (2 × 16 AWG), jusqu'à la carte",
              "commande": "Câble de commande de l'ESC {} (3 fils)", "capteur": "Câble du capteur {} (3 fils Dupont)",
              "principal": "Câble d'alimentation de la carte", "bno": "Câble du BNO055 (4 fils Dupont)", "nappe": "Nappe des signaux (11 fils Dupont)"}
    lignes_k = []
    for cle in ("moteur", "alim", "principal", "commande", "capteur", "bno", "nappe"):
        for nom in [n for n in LC if n.rstrip("1234") == cle]:
            lignes_k.append([noms_c[cle].format(nom[len(cle):]), f(DC[nom], 1), f(LC[nom], 0), origine[cle]])
    cables_3d = tableau(["Câble", "Ø (mm)", "Longueur (mm)", "Longueur"], lignes_k, num=(1, 2))
    lignes_c = []
    for k in range(4):
        b0 = 4 * k + 1
        lignes_c += [[str(b0), f"Capteur {k + 1}, VCC", "pont des 4 broches V" + (" ; <b>un fil</b>" if k == 0 else ""), "3V3 de l'ESP32" if k == 0 else "—"],
                     [str(b0 + 1), f"Capteur {k + 1}, GND", "pont des 4 broches G" + (" ; <b>un fil</b>" if k == 0 else ""), "GND" if k == 0 else "—"],
                     [str(b0 + 2), f"Capteur {k + 1}, D0", "oui", f"GPIO {CAPTEUR_GPIO[k]}"]]
        if k < 3:
            lignes_c.append([str(b0 + 3), "vide", "—", "—"])
    capteurs = tableau(["Broche", "Dessus : fil du capteur", "Dessous", "Breadboard"], lignes_c)
    bno = tableau(["Broche du BNO055", "Fil", "Breadboard"], [
        ["VIN", "Dupont femelle-mâle", "3V3 de l'ESP32"], ["GND", "Dupont femelle-mâle", "GND"],
        ["SCL", "Dupont femelle-mâle", "GPIO 22"], ["SDA", "Dupont femelle-mâle", "GPIO 21"],
        ["ADD, INT, BOOT, RST", "aucun", "Adresse 0x28 ou 0x29 selon la carte : faire un scan I2C"]])
    alim = tableau(["Liaison", "De", "Vers", "Remarque"], [
        ["Puissance", "Alimentation de labo, + et −", "Entrée XT60 mâle de la carte de distribution (câble par la face +X)", "12,0 V ; limite de courant au maximum ; le câble finit par une XT60 femelle"],
        ["Distribution", "Carte de distribution XT60 1 vers 4", "XT60 des 4 ESC", "Carte Jonronfey ; vérifier la LED de polarité avant de brancher les ESC"],
        ["Moteurs", "ESC (3 fils bleus)", "A2212", "Soudés, inchangés ; sens inversé par le firmware"],
        ["Logique", "Alimentation de labo", "LM2596 (bornier IN)", "Ou ESP32 sur l'USB seul"],
        ["5 V", "LM2596 (bornier OUT, réglé à 5,0 V)", "ESP32 VIN et GND", ""],
        ["Masse commune", "Breadboard GND", "Broche 3 du bornier (masse des ESC)", "Une seule suffit : la carte de distribution relie déjà les masses des ESC"]])
    S.append(("7. Électronique, câblage et alimentation", "".join(el) + "<h3>Schéma de principe</h3>" + schema
              + "<h3>Bornier RW-11, rangée intérieure : ESC</h3><p>Broche 1 du côté +Y (côté des moteurs 1 et 2). Dans chaque groupe, le fil blanc (signal) de la prise va vers +Y. "
              "ESC 1 : moteur à 45° (+X, +Y) ; ESC 2 : 135° ; ESC 3 : 225° ; ESC 4 : 315° ; le numéro du moteur est gravé en points dans chaque coin du plateau. "
              "<b>L'ordre des prises suit l'arrivée des câbles sur la bordure, pour qu'aucun ne croise : ESC 2, ESC 3, ESC 4, ESC 1</b>, de +Y vers −Y.</p>" + bornier
              + "<h3>Bornier RW-11, rangée extérieure : capteurs de vitesse</h3><p>Même sens (broche 1 côté +Y) ; capteur k sur la roue k. "
              "Sous la lèvre, les broches V sont reliées entre elles par un fil nu soudé, de même pour les broches G : deux fils seulement vont à la "
              "breadboard pour l'alimentation des 4 capteurs. <b>VCC en 3,3 V, jamais en 5 V.</b></p>" + capteurs
              + "<h3>BNO055</h3>" + bno + "<h3>Alimentation et masses</h3>" + alim
              + "<h3>Le câblage dessiné dans SolidWorks</h3><p>Chaque câble est un tube à son diamètre réel, coudes arrondis (rayon d'au moins "
              f"{f(R_COURBURE, 0)} mm pour le 16 AWG en faisceau), dans l'assemblage Dispositif : pièces RW-50 à RW-56, une par famille, une couleur "
              "par famille. Le fil silicone 16 AWG 200 °C (252 brins de 0,08 mm) fait 3,0 mm de diamètre extérieur ; 3 fils moteur liés font "
              f"une enveloppe de {f(D_MOTEUR, 1)} mm, 2 fils d'alimentation {f(D_ALIM, 1)} mm. Les longueurs mesurées sont respectées au "
              "millimètre : le mou des 18 cm est une boucle contre la face intérieure du corps ; les 13 cm montent en diagonale jusqu'à la carte de distribution. "
              "Aucun câble n'en traverse un autre ni ne traverse une pièce (section 10).</p>"
              f"<figure><img src='{url(os.path.join(RENDUS, 'cablage.png'))}' style='width:120mm'><figcaption>Le câblage seul, avec les appareils "
              "qu'il relie : ESC (violet), carte de distribution XT60 et ses fiches (noir, jaune), BNO055, bornier, cartes TCRT5000 (vert sombre).</figcaption></figure>"
              + cables_3d))

    # 8. Montage du câblage et réglages
    usages = ["Presque neutre : équilibrage statique, essais des roues", "Premiers essais en boucle fermée", "Essais standard",
              "Essais exigeants", "Limite : roues les plus sollicitées"]
    reg = tableau(["Pivot", "h", "Usage conseillé"],
                  [[f"{mm(eq['zp'])} (rangée +24, paliers remontés de {f(eq['zp'] - max(Z_PIVOTS), 0)} mm)", f"{f(eq['h'])} mm",
                    "Équilibré : le dispositif reste où on le pose. Équilibrage statique, essais des roues"]]
                  + [[f"{mm(p['zp'])} (rangée)", f"{f(p['h'])} mm", u] for p, u in zip(piv, usages)])
    lignes_eq = []
    for k, c in enumerate(FACES_EQ):
        nb = EQ_ECROUS[k]
        if nb:
            debut = EQ_POSITIONS[k] - R_PAROI - nb * EQ_ECROU[1] / 2
            lignes_eq.append([f"Tige {c}", str(nb), f"{f(EQ_POSITIONS[k], 1)} mm", f"{f(debut, 1)} mm"])
        else:
            lignes_eq.append([f"Tige {c}", "0", "pas de paquet", "écrous de serrage seulement"])
    tab_eq = tableau(["Tige", "Écrous de réglage", "Milieu du paquet, depuis le centre du corps",
                      "Face intérieure du paquet, depuis la paroi (contrainte SolidWorks « Équilibrage … »)"], lignes_eq)
    S.append(("8. Montage du câblage et réglages", f"""
<h3>Montage, dans l'ordre</h3>
<ol>
<li><b>Corps.</b> Poser les {n_ins_corps} inserts M3 à chaud. Visser les 4 platines sur les faces diagonales (2 vis M3 × 8 chacune).</li>
<li><b>Moteurs.</b> Visser l'A2212 sur sa platine, sortie des fils du côté de la fente : 4 vis M3 × 14 à travers la croix, la
platine et la paroi, écrous Nylstop à l'intérieur du corps. Les fils moteur sont soudés au moteur et à l'ESC : rien n'est à
enfiler. Plateau retiré, poser les fils dans la fente du corps par le dessus, l'ESC passant par-dessus le bord, à l'intérieur.</li>
<li><b>Boucle des fils moteur.</b> Dans le corps, former la boucle contre la face diagonale, sous la fente, et la lier sur
elle-même par un collier. Remonter les fils dans le coin du corps, ESC au-dessus. <b>Rien ne doit traverser le centre du
corps</b> : c'est la place du cardan.</li>
<li>Monter les disques (vis M6 freinées), puis les carters (2 M3 × 10 chacun).</li>
<li><b>Tiges d'équilibrage.</b> Visser un écrou sur chaque tige, à 1,5 mm du bout. Plateau retiré, passer la tige dans son trou
de l'intérieur vers l'extérieur, écrou contre la face intérieure, et la serrer par un second écrou contre la face extérieure.
Visser ensuite les écrous de réglage (tableau de l'équilibrage ci-dessous) et serrer chaque paquet sur lui-même.</li>
<li><b>Capteurs de vitesse.</b> Visser la carte TCRT5000 sous le bras de la potence (M3 × 8 et écrou), capteur vers le disque, puis
la potence sur le bossage du haut du carter (2 M3 × 8, lumières au milieu). Tourner le disque à la main : rien ne doit toucher.</li>
<li><b>Plateau.</b> Poser le plateau sur le corps en faisant passer les fils de chaque ESC dans l'encoche de son coin ; 3 vis
M3 × 10, la quatrième, en −X, est la vis M3 × 16 du bornier. Poser chaque ESC debout entre ses joues, bout moteur vers le coin de
son moteur, et le serrer par 2 colliers.</li>
<li><b>Carte de distribution.</b> Visser les 4 entretoises M3 × 35 sous le plateau (M3 × 8 par-dessous), après avoir collé le
BNO055 (étape suivante). Poser la carte, entrée vers +X, et la visser (4 M3 × 6). Brancher chaque ESC sur sa sortie (de +X vers −X :
ESC 2, ESC 1, ESC 3, ESC 4), le fil monté en diagonale au-dessus des ESC. Brancher le câble d'alimentation sur l'entrée et le faire
descendre le long de la face +X. <b>Avant de brancher les ESC</b>, mettre l'alimentation sous tension seule et vérifier la LED de
polarité.</li>
<li><b>BNO055 et bornier.</b> Coller le BNO055 dans son logement (adhésif mousse), barrette vers −X, inscriptions vers le haut.
Coller les 2 barrettes dans le bornier ; sous la rangée extérieure, souder un fil nu qui relie les 4 broches V, un autre pour les
4 broches G. Poser le bornier (2 pions, vis M3 × 16).</li>
<li><b>Câbles de signal.</b> Coucher les câbles de commande et les câbles des capteurs sur la bordure du plateau, entre les ESC et
le bord, tenus par des colliers dans les passe-colliers, et les brancher sur le bornier (tableaux de la section 7).</li>
<li><b>Nappe des signaux.</b> Fils Dupont femelle-mâle sous le bornier (rangée des ESC : 4 signaux et 1 masse ; rangée des capteurs :
4 sorties, le 3,3 V et la masse) et sur la barrette du BNO055 (4 fils). Deux paquets, sans les torsader ensemble : l'I2C d'un côté
(SDA torsadé avec GND, SCL avec VIN), le reste de l'autre. Les faire descendre le long de la face −X du corps, les attacher par un
collier dans les 2 fentes à z −20, laisser une boucle libre d'environ 10 cm, les attacher dans le tunnel −X du moyeu du socle, puis
jusqu'à la breadboard.</li>
<li><b>Câble d'alimentation.</b> De l'entrée de la carte, il passe par-dessus l'ESC +X et descend le long de la face +X, puis même chemin (fentes à z −20, boucle, tunnel +X du socle)
jusqu'à l'alimentation de labo.</li>
<li><b>Contrôle.</b> Incliner le dispositif à la main jusqu'aux butées dans toutes les directions : les câbles ne doivent ni tirer,
ni toucher un disque, et les boucles ne doivent pas se tendre.</li>
</ol>
<h3>Équilibrage statique</h3>
<p>Un décalage latéral du centre de gravité de 1 mm crée un couple permanent de ≈ {f(couple_mm, 1)} N·mm. Les roues ne peuvent le
compenser qu'en accélérant sans fin, jusqu'à saturer. Le modèle est équilibré par les tiges et les écrous, mais le câblage réel
ne sera pas exactement celui du modèle : le réglage se finit sur le banc. Les tiges ±X règlent le tangage (centre de gravité
selon X), les tiges ±Y le roulis (selon Y) ; la hauteur du pivot se règle dans les lumières des paliers.</p>
<figure><img src='{url(os.path.join(RENDUS, 'equilibrage.png'))}' style='width:110mm'>
<figcaption>Le corps sans son plateau : paliers de tangage à lumières (orange), 4 tiges d'équilibrage M6 (gris) en moulin sur
les faces ±X et ±Y, écrous de serrage contre la paroi et paquets d'écrous de réglage (jaune) dans le réglage du modèle.</figcaption></figure>
<p><b>Réglage du modèle</b> (point de départ, pivot à {mm(eq['zp'])}) :</p>
{tab_eq}
<p><b>Méthode sur le banc.</b> Pivot à {mm(eq['zp'])}, écrous au réglage du modèle.</p>
<ol>
<li>Tangage bloqué (goupille), roulis libre : si le dispositif penche vers +Y, éloigner du corps le paquet de la tige −Y ou
rapprocher celui de la tige +Y, et inversement. Un écrou déplacé de 10 mm déplace le centre de gravité d'environ
{f(MASSES['ecrou_m6'] * 10 / (B['masse'] * 1000), 3)} mm ; s'il faut plus, ajouter ou retirer un écrou.</li>
<li>Roulis bloqué, tangage libre : même chose avec les tiges ±X.</li>
<li>Deux axes libres, régler la hauteur : si le dispositif revient à plat en oscillant, le centre de gravité est sous le pivot,
descendre les paliers ; s'il tombe franchement vers un côté, il est au-dessus, monter les paliers (de la même valeur des deux
côtés). Recommencer 1 et 2 si besoin, jusqu'à ce qu'il reste à peu près où on le pose dans toutes les directions.</li>
<li>Serrer les paquets d'écrous sur eux-mêmes et les vis des paliers. La Perception du jumeau numérique estime le déséquilibre restant
en mm : s'en servir pour finir le réglage, puis faire entrer la vitesse des roues dans la commande pour qu'elle trouve seule
l'angle d'équilibre réel.</li>
</ol>
<p>Dans SolidWorks (Dispositif), chaque paquet de réglage est placé par une seule contrainte de distance nommée « Équilibrage +X :
position du paquet de 3 écrous (distance à la paroi) », et de même pour +Y et −Y ; sa valeur est la dernière colonne du tableau. En changer la valeur
déplace tout le paquet, les écrous suivants s'appuyant sur le premier. Pour ajouter ou retirer un écrou, insérer ou supprimer un
RW-41 du paquet (coaxial à la tige, en contact avec l'écrou précédent).</p>
<h3>Changer la hauteur du centre de rotation</h3>
<p>Desserrer les 2 vis de chaque palier. Pour changer de rangée, les revisser dans la paire d'inserts voulue ; pour le réglage
fin, faire glisser le palier dans ses lumières (±{f(PALIER_REGLAGE, 0)} mm), à la même hauteur des deux côtés, puis serrer. La
tige reste dans la fourche : seul le dispositif monte ou descend, le poteau ne bouge pas. Dans SolidWorks, modifier les deux
contraintes « Hauteur du pivot de tangage, palier +Y » et « … palier −Y » (même valeur, hauteur de l'axe au-dessus du plan des
axes des roues) ; leur nom rappelle la plage de la rangée utilisée.</p>
{reg}
<h3>Bloquer ou libérer un axe</h3>
<p>Mettre le dispositif à plat et introduire la goupille de blocage dans le trou du bas : à travers le bras de la fourche dans le
croisillon pour le roulis (accès par la fenêtre de la face ±X du corps, en écartant les câbles), à travers le collier dans le
palier pour le tangage. Les goupilles de butée restent en place : elles limitent chaque axe à ±20°.</p>
<h3>Mise en service, dans l'ordre</h3>
<ul>
<li>Alimentation de labo : 12,0 V, limite de courant au maximum, sortie coupée pendant le câblage.</li>
<li>LM2596 réglé à 5,0 V avant de le relier à l'ESP32, ou ESP32 sur l'USB du PC seul. Vérifier qu'aucun fil n'est branché sous les broches + du bornier.</li>
<li>Disques démontés : vérifier l'armement des ESC (1500 µs = arrêt) et le sens de chaque moteur. Pour inverser un moteur sans
toucher aux soudures, inverser le signe de sa commande dans le firmware.</li>
<li>Scan I2C, mode IMUPLUS, correspondance des axes du BNO055 (flèche du plateau = +X).</li>
<li>Remonter les disques, vis M6 freinées. Limiter la commande à 1375 à 1625 µs dans le firmware (section 9).</li>
<li>Capteurs de vitesse : régler le seuil de chaque TCRT5000 (potentiomètre) en tournant le disque à la main, la LED témoin doit
changer à chaque rayon ; puis, à vitesse constante, comparer la vitesse mesurée à la vitesse attendue (environ KV × tension ×
part de la commande).</li>
<li>Équilibrage statique au pivot {mm(eq['zp'])} (tiges et écrous, puis hauteur dans les lumières).</li>
<li>Tangage bloqué, pivot {mm(piv[1]['zp'])} : vérifier qu'une accélération de chaque roue fait tourner le dispositif dans le sens prévu (signes de
la matrice d'allocation à 45°), puis régler la boucle de roulis seule.</li>
<li>Libérer le tangage, régler les deux axes, puis descendre le pivot pour durcir l'essai.</li>
</ul>"""))

    # 9. Sécurité
    lignes_v = [[f"{1500 - v['offset']} à {1500 + v['offset']} µs", f(v["n"], 0), f(v["F"], 0), f(v["tau"], 1), f(v["E"], 1),
                 f(v["securite"], 1)] for v in B["vitesses"]]
    S.append(("9. Sécurité : vitesse des disques et alimentation", f"""
<p>Chaque vis M6 d'équilibrage (8 g avec son écrou, au rayon de 55 mm) est retenue par le bord du disque, où il ne reste que
1,5 mm de PLA entre le trou Ø7 et l'extérieur (cisaillement sur 2 × 1,5 × 4,5 mm²). L'effort centrifuge croît avec le carré de la
vitesse. Avec une résistance prudente du PLA imprimé de 20 MPa au cisaillement :</p>
{tableau(["Commande", "Vitesse à vide (tr/min)", "Effort par vis (N)", "Cisaillement (MPa)", "Énergie d'une vis éjectée (J)", "Sécurité"], lignes_v, num=range(1, 6))}
<div class=alerte><b>À retenir.</b> Les bornes du firmware du banc à un moteur (1300 à 1700 µs) donnent environ
{f(v200['n'], 0)} tr/min et une sécurité de seulement {f(v200['securite'], 1)}. <b>Limiter la commande à 1375 à 1625 µs</b> (environ
{f(v125['n'], 0)} tr/min, sécurité {f(v125['securite'], 1)}) tant que les disques ne sont pas modifiés. Au-delà, il faudrait éloigner les trous du
bord, passer à des masses plus légères ou à un disque en aluminium.</div>
<div class=note><b>Alimentation de labo et freinage.</b> Quand un ESC freine son disque, l'énergie du disque (jusqu'à
{f(B['energie_roue'], 0)} J à {f(v125['n'], 0)} tr/min) peut repartir vers l'alimentation. Une alimentation de labo ne sait pas
l'absorber : sa tension monte, et elle peut se mettre en sécurité ou souffrir. En équilibre, une roue qui freine pendant qu'une autre
accélère échange l'énergie par le faisceau et le risque reste faible ; il devient réel quand on arrête les 4 disques en même temps.
La vraie parade est logicielle : arrêter les disques par une rampe lente dans le firmware (l'énergie se perd alors dans le moteur et
l'ESC) et ne jamais freiner les 4 disques ensemble ; surveiller la tension affichée par l'alimentation. Un condensateur de 2 200 µF
sur l'entrée de la carte de distribution n'absorbe que ≈ {f(e_cond, 2)} J en montant de 12 à 16 V, moins de 1 % de l'énergie d'un disque : il amortit les pointes
de tension, il ne remplace pas la rampe. La batterie de la phase suivante absorbe ce freinage sans difficulté.</div>
<ul>
<li>Porter des lunettes de protection et ne jamais se placer dans le plan d'un disque en rotation.</li>
<li>Freiner les vis M6 (écrous Nylstop ou frein-filet) et vérifier leur serrage avant chaque séance.</li>
<li>Couper la sortie de l'alimentation, ou débrancher la XT60 du câble d'alimentation, avant toute intervention sur le dispositif.</li>
<li>PLA : surveiller la température des moteurs (au-delà de 50 °C, les platines PLA peuvent se déformer).</li>
<li>Phase batterie : charger la LiPo avec un chargeur équilibreur, dans un sac ignifuge, jamais sans surveillance ; ne pas descendre sous 3,3 V par élément ; fusible sur le + de la batterie, au plus près d'elle.</li>
<li>Arrêt d'urgence : garder la main sur la sortie de l'alimentation de labo, ou ajouter un coupe-circuit sur le câble d'alimentation (option du carnet).</li>
</ul>"""))

    # 10. Vérifications
    S.append(("10. Vérifications faites en CAO", tableau(["Contrôle", "Résultat"], [
        [f"Interférences au repos (build123d, pivot en haut de course {mm(max(Z_PIVOTS) + PALIER_REGLAGE)}, équilibré {mm(eq['zp'])} et en bas de course {mm(min(Z_PIVOTS) - PALIER_REGLAGE)}), tous les câbles, tiges et écrous d'équilibrage compris, disques et vis d'équilibrage des disques pris par leur enveloppe en rotation", "Aucune"],
        ["Jeux autour des tiges d'équilibrage et de leurs écrous (distance exacte entre solides, sur toute la course des paliers)", "2,2 mm aux paliers (pivot au plus bas), 2,3 mm entre le bout des tiges et les carters (fixes l'un par rapport à l'autre), 4,8 mm aux colliers, 9,2 mm aux disques en rotation"],
        ["Câbles entre eux (distance entre axes moins les deux rayons, sur 300 points par câble)", "Aucun câble n'en traverse un autre ; plus petit écart 0,2 mm (deux câbles qui se longent) ; rayon de courbure du 16 AWG : 9 mm, 7 mm à la sortie des fils d'alimentation"],
        [f"Balayage du cardan : roulis et tangage de −20° à +20° par pas de 10°, coins combinés compris, câbles et tiges d'équilibrage compris, contre fourche et poteau, pour les 5 rangées, le pivot équilibré et les deux bouts des lumières ({mm(min(Z_PIVOTS) - PALIER_REGLAGE)} à {mm(max(Z_PIVOTS) + PALIER_REGLAGE)})", f"Aucun contact ; le socle reste à {f(-Z_SOCLE - 141.9, 0)} mm sous le point le plus bas au pivot équilibré, 11 mm au haut de la course"],
        ["Import des pièces dans SolidWorks", "Chaque pièce imprimée ou du commerce est un seul corps solide (un import raté, en surfaces, arrête la construction) ; les 7 pièces de câblage ont un corps par câble"],
        ["Assemblages SolidWorks rouverts", SW_LIAISONS],
        ["Détection d'interférences de SolidWorks (vrais modèles A2212 et disques)", SW_INTERFERENCES],
        ["Centre de gravité (modèle de ce document, partie mobile)", f"x {f(B['G'][0], 2)}, y {f(B['G'][1], 2)} mm : sur les axes ; {f(eq['h'], 1)} mm au-dessus du pivot équilibré. Le jumeau numérique, qui prend le moteur et le disque relevés dans SolidWorks, le place à 0,00 mm du pivot : l'écart donne l'ordre de grandeur de ce qui reste à régler sur le banc"]])))

    # 11. Points ouverts
    S.append(("11. Points ouverts", tableau(["Point", "Action"], [
        ["<b>Largeur et épaisseur de l'ESC</b>, et côté de sortie de ses fils (moteur d'un bout, alimentation et commande de l'autre ?)", f"À mesurer <b>avant d'imprimer le plateau</b> : les joues sont écartées pour {f(ESC[2], 0)} mm d'épaisseur, la hauteur prise est de {f(ESC[1], 0)} mm. Si les trois câbles sortent du même bout, le cheminement change"],
        ["<b>Cotes de la carte de distribution XT60</b> : longueur, largeur, entraxe des trous, position des 4 sorties et de l'entrée", "Les mesurer à réception : le modèle part de l'annonce (74 × 32 mm) et de la photo du vendeur"],
        ["Longueur du câble de commande des ESC", "Mesurer : dessinés à 25 cm au plus"],
        ["Cotes de la carte TCRT5000 et du GY-BNO055, position et sens des broches de la carte TCRT5000", "Mesurer ; la potence et le logement du BNO055 en dépendent"],
        ["Réponse du TCRT5000 sur le PLA du disque", "Essayer sur un disque avant de tout monter ; au besoin, adhésif aluminium ou blanc sur les rayons"],
        ["Nombre de moteurs A2212 et d'ESC disponibles ; courant maximal de l'alimentation de labo", "Vérifier avant de commander"],
        ["Distance entre le banc et la breadboard", "Rester sous 40 cm de fils (I2C à 100 kHz)"],
        ["Couple réel de l'A2212 et vitesse maximale du disque", "Mesurer sur le banc à un moteur avant les essais à deux axes"],
        ["Tenue des vis d'équilibrage du disque", "Limiter la commande à ±125 µs ; à terme, revoir le disque (trous plus loin du bord ou aluminium)"],
        ["Brochage du firmware", f"ESC sur {', '.join(map(str, ESC_GPIO))} ; capteurs sur {', '.join(map(str, CAPTEUR_GPIO))} ; garder 21 et 22 pour l'I2C, à 100 kHz"],
        ["Mode du BNO055", "Passer de NDOF à IMUPLUS ; caler la boucle sur 100 Hz ou lire le gyromètre brut"],
        ["Masse et centre de gravité réels", "Peser le dispositif câblé ; équilibrage statique par les écrous et les lumières des paliers (section 8)"],
        ["Moteurs chauds sur platines PLA", "Surveiller ; platines en PETG si les essais sont longs"]])))

    # Annexes
    nom_tab = [["RW-01", "1", "Corps central", "Impression PLA"], ["RW-02", "4", "Platine moteur", "Impression PLA (PETG mieux)"], ["RW-03", "4", "Carter de disque", "Impression PLA (PETG mieux)"],
               ["RW-04", "2", "Palier de tangage", "Impression PLA"], ["RW-05", "2", "Collier de blocage", "Impression PLA 100 %"], ["RW-06", "1", "Croisillon", "Impression PLA 100 %"],
               ["RW-07", "1", "Fourche de roulis", "Impression PLA"], ["RW-08", "1", "Plateau supérieur", "Impression PLA"],
               ["RW-09", "1", "Berceau de batterie", "Phase batterie, plus tard"], ["RW-10", "1", "Socle", "Impression PLA (ou planche)"],
               ["RW-11", "1", "Bornier à deux rangées", "Impression PLA"], ["RW-12", "4", "Potence du capteur de vitesse", "Impression PLA"],
               ["RW-20", "4", "Roulement 625-2Z", "Commerce"], ["RW-21", "1", f"Tige Ø5 h6 × {f(TIGE, 0)}", "Commerce"],
               ["RW-22", "2", "Vis épaulée Ø5 × 10, M4", "Commerce"], ["RW-23", "2", "Entretoise Ø8 / Ø5 × 4", "Impression PLA 100 %"], ["RW-24", "4", "Goupille Ø3 × 16", "Commerce"],
               ["RW-25", "1", f"Tube alu Ø12 × 1, L {f(TUBE[2], 0)}", "Commerce"], ["RW-26", "4", "Entretoise hexagonale M3 × 35 F/F", "Commerce"],
               ["RW-30", "1", "LiPo 3S 2200 mAh 40C", "Phase batterie"], ["RW-31", "4", "ESC 30 A 2-4S, BEC 5 V / 2 A", "Disponibles (nombre à vérifier)"],
               ["RW-32", "1", "GY-BNO055", "Disponible"], ["RW-33", "4", "Carte TCRT5000 (capteur de vitesse)", "Commerce"],
               ["RW-34", "1", "Embase XT60 femelle", "Phase batterie"],
               ["RW-35", "1", "Interrupteur KCD1", "Phase batterie"], ["RW-36", "2", "Barrette mâle 1 × 15, broches longues", "Commerce"],
               ["RW-37", "1", "Carte de distribution XT60 1 vers 4 (Jonronfey)", "Achetée"], ["RW-38", "4", "Fiche XT60 d'un ESC, branchée", "Câblage existant"],
               ["RW-39", "1", "Fiche XT60 du câble d'alimentation", "Câblage existant"],
               ["RW-40", "4", f"Tige d'équilibrage, tige filetée M6 × {f(EQ_TIGE[1], 0)}", "Commerce (tige de 1 m à couper)"],
               ["RW-41", str(sum(EQ_ECROUS) + 2 * len(EQ_FACES)), "Écrou hexagonal M6 (serrage et réglage de l'équilibrage)", "Commerce (prévoir une réserve)"],
               ["RW-50", "1", "Fils moteur, 3 × 16 AWG, 180 mm (4 faisceaux)", "Câblage existant"], ["RW-51", "1", "Fils d'alimentation des ESC, 2 × 16 AWG, 130 mm (4 paires)", "Câblage existant"],
               ["RW-52", "1", "Câble d'alimentation de la carte", "Câblage existant"], ["RW-53", "1", "Câbles de commande des ESC (4)", "Câblage existant"],
               ["RW-54", "1", "Câbles des capteurs de vitesse (4)", "Commerce (fils Dupont)"], ["RW-55", "1", "Câble du BNO055", "Commerce (fils Dupont)"],
               ["RW-56", "1", "Nappe des signaux vers la breadboard", "Commerce (fils Dupont)"],
               ["A2212", "4", "Moteur A2212 1400 KV", "Disponibles (à vérifier)"], ["Disque", "4", "Disque Ø120 et 4 vis M6", "Existant"],
               ["Table", "1", "ESP32 DevKit V1 et breadboard", "Disponible"], ["Table", "1", "Régulateur LM2596 à afficheur", "Disponible"],
               ["Table", "1", "Alimentation de labo", "Disponible"]]
    S.append(("Annexe A. Nomenclature", tableau(["Rep.", "Nb", "Désignation", "Origine"], nom_tab)))
    S.append(("Annexe B. Fichiers et régénération", """
<p>Dossier du banc (<b>Banc_stabilisation</b>) : assemblages Banc_stabilisation, Dispositif et Module_roue ; pièces RW-xx ;
A2212.SLDPRT ; STEP des pièces dans cao/ ; rendus/ ; sources/ ; README.md. Le fichier d'origine disque_vis est référencé sans
être modifié. Les pièces de la phase batterie (RW-09, RW-30, RW-34, RW-35) sont créées mais pas montées.</p>
<p>Toutes les cotes viennent de <b>sources/rw_params.py</b>. Pour régénérer :</p>
<ul><li><b>rw_pieces.py</b> (Python avec build123d) : STEP de toutes les pièces ; <b>rw_cables.py</b> : cheminement, longueurs et STEP des câbles ;</li>
<li><b>rw_verif.py</b> : interférences, balayage du cardan, centre de gravité, hauteur du socle ;</li>
<li><b>rw_calculs.py</b> : calculs de cette documentation ;</li>
<li><b>rw_sw.py</b> (Python système avec pywin32, SolidWorks fermé) : pièces et assemblages contraints ;</li>
<li><b>verif_liaisons.py</b> et <b>rw_interferences.py</b> : contrôles dans SolidWorks ;</li>
<li><b>rw_rendus.py</b> : vues d'ensemble et gros plans ; <b>rw_documents.py</b> : les deux PDF.</li></ul>"""))
    S.append(("Annexe C. Sources", """<ul>
<li>Dossier du projet : DOC/decisions-techniques.md (A2212, couple requis), crystof/222c434c_a2212-brushless-motor.pdf, Dimension .pdf, modèle moteur_A2212 (KV 1400), TP1 (inertie du disque) ; photos du câblage existant (28/10/2026).</li>
<li>A2212 1000 KV, courant maxi et plage 2 à 3S : <a href='https://ca.robotshop.com/products/e-s-motor-xxd-a2212-brushless-motor-160w-mounting-base-kits-kv-1000'>RobotShop</a>.</li>
<li>BNO055 : <a href='https://components101.com/sensors/bno055-sensor-pinout-datasheet-equivalent-configuration-specs'>components101</a>, <a href='https://sigmanortec.ro/en/absolute-orientation-sensor-module-9-axes-gy-bno055-iic-serial-3-5v'>Sigmanortec (GY-BNO055)</a>.</li>
<li>Roulements 625ZZ : <a href='https://www.olimex.com/Products/Robot-CNC-Parts/Bearings/625ZZ/'>Olimex</a>.</li>
<li>TCRT5000 : fiche Vishay (distance de lecture, courant de la LED) ; ESP32 : fiche et errata Espressif (entrées 34 à 39, GPIO 36 et 39).</li>
<li>LiPo 3S 2200 mAh : <a href='https://hobbyking.com/fr_fr/turnigy-2200mah-3s-40c-lipo-pack-w-xt60.html'>HobbyKing</a>, <a href='https://www.rcteam.com/en/products/konect-lipo-11-1v-2200mah-35c-xt60-kn-lp3s2200'>RCteam</a>.</li>
<li>Inserts à chaud : <a href='https://www.prusa3d.com/fr/produit/inserts-filetes-m3-standard-100-pcs/'>Prusa</a> (température de pose).</li>
<li>Tube aluminium 12 × 1 : <a href='https://www.bricodepot.fr/p/3232630508756/tube-rond-aluminium-brut-12-x-1-mm-1-m-argent'>Brico Dépôt</a>.</li></ul>
<p>Prix et caractéristiques relevés le 28/10/2026, à vérifier au moment de la commande.</p>"""))
    return garde, S


# ================================================================ DOCUMENT 2 : CARNET DE COMMANDES
# (catégorie, article, spécification, quantité à commander, utilisé, prix unitaire indicatif, moins cher, alternative, statut)
# statut : "base" à acheter pour le banc ; "option" ; "batterie" phase batterie ; "stock" probablement déjà disponible
# prix « estimé » : ordre de grandeur, non relevé chez un fournisseur
ACHATS = [
    ("Mécanique", "Roulements 625-2Z", "5 × 16 × 5 mm, flasques métal (2Z / ZZ), lot de 10", 1, "4", 6.00, "AliExpress, eBay (5 à 9 € le lot)", "Olimex (0,63 € pièce), 3DJake", "base"),
    ("Mécanique", "Axe linéaire Ø5 h6", "Acier chromé trempé, 200 mm (longueur standard, sans coupe)", 1, "1", 4.00, "AliExpress « axe linéaire 5 mm »", "eBay, Ooznest (coupe à mesure)", "base"),
    ("Mécanique", "Vis épaulées Ø5 × 10, M4", "ISO 7379, inox ou acier, épaulement Ø5 × 10, filetage M4", 2, "2", 3.00, "AliExpress « vis épaulée M4 5 mm »", "eBay (vendeurs allemands), Lemu", "base"),
    ("Mécanique", "Goupilles Ø3 × 16", "Goupilles cylindriques acier ou inox, lot de 20 à 50", 1, "4", 5.00, "AliExpress, Amazon", "Bambu Lab Store (D3 dowel pins, lot de 20)", "base"),
    ("Mécanique", "Tube aluminium Ø12 × 1", "Tube rond, 1 m, à couper à 136 mm", 1, "1", 6.09, "Brico Dépôt (6,09 €)", "Castorama, Bricomarché", "base"),
    ("Mécanique", "Inserts à chaud M3 × 5,7", "Laiton, lot de 100 (perçage Ø4)", 1, "43", 9.00, "AliExpress (environ 5 €)", "3DJake Ruthex, Prusa", "base"),
    ("Mécanique", "Inserts à chaud M4", "Laiton, lot de 50 (perçage Ø5,6)", 1, "2", 5.00, "AliExpress", "3DJake, Amazon", "base"),
    ("Visserie", "Assortiment vis CHC M3 inox", "6 à 20 mm avec écrous et écrous Nylstop (≥ 16 × M3 × 14, 12 × M3 × 8, 11 × M3 × 10, 12 × M3 × 12, 2 × M3 × 16 ; ≥ 30 écrous)", 1, "53", 12.00, "AliExpress, Amazon (coffret M3)", "Audiophonics (sachets de 10)", "base"),
    ("Visserie", "Vis sans tête M3 × 5", "Lot", 1, "3", 2.00, "AliExpress, Amazon", "Quincaillerie", "base"),
    ("Visserie", "Vis CHC M4 × 30 et écrous", "2 vis, 2 écrous", 2, "2", 0.75, "Quincaillerie", "Brico", "base"),
    ("Équilibrage", "Tige filetée M6, 1 m", "Acier zingué DIN 976, à couper en 4 tiges de 60 mm (prix estimé)", 1, "4 × 60 mm", 2.00, "Quincaillerie, Brico", "Goujons M6 × 60", "base"),
    ("Équilibrage", "Écrous hexagonaux M6", f"ISO 4032, sachet de 25 ({sum(EQ_ECROUS) + 2 * len(EQ_FACES)} dans le réglage du modèle, le reste en réserve) (prix estimé)", 1, str(sum(EQ_ECROUS) + 2 * len(EQ_FACES)), 3.00, "Quincaillerie, Brico", "AliExpress, Amazon", "base"),
    ("Capteurs", "Modules TCRT5000", "Capteur réflectif avec comparateur LM393 et sortie D0, lot de 5 (prix estimé)", 1, "4", 5.00, "AliExpress, Amazon « TCRT5000 module »", "Magasin d'électronique", "base"),
    ("Câblage", "Barrette mâle 2,54 mm à broches longues", "Simple rangée, broches d'environ 20 mm, 1 × 40 (2 morceaux de 15), lot (prix estimé)", 1, "30 broches", 3.00, "AliExpress, Amazon « long pin header 2.54 20 mm »", "Magasin d'électronique", "base"),
    ("Câblage", "Fils Dupont femelle-mâle 40 cm", "Lot de 40 (prix estimé)", 1, "15", 3.50, "AliExpress, Amazon", "Magasin d'électronique", "base"),
    ("Câblage", "Fils Dupont femelle-femelle 20 cm", "Lot de 40, capteurs vers le bornier (2 fils bout à bout pour les roues 1 et 4) (prix estimé)", 1, "20", 2.50, "AliExpress, Amazon", "Magasin d'électronique", "base"),
    ("Consommables", "Colliers de serrage 2,5 mm", "Lot de 100", 1, "≈ 40", 3.00, "AliExpress, Amazon", "Brico", "base"),
    ("Consommables", "Adhésif mousse double face", "Rouleau, pour le BNO055", 1, "1", 4.00, "Amazon", "Brico", "base"),
    ("Sécurité", "Lunettes de protection", "Pour tous les essais avec disques", 1, "1", 5.00, "Brico", "Amazon", "base"),
    ("Option", "Condensateur 1000 à 2200 µF, 25 V", "Électrolytique faible ESR, à souder sur l'entrée de la carte de distribution : amortit les pointes de tension, pas le freinage (prix estimé)", 1, "1", 2.00, "AliExpress, magasin d'électronique", "Amazon", "option"),
    ("Option", "Coupe-circuit pour le câble d'alimentation", "Interrupteur ou coupe-batterie 30 A au moins, à portée de main pendant les essais (prix estimé)", 1, "1", 8.00, "AliExpress, magasin de modélisme", "Amazon", "option"),
    ("Option", "Embout pour inserts à chaud", "Si le fer à souder n'en a pas", 1, "1", 17.95, "Filament2print (kit Mintion, 17,95 €)", "AliExpress (moins cher)", "option"),
    ("Batterie", "LiPo 3S 2200 mAh 40C", "Prise XT60, environ 105 × 34 × 24 mm", 1, "1", 24.99, "eBay SLS XTRON 40C (24,99 €)", "RCteam Konect 35C (24,90 €)", "batterie"),
    ("Batterie", "Chargeur équilibreur 2 à 3S", "SkyRC e3S ou équivalent", 1, "1", 18.20, "Megadron (18,20 €)", "Unmanned Tech, magasin de modélisme", "batterie"),
    ("Batterie", "Sac de charge ignifuge LiPo", "Taille moyenne", 1, "1", 10.00, "AliExpress, Amazon", "Magasin de modélisme", "batterie"),
    ("Mécanique", "Entretoises hexagonales M3 × 35 F/F", "Laiton, femelle-femelle, lot de 10 (carte de distribution) (prix estimé)", 1, "4", 4.00, "AliExpress", "Kit d'entretoises M3 (Amazon)", "base"),
    ("Batterie", "Embase XT60, interrupteur KCD1, sangle 20 mm", "Pour le berceau RW-09 ; l'interrupteur ne coupe que l'électronique", 1, "1", 8.00, "AliExpress", "Amazon", "batterie"),
    ("Batterie", "Fusible lame 30 A et porte-fusible", "Sur le + de la LiPo, au plus près d'elle (prix estimé)", 1, "1", 4.00, "Magasin auto, AliExpress", "Amazon", "batterie"),
    ("À vérifier", "Moteurs A2212 (même KV)", "4 nécessaires", 4, "4", 9.00, "AliExpress, RobotShop (8 à 12 €)", "", "stock"),
    ("À vérifier", "ESC 30 A bidirectionnels", "Prix pour 3 s'il n'y en a qu'un", 3, "4", 12.00, "AliExpress, eBay (9 à 15 €)", "RobotShop « Basic 30A ESC forward/reverse »", "stock"),
    ("À vérifier", "ESP32 DevKit V1 30 broches", "", 1, "1", 6.00, "AliExpress, Amazon", "", "stock"),
    ("À vérifier", "Module GY-BNO055", "", 1, "1", 14.00, "eBay (environ 14 €)", "AliExpress", "stock"),
    ("À vérifier", "PLA 1,75 mm", "≈ 0,9 kg utiles", 1, "0,9 kg", 27.46, "LDLC Bambu Lab PLA Basic (27,46 €/kg)", "Bambu Lab Store", "stock"),
]


def carnet():
    garde = (f"<div class=garde><h1>Carnet de commandes</h1><div class=sous>Banc de stabilisation à 4 roues de réaction</div>"
             f"<img src='{url(os.path.join(RENDUS, 'vue_iso.png'))}' style='width:105mm'>"
             f"<div class=meta>Projet Monowheel · {DATE} · version {VERSION}<br>Phase de test : câblage existant, ESP32 sur breadboard, "
             f"alimentation de labo<br>Prix indicatifs relevés le {DATE}, à vérifier au moment de commander</div></div>")
    tot = {}
    for a in ACHATS:
        tot[a[8]] = tot.get(a[8], 0) + a[3] * a[5]
    budget_a = tot["base"]
    budget_b = budget_a + tot["batterie"]
    budget_c = budget_b + tot["stock"] + tot["option"]
    S = []
    S.append(("1. Synthèse du budget", f"""
<p>Le banc reprend le matériel déjà disponible : moteurs, ESC et leur câblage, carte de distribution XT60 1 vers 4 (achetée), alimentation de labo, ESP32 sur breadboard,
BNO055, régulateur LM2596 à afficheur, imprimante et PLA. Toutes les pièces sur mesure s'impriment (section 3) ; le budget ne
couvre que les achats.</p>
{tableau(["Budget", "Contenu", "Total indicatif"], [
 ["A. Banc pour la phase de test", "Mécanique du cardan, visserie, inserts, barrette du bornier, fils Dupont, colliers, lunettes", euros(budget_a)],
 ["B. A + phase batterie (plus tard)", "LiPo 3S 2200 mAh, chargeur équilibreur, sac de charge, petites pièces du berceau", euros(budget_b)],
 ["C. Tout acheter", "B + 4 moteurs, 3 ESC, ESP32, BNO055, 1 kg de PLA, condensateur, coupe-circuit et embout d'inserts", euros(budget_c)]], num=(2,))}
<div class=note>Les prix les plus bas sont sur AliExpress (livraison de 1 à 3 semaines) ; Amazon et les magasins français coûtent un peu
plus mais livrent en quelques jours. Lancer la commande AliExpress en premier, puisque c'est elle qui fixe le délai, et imprimer
pendant l'attente.</div>
<h3>Matériel supposé déjà disponible (à cocher)</h3>
{tableau(["", "Article", "À défaut"], [
 ["<span class=coche>☐</span>", "4 moteurs A2212 identiques (même KV), fils soudés à leur ESC", "≈ 9 € pièce"],
 ["<span class=coche>☐</span>", "4 ESC 30 A 2-4S avec leur XT60 et leur câble de commande", "≈ 12 € pièce"],
 ["<span class=coche>☑</span>", "Carte de distribution XT60 1 vers 4 Jonronfey (achetée)", "12,50 € (Amazon)"],
 ["<span class=coche>☐</span>", "Alimentation de labo (au moins 10 A conseillés)", "—"],
 ["<span class=coche>☐</span>", "ESP32 DevKit V1 30 broches et breadboard", "≈ 6 € et ≈ 4 €"],
 ["<span class=coche>☐</span>", "Module GY-BNO055 avec sa barrette soudée", "≈ 14 €"],
 ["<span class=coche>☐</span>", "Régulateur LM2596 à afficheur", "≈ 4 €"],
 ["<span class=coche>☐</span>", "PLA 1,75 mm, au moins 1 kg", "≈ 27,46 € la bobine de 1 kg"],
 ["<span class=coche>☐</span>", "4 disques imprimés et leurs 4 vis M6 avec écrous", "À imprimer, vis M6 en quincaillerie"],
 ["<span class=coche>☐</span>", "Fer à souder et embout pour inserts", "Embout : ≈ 18 € (kit) ou moins sur AliExpress"],
 ["<span class=coche>☐</span>", "Multimètre (réglage du LM2596)", "≈ 15 €"]])}
"""))

    def lignes(statut, sous_total=True):
        out, s = [], 0.0
        for cat, art, spec, q, util, pu, eco, alt, st in ACHATS:
            if st != statut:
                continue
            out.append([cat, f"<b>{art}</b><br><span style='color:#555'>{spec}</span>", str(q), util, euros(pu), euros(q * pu), eco, alt])
            s += q * pu
        if sous_total:
            out.append(["", "<b>Sous-total</b>", "", "", "", euros(s), "", ""])
        return out
    ent = ["Catégorie", "Article et spécification", "Qté", "Utilisé", "Prix u.", "Total", "Le moins cher", "Plus rapide ou alternative"]
    S.append(("2. Liste d'achats du banc (budget A)", "<p>Quantité = ce qu'il faut commander (lots compris) ; « Utilisé » = ce que le banc consomme. "
              "Les prix marqués « estimé » sont des ordres de grandeur, les autres ont été relevés chez le fournisseur cité.</p>"
              + tableau(ent, lignes("base"), num=(4, 5), classe_derniere="total")))
    imp = B["impression"]
    plein = ("RW-05_Collier", "RW-06_Croisillon", "RW-23_Entretoise-roulis")
    serre = ("RW-02_Platine-moteur", "RW-03_Carter", "RW-04_Palier", "RW-07_Fourche", "RW-11_Bornier", "RW-12_Porte-capteur")
    def g(x):
        return f(x, 0 if x >= 1 else 1) + " g"
    lignes_imp = [[p["nom"].replace("_", " "), str(p["nb"]), g(p["masse"]), g(p["masse_tot"]), f(p["heures"], 1) + " h",
                   "100 %" if p["nom"] in plein else ("4 à 5 parois, 30 à 40 %" if p["nom"] in serre else "3 parois, 15 à 20 %")]
                  for p in imp]
    lignes_imp.append(["<b>Total, avec 10 % de purge et de pertes</b>", "", "", f"<b>{f(B['pla_total'], 0)} g</b>", f"<b>{f(B['heures_total'], 0)} h</b>", ""])
    S.append(("3. Pièces à imprimer (PLA)", f"""
<p>Toutes les pièces sur mesure sont prévues en PLA, sur la Bambu Lab A1 (buse 0,4 mm, couches de 0,2 mm). Masses et durées sont
des estimations (0,8 g/cm³ pour 2 à 5 parois et un remplissage partiel, 20 g/h) : le trancheur donnera les valeurs exactes. Le
berceau de batterie (RW-09) n'est pas à imprimer maintenant. Coût du PLA : environ {euros(B['pla_total'] / 1000 * 27.46)} pour
{f(B['pla_total'], 0)} g à 27,46 €/kg.</p>
{tableau(["Pièce", "Nb", "Masse unitaire", "Masse totale", "Durée", "Réglages"], lignes_imp, num=(1, 2, 3, 4))}
<div class=note><b>Ordre d'impression conseillé :</b> croisillon, fourche, paliers et colliers d'abord (petites pièces, elles valident les
ajustements des roulements Ø16 et de la tige Ø5 : ajuster au besoin la compensation de trou du trancheur), puis le bornier (il valide
les barrettes), une potence (elle valide la carte TCRT5000), une platine, le corps, les 3 autres platines et potences,
les carters, le plateau et le socle en dernier (environ {f(impression('RW-10_Socle')['heures'], 0)} h ; une planche de bois ou de MDF
percée Ø12 le remplace). <b>Avant d'imprimer le plateau</b> (environ {f(impression('RW-08_Plateau')['heures'], 0)} h), mesurer la largeur et
l'épaisseur de l'ESC : les joues sont faites pour {f(ESC[2], 0)} mm d'épaisseur. Le PLA suffit pour le banc ; le PETG est conseillé pour les carters et
les platines si les essais deviennent longs (chaleur des moteurs).</div>"""))
    S.append(("4. Options et phase batterie", "<p>Les options rendent le banc plus sûr ou plus confortable (elles comptent dans le budget C) ; la phase batterie (budget B) se commande quand les essais sur alimentation de labo sont concluants.</p>"
              + tableau(ent, lignes("option") + lignes("batterie"), num=(4, 5))))
    S.append(("5. S'il faut aussi racheter (budget C)", "<p>Articles supposés déjà disponibles, avec leur prix si ce n'est pas le cas.</p>"
              + tableau(ent, lignes("stock"), num=(4, 5), classe_derniere="total")))
    paniers = {}
    for cat, art, spec, q, util, pu, eco, alt, st in ACHATS:
        if st != "base":
            continue
        cle = ("AliExpress" if "AliExpress" in eco else ("eBay" if "eBay" in eco else ("Brico Dépôt / quincaillerie" if ("Brico" in eco or "Quincaillerie" in eco) else "Amazon")))
        paniers.setdefault(cle, []).append(art)
    S.append(("6. Paniers par fournisseur et calendrier", tableau(["Fournisseur", "Articles", "Délai habituel"], [
        [k, ", ".join(v), "1 à 3 semaines" if k == "AliExpress" else ("3 à 7 jours" if k == "eBay" else "Immédiat ou 1 à 3 jours")]
        for k, v in paniers.items()]) + f"""
<ul>
<li><b>Jour 1 :</b> commande AliExpress groupée (roulements, axe Ø5, vis épaulées, goupilles, inserts, visserie, TCRT5000, barrettes, fils Dupont) ; achat du tube et de la quincaillerie en magasin.</li>
<li><b>Jours 1 à 5 :</b> impression des pièces (environ {f(B['heures_total'], 0)} h au total) ; pose des inserts à chaud dès que les pièces sont prêtes ; montage des modules de roue avec le câblage existant.</li>
<li><b>À réception :</b> montage du cardan, câblage du plateau, équilibrage statique, premiers essais sur alimentation de labo (1375 à 1625 µs).</li>
<li><b>Ensuite :</b> phase batterie (budget B), puis carte imprimée avec l'ESP32 pour la version suivante.</li>
</ul>
<div class=note><b>Points de vigilance à la commande :</b> modules TCRT5000 avec sortie numérique D0 et potentiomètre, broches coudées ; barrette à broches longues (une barrette standard tient mal les fils Dupont dessous) ;
roulements 625 avec flasques métal (2Z / ZZ) ; tige en acier rectifié h6 (pas en tige filetée) ; même KV pour les 4 moteurs ; en cas de
rachat d'ESC, vérifier « brushless » et « reverse » ; vérifier les frais de port, qui changent souvent l'ordre des prix.</div>"""))
    S.append(("Sources des prix", """<ul>
<li>Roulements 625ZZ : <a href='https://www.ebay.de/itm/336162286988'>eBay</a>, <a href='https://www.olimex.com/Products/Robot-CNC-Parts/Bearings/625ZZ/'>Olimex</a>, <a href='https://www.3djake.ch/fr-CH/3djake/roulements-a-billes?sai=33706'>3DJake</a>.</li>
<li>ESC bidirectionnels : <a href='https://www.robotshop.com/products/basic-30a-esc-v3-forward-reverse-firmware'>RobotShop</a>, <a href='https://www.mybotshop.de/Bidirectional-Brushless-ESC-30A-2-4s-UBEC-2A-5V'>MyBotShop</a>, <a href='https://www.ebay.de/itm/185507331451'>eBay</a>.</li>
<li>LiPo 3S 2200 mAh : <a href='https://www.ebay.de/p/1276219922'>SLS XTRON (eBay)</a>, <a href='https://www.rcteam.com/en/products/konect-lipo-11-1v-2200mah-35c-xt60-kn-lp3s2200'>RCteam</a>, <a href='https://hobbyking.com/fr_fr/turnigy-2200mah-3s-40c-lipo-pack-w-xt60.html'>HobbyKing</a>.</li>
<li>Chargeur SkyRC e3S : <a href='https://megadron.pl/en/products/skyrc-e3s-2s-3s-charger-33686.html'>Megadron</a>, <a href='https://www.unmannedtechshop.co.uk/fr/products/skyrc-e3s-20w-2-3s-lithium-balance-charger'>Unmanned Tech</a>.</li>
<li>Vis épaulées M4 Ø5 : <a href='https://www.ebay.de/itm/284890545791'>eBay</a>, <a href='https://www.lemu.dk/en/product/m4x5x10-a2-shoulder-boltiso-7379-129-h8-id-2985805001'>Lemu</a>.</li>
<li>Axe Ø5 : <a href='https://resources.ooznest.co.uk/aluminium-extrusion-system/linear-motion/linear-shafts/chrome-plated-linear-shafts/5mm-chrome-plated-hardened-ground-bearing-linear-shaft-cut-to-size-var-hgls-cp-5-cts'>Ooznest</a>.</li>
<li>Inserts M3 : <a href='https://www.3djake.ch/fr-CH/ruthex/inserts-filetes-m3-lot-de-100'>3DJake Ruthex</a>, <a href='https://www.prusa3d.com/fr/produit/inserts-filetes-m3-standard-100-pcs/'>Prusa</a> ; embout : <a href='https://filament2print.com/fr/maintenance-outils-fdm/4747-kit-embouts-inserts-filetes-thermofusibles-mintion.html'>Filament2print</a>.</li>
<li>Goupilles 3 × 16 : <a href='https://us.store.bambulab.com/en/products/d3-stainless-steel-dowel-pin'>Bambu Lab Store</a>, <a href='https://www.zoro.com/i/G3424620/'>Zoro</a>.</li>
<li>Tube 12 × 1 : <a href='https://www.bricodepot.fr/p/3232630508756/tube-rond-aluminium-brut-12-x-1-mm-1-m-argent'>Brico Dépôt</a>.</li>
<li>Entretoises et vis M3 : <a href='https://www.audiophonics.fr/fr/visserie-entretoises/entretoises-laiton-nickele-m3x15mm-femelle-femelle-x10-p-10234.html'>Audiophonics</a>.</li>
<li>GY-BNO055 : <a href='https://www.ebay.de/itm/405891892435'>eBay</a> ; PLA : <a href='https://www.ldlc.com/fiche/PB00727267.html'>LDLC</a>.</li>
<li>Barrette à broches longues, fils Dupont, TCRT5000, condensateur, coupe-circuit, fusible : prix estimés, non relevés.</li></ul>"""))
    return garde, S, (budget_a, budget_b, budget_c)


def main():
    global B
    B = C.bilan()
    rendre_pieces()
    g, S = doc_technique()
    imprimer(document("Documentation technique", g, S), os.path.join(DOSSIER, "Documentation-technique_banc-stabilisation.pdf"),
             "Banc de stabilisation · Documentation technique", S)
    g, S, budgets = carnet()
    imprimer(document("Carnet de commandes", g, S), os.path.join(DOSSIER, "Carnet-de-commandes_banc-stabilisation.pdf"),
             "Banc de stabilisation · Carnet de commandes", S)
    print("budgets A, B, C :", [round(b, 2) for b in budgets])


if __name__ == "__main__":
    main()
