"""Cotes du banc de stabilisation à 4 roues de réaction, version 3 (source unique, en mm).

Repère du dispositif, celui de « Système de stabilisation.SLDASM » : Z vers le haut, X = axe de roulis, Y = axe de
tangage, origine au centre du corps à la hauteur des axes des moteurs. Les 4 moteurs A2212 ont leur axe horizontal
sur les diagonales (45°, 135°, 225°, 315°) : chaque roue agit à cos 45° sur le roulis et sur le tangage.

Version 3 (10/11/2026), d'après les mesures du matériel : ESC de 78 mm (enveloppe prise à 80 × 32 × 14), 18 cm de fil du
moteur à l'ESC, 13 cm de l'ESC à sa XT60, fil silicone 16 AWG 200 °C (Ø 3,0 mm). Les ESC passent sur un étage, le
plateau supérieur, debout en couronne autour du BNO055. La carte de distribution XT60 1 vers 4 achetée (Jonronfey) est
au centre de l'étage, sur 4 entretoises, juste au-dessus des ESC : chaque ESC s'y branche par sa XT60. Le capteur de
vitesse TCRT5000 lit les 4 rayons du disque, côté extérieur, sur une potence vissée au carter. Tout le câblage est
dessiné (rw_cables.py).
Repère d'une face (plan_roue) : u tangentiel, v vertical (= z du dispositif), w selon la normale sortante ; la face
intérieure de la paroi est à w = −E_PAROI. Dans un module de roue, w est aussi l'axe du moteur.
"""
import math

ANGLES_ROUES = (45.0, 135.0, 225.0, 315.0)
ANGLES_FACES = (0.0, 90.0, 180.0, 270.0)            # faces ±X, ±Y (sans moteur)
C45 = math.cos(math.radians(45.0))

# ---------------------------------------------------------------- corps central (RW-01)
R_PAROI = 80.0            # demi-largeur extérieure, identique sur les 8 faces (160 mm sur plats)
E_PAROI = 4.0
Z_BAS, Z_HAUT = -35.0, 60.0
REBORD_BAS = 4.0          # rebord bas (raideur), le haut est fermé par le plateau
BOSSAGE = (10.0, 8.0)     # bossages des vis du plateau sur les faces ±X, ±Y : Ø, hauteur sous le haut

# ---------------------------------------------------------------- module de roue : platine (RW-02) et carter (RW-03)
E_PLATINE = 4.0
R_APPUI = R_PAROI + E_PLATINE     # face d'appui de la croix de fixation de l'A2212
TROUS_MOTEUR = [(sx * 11.7, sz * 11.65) for sx in (-1, 1) for sz in (-1, 1)]   # croix A2212 (u, v)
VIS_PLATINE = [(-20.0, 0.0), (20.0, 0.0)]                                       # 2 vis M3 de plus, dans des inserts
# empilage relevé dans « Système de stabilisation.SLDASM », compté depuis la face d'appui du moteur
CLOCHE = (7.3, 29.3, 14.0)        # cloche tournante de l'A2212 : début, fin, rayon
ARBRE_FIN = 40.7
DISQUE = (32.7, 37.2, 60.0)       # disque Ø120 × 4,5 : début, fin, rayon
VIS_DISQUE = (26.7, 41.5, 48.0, 61.0)   # vis M6 d'équilibrage et écrous en rotation : début, fin, rayons int. et ext.
RAYONS_DISQUE = (12.0, 50.0, 15.0)      # disque d'origine ajouré : 4 rayons pleins de 15° entre r 12 et 50 (relevé du STEP)
CARTER_R = (65.0, 67.5)           # bande du carter : rayon intérieur, extérieur
CARTER_AX = (23.5, 45.0)          # étendue axiale du carter depuis la face d'appui
LEVRE_R = 62.0                    # lèvres du carter, hors de l'enveloppe tournante (61)
BARRE = (10.0, 8.0)               # barres du carter (tangentiel × radial), en haut et en bas
BARRE_R = (63.0, 71.0)            # position radiale des barres (autour de l'axe du moteur)

# ---------------------------------------------------------------- passages dans chaque face diagonale (u, v)
FENTE_FILS = (10.0, 16.0, -12.0)  # fente des fils moteur, ouverte vers le haut (les fils s'y posent par-dessus) : largeur, v du bas, u du centre
V_FILS = 21.0                     # hauteur où les fils moteur traversent la paroi

# ---------------------------------------------------------------- ESC sur l'étage (plateau), debout en couronne
ESC = (80.0, 32.0, 14.0)          # ESC 30 A existant, enveloppe : longueur (78 mesurés), largeur (debout), épaisseur
ESC_A = 53.0                      # distance du centre au plan médian de chaque ESC (couronne carrée)
SUPPORT_ESC = (2.0, 18.0, 60.0, 0.5)   # joues du support : épaisseur, hauteur, longueur, jeu de chaque côté
SANGLE_ESC = (3.2, 2.2, 28.0)     # fentes du collier qui tient l'ESC : largeur, épaisseur, position le long de l'ESC (±)
ENCOCHE_COIN = (20.0, 67.0)       # encoche de chaque coin du plateau (fils moteur, alimentation, capteur) : largeur, rayon intérieur
# ESC k : face (angle du plan médian), angle du coin de son bout moteur, angle du coin de son bout alimentation
ESC_FACE = (0.0, 90.0, 180.0, 270.0)
ESC_COIN_MOTEUR = (45.0, 135.0, 225.0, 315.0)
ESC_COIN_ALIM = (315.0, 45.0, 135.0, 225.0)

# ---------------------------------------------------------------- carte de distribution XT60 1 vers 4, au centre de l'étage
# Achetée (Jonronfey, « XT60 Male to 4 XT60 Female », LED de polarité) : entrée XT60 mâle coudée d'un côté,
# 4 sorties XT60 femelles droites en ligne. Cotes de l'annonce (74 × 32 mm, trous M3) ; position des sorties, de l'entrée
# et entraxe des trous relevés sur la photo du vendeur : à vérifier sur la carte. Posée sur 4 entretoises : le dessous de
# la carte passe 3 mm au-dessus des ESC, et la fiche du câble d'alimentation, branchée sur l'entrée, passe au-dessus de
# l'ESC +X (à plat sur le plateau, elle aurait buté dedans).
PDB = (74.0, 32.0, 1.6)            # longueur (selon X, entrée côté +X), largeur, épaisseur
PDB_TROUS = [(sx * 33.0, sy * 12.0) for sx in (-1, 1) for sy in (-1, 1)]   # trous M3 (entraxe 66 × 24, estimé)
PDB_SORTIES = (15.3, 1.3, -14.8, -30.3)    # x des 4 sorties XT60 femelles, sur l'axe de la carte
PDB_ENTREE = (23.0, 48.4, 9.0)     # entrée mâle coudée : x début, x du bout, hauteur au-dessus de la carte
PDB_LED = (30.0, 12.5)             # LED de polarité (x, y)
XT60_SECTION = (8.2, 15.6)         # boîtier XT60 : épaisseur, largeur
XT60_DOUILLE_H = 16.0              # sortie femelle droite : hauteur au-dessus de la carte
XT60_FICHE_H = 12.0                # fiche mâle de l'ESC, branchée : hauteur visible au-dessus de la sortie
FICHE_ENTREE = 16.0                # fiche femelle du câble d'alimentation, branchée sur l'entrée : longueur
PDB_SORTIE_ESC = (1, 0, 2, 3)      # sortie (rang dans PDB_SORTIES) de l'ESC k : chaque fil part vers son coin sans en croiser un autre
ENTRETOISE = 35.0                  # entretoises hexagonales M3 F/F de 35 mm sous la carte
POS_ENTRETOISES = PDB_TROUS

# ---------------------------------------------------------------- capteur de vitesse : TCRT5000 sur une potence (RW-12)
# En haut de chaque roue, devant la face extérieure du disque : il lit le passage des 4 rayons (4 impulsions par tour),
# sans rien coller. Son câble rejoint directement l'étage, sans entrer dans le corps.
TCRT_CARTE = (32.0, 14.0, 1.6)    # carte du commerce (à mesurer) : longueur (tangentielle), largeur, épaisseur
TCRT_BOITIER = (10.0, 5.8, 7.0)   # boîtier TCRT5000 au bout de la carte : longueur, largeur, hauteur
TCRT_V = 40.0                     # trou de fixation de la carte, au-dessus de l'axe ; capteur à 41,5 mm de l'axe
TCRT_ECART = 4.0                  # du capteur à la face extérieure du disque (plage du TCRT5000 : 0,2 à 15 mm)
W_CARTE = E_PLATINE + DISQUE[1] + TCRT_ECART + TCRT_BOITIER[2]   # face de la carte côté composants (vers le disque)
PATTE_CARTER = (14.0, 6.5, 31.0)  # bossage du carter (haut de la bande, jusqu'à la lèvre extérieure) : largeur, saillie, w début
POTENCE = (10.0, 4.0)             # bras de la potence : largeur, épaisseur

# ---------------------------------------------------------------- cardan
CROIX = 28.0                      # croisillon, cube
D_TIGE = 5.0                      # tige de tangage Ø5 et vis épaulées de roulis Ø5 (ISO 7379, M4)
TIGE = 200.0                      # longueur de la tige de tangage
ROULEMENT = (16.0, 5.0, 5.0)      # 625-2Z : Ø ext, épaisseur, Ø int
R_GOUPILLE = 11.5                 # rayon des goupilles de blocage et de butée (Ø3) autour de chaque axe
BUTEE = 20.0                      # débattement de chaque axe, en degrés
# palier de tangage (RW-04) vissé sur les faces ±Y du corps, à 5 hauteurs (centre de gravité en haut de la plage)
Z_PIVOTS = (24.0, 16.0, 8.0, 0.0, -8.0)
PALIER = (34.0, 44.0, 8.0)        # x × z × épaisseur
PALIER_TROUS_X = 12.0
PALIER_REGLAGE = 4.0              # lumières verticales des 2 vis du palier : le pivot se règle à ±4 mm autour de chaque rangée
# fourche de roulis (RW-07)
FOURCHE_JEU = 1.0
FOURCHE_BRAS = 8.0                # épaisseur des bras
FOURCHE_LARGE = 15.0              # demi-largeur des bras (selon Y)
FOURCHE_BASE = (20.0, 20.0)       # garde sous le pivot (balayage du croisillon), hauteur du socle de fourche
TUBE = (12.0, 1.0, 136.0)         # poteau : tube alu Ø12 × 1, longueur (rw_verif donne le pied au ras de la table ; 4 mm de moins)
EMMANCHEMENT = 18.0
FENETRE_X = (26.0, 12.0)          # fenêtres d'accès aux goupilles de roulis (faces ±X) : largeur, marge autour des pivots

# ---------------------------------------------------------------- plateau supérieur (RW-08), l'étage, et bornier (RW-11)
# L'ESP32 et le régulateur restent sur la table (breadboard). Le plateau ferme le corps et porte le BNO055 au centre, les
# 4 ESC debout autour, le bornier sur le bord −X (sortie de la nappe des signaux) ; les câbles de signal font le tour
# par la bordure, entre les ESC et le bord ; le câble d'alimentation arrive par la face +X sur l'entrée de la carte.
Z_PLATEAU = Z_HAUT
E_PLATEAU = 5.0
VIS_PLATEAU = (0.0, 90.0, 180.0, 270.0)   # 4 vis M3 dans les bossages des faces ±X, ±Y
R_VIS_PLATEAU = R_PAROI - E_PAROI - BOSSAGE[0] / 2 + 1.0    # le bossage entre de 1 mm dans la paroi
PASSE_COLLIER = (3.2, 2.0, 9.0, 10.0)     # tunnel pour collier de 2,5 mm : largeur, hauteur, longueur ; pas de la grille
R_REPERES = 58.0                          # 1 à 4 points gravés dans chaque coin : numéro du module de roue
BNO055 = (27.0, 21.0, 1.6)        # GY-BNO055 (à mesurer) : barrette 8 broches le long d'un grand côté
BNO_LOGEMENT = (22.0, 28.0)       # BNO055 tourné de 90° (grand côté selon Y), broches vers le haut, barrette côté −X
BORNIER_N = 15                    # barrettes mâles 1 × 15 : ESC (S + −) et capteurs (V G D), 4 groupes de 3
BORNIER_X = (-80.0, -67.5)        # bloc posé sur le plateau, entre l'ESC −X et le bord
BORNIER_LEVRE = (-98.0, 4.0)      # lèvre en porte-à-faux hors du corps : x extérieur, épaisseur
BORNIER_H = 11.0
X_BARRETTES = (-85.0, -91.0)      # rangées : câbles de commande des ESC, capteurs de vitesse
PIONS_BORNIER = [(-76.5, -18.0), (-76.5, 18.0)]
FLECHE = (-6.0, 22.0, 12.0)       # flèche +X gravée (axe de roulis) : début, y, longueur
SORTIE_Y = 22.0                   # câbles vers la table : colliers sur les faces ±X à y = ∓22, z −20
NAPPE_SOCLE = 6.0                 # colliers des câbles dans deux tunnels du moyeu du socle (±X), à 6 mm du haut
# phase batterie (plus tard) : berceau RW-09, hors du montage actuel (à revoir : les ESC et la carte de distribution
# occupent maintenant le dessus du plateau)
BERCEAU = (130.0, 40.0, 3.0)
BATTERIE = (105.0, 34.0, 24.0)    # LiPo 3S 2200 mAh (à confirmer)

# ---------------------------------------------------------------- câblage (rw_cables.py)
D_FIL = 3.0                       # fil silicone 16 AWG 200 °C, 252 brins de 0,08 mm : Ø extérieur 3,0 mm
D_MOTEUR, D_ALIM, D_PRINCIPAL = 6.5, 6.0, 6.5     # 3 fils en faisceau, 2 fils, câble d'alimentation (enveloppes)
D_COMMANDE, D_CAPTEUR, D_BNO, D_NAPPE = 3.0, 3.5, 4.0, 8.0   # câble servo 3 fils, 3 fils Dupont, 4 fils Dupont, nappe
R_COURBURE = 9.0                  # rayon de courbure mini du 16 AWG silicone (3 × Ø)
LONGUEURS = {"moteur": 180.0, "alim_esc": 130.0}     # mesurées sur le câblage ; les autres câbles sont relevés sur le modèle

# ---------------------------------------------------------------- socle (RW-10)
SOCLE = (240.0, 240.0, 6.0)
MOYEU_SOCLE = (36.0, 50.0)        # bossage central : Ø, hauteur

# ---------------------------------------------------------------- masses (g) et masses volumiques (g/cm3)
RHO_IMPRIME = 0.8                 # PLA/PETG imprimé, 2 parois et 15 % de remplissage
RHO_PLEIN = 1.24
MASSES = {"moteur": 58.0, "disque": 50.0, "esc": 28.0, "batterie": 180.0, "bno055": 3.0, "xt60": 10.0, "pdb": 20.0, "entretoise": 1.5,
          "nappe": 12.0, "alim": 12.0, "barrette": 1.0, "roulement": 4.4, "tige": 31.0, "vis_epaulee": 3.0, "tcrt": 3.0,
          "tige_m6": 10.6, "ecrou_m6": 2.4}
MASSE_LINEIQUE = {"fil16": 18.0, "commande": 10.0, "dupont": 3.0}   # g/m : un fil 16 AWG silicone, câble servo, un fil Dupont
Z_SOCLE = -156.0                  # dessus du socle sous le pivot (point le plus bas à ±20° combinés : 141,0 mm, marge 15)
Z_PIVOT_DEFAUT = Z_PIVOTS[0]      # rangée montée : la plus haute

# ---------------------------------------------------------------- équilibrage : amener le centre de masse sur le pivot
# 4 tiges filetées M6 sortent des faces ±X et ±Y, serrées sur la paroi par un écrou de chaque côté. Les écrous de réglage
# s'y déplacent : leur nombre donne le réglage grossier, leur position le réglage fin. Les tiges sont décalées de EQ_DECALAGE
# sur leur face, en moulin (+X à y > 0, +Y à x < 0, −X à y < 0, −Y à x > 0) : elles passent à côté des fenêtres et des
# paliers et leurs masses s'annulent deux à deux. La hauteur du pivot se règle par les lumières des paliers.
EQ_TIGE = (6.0, 60.0)             # tige filetée M6 : Ø, longueur
EQ_ECROU = (10.0, 5.0)            # écrou M6 : sur plats, hauteur
EQ_Z = -20.0                      # hauteur des 4 tiges (sous l'axe des roues, au-dessus du rebord bas)
EQ_DECALAGE = 25.0                # décalage de chaque tige par rapport au milieu de sa face : sur ±Y, les écrous passent à
                                  # 2,2 mm du palier (±17 mm) dans toute sa course (rangées −8 à +24, lumières ±4)
EQ_INTERIEUR = 6.5                # longueur de tige à l'intérieur du corps (écrou de serrage intérieur compris)
EQ_FACES = (0.0, 90.0, 180.0, 270.0)    # faces +X, +Y, −X, −Y
# réglage nominal de la CAO (calculé par jumeau_numerique/construction/preparer_cao.py --equilibrer) : nombre d'écrous de réglage de chaque tige et distance de leur
# milieu au centre du corps, puis hauteur du pivot qui met le centre de masse sur l'axe de tangage
EQ_ECROUS = (3, 1, 0, 2)
EQ_POSITIONS = (104.9, 89.1, 107.8, 103.6)
Z_PIVOT_EQUILIBRE = 25.0           # rangée +24 mm, paliers remontés de 1,0 mm dans leurs lumières
FACES_EQ = ("+X", "+Y", "−X", "−Y")


def ecrous_equilibrage():
    """Écrous des 4 tiges d'équilibrage : [(k, angle de la face, position du centre de l'écrou le long de la tige depuis la
    face extérieure de la paroi, rôle, rang)]. 2 écrous de serrage par tige (un de chaque côté de la paroi), puis le
    paquet des écrous de réglage, de l'intérieur vers l'extérieur."""
    he = EQ_ECROU[1]
    out = []
    for k, a in enumerate(EQ_FACES):
        out += [(k, a, -E_PAROI - he / 2, "serrage", 0), (k, a, he / 2, "serrage", 1)]
        n = EQ_ECROUS[k]
        out += [(k, a, EQ_POSITIONS[k] - R_PAROI + (j - (n - 1) / 2) * he, "reglage", j) for j in range(n)]
    return out
