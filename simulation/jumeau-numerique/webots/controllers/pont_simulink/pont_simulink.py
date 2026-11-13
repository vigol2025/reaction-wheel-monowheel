"""Pont entre Simulink et le jumeau Webots du banc de stabilisation (version 3).

Simulink commande, Webots obéit : ce contrôleur tient la place de l'ESP32 et de tout ce qui est derrière lui.
  - port 5007 : au lancement de la simulation, MATLAB envoie ses réglages (51 nombres, Model Workspace du modèle) ;
    le banc est remis en position de départ ;
  - port 5006 : trame de commande, celle de l'ESP32 du banc réel (4 impulsions d'ESC en µs), suivie de la poussée d'essai
    (2 nombres, N.m, pour le jumeau seulement), toutes les T_pont ;
  - port 5005 : trame de télémétrie, la même que celle de l'ESP32 (BNO055, 4 vitesses de roue), suivie des grandeurs
    réelles du jumeau (angles du cardan, vitesses, courants, couples, tensions).
Webots avance de T_pont à chaque trame de commande reçue : les deux logiciels restent au même instant.

Webots ne calcule que la mécanique (corps et liaisons de la CAO). Les ESC, les moteurs A2212, les butées, le frottement
du cardan, le BNO055 et les TCRT5000 sont calculés ici, avec les mêmes équations que le jumeau Simscape.
"""
import json
import math
import os
import random
import select
import socket
import struct

from controller import Supervisor

HOTE = "127.0.0.1"
PORT_TELEMETRIE, PORT_COMMANDE, PORT_CONFIG = 5005, 5006, 5007
N_CONFIG = 51                                              # nombres en simple précision
N_COMMANDE = 21                                            # octets : les 13 de l'ESP32, plus la poussée d'essai
SOUS_PAS = 20                                              # calcul du courant des moteurs : 20 sous-pas par pas de Webots
NOMS_CONFIG = ("pivot_mm", "blocage_roulis", "blocage_tangage", "q0_roulis_deg", "q0_tangage_deg", "V_alim", "f_trame_esc",
               "imp_neutre", "imp_min", "imp_max", "zone_morte_us", "tau_esc", "armement_actif", "t_armement",
               "fenetre_armement_us", "sens1", "sens2", "sens3", "sens4", "Ke", "Kt", "R_moteur", "L_moteur", "f_roue",
               "butee_deg", "k_butee", "c_butee", "b_cardan", "k_cables", "g", "T_bno", "bruit_bno", "sigma_angle_deg",
               "sigma_gyro_dps", "sigma_acc", "n_rayons", "t_arret_tcrt", "T_tcrt")


# ------------------------------------------------------------------ petites matrices 3 × 3 (listes de lignes)
def produit(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def transposee_fois(A, v):
    return [sum(A[k][i] * v[k] for k in range(3)) for i in range(3)]


def rotation_quaternion(q):
    """Matrice de rotation d'un quaternion (x, y, z, w)."""
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def rotation_cardan(roulis, tangage):
    """Orientation du dispositif pour des angles de cardan donnés : roulis autour de X, puis tangage autour de Y."""
    cr, sr, ct, st = math.cos(roulis), math.sin(roulis), math.cos(tangage), math.sin(tangage)
    return produit([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], [[ct, 0, st], [0, 1, 0], [-st, 0, ct]])


def quaternion_bruit(q, n):
    """Quaternion q tourné d'une petite rotation n (rad, axes du capteur) : le bruit de mesure de l'orientation, de même écart
    type que celui des angles d'Euler (le BNO055 tire ses angles d'Euler de son quaternion)."""
    d = [1.0, n[0] / 2, n[1] / 2, n[2] / 2]
    w = q[0] * d[0] - q[1] * d[1] - q[2] * d[2] - q[3] * d[3]
    x = q[0] * d[1] + d[0] * q[1] + q[2] * d[3] - q[3] * d[2]
    y = q[0] * d[2] + d[0] * q[2] + q[3] * d[1] - q[1] * d[3]
    z = q[0] * d[3] + d[0] * q[3] + q[1] * d[2] - q[2] * d[1]
    m = math.sqrt(w * w + x * x + y * y + z * z)
    s = 1.0 if w >= 0 else -1.0
    return [s * w / m, s * x / m, s * y / m, s * z / m]


def quaternion_rotation(R):
    """Quaternion (w, x, y, z) d'une matrice de rotation, w positif."""
    t = R[0][0] + R[1][1] + R[2][2]
    if t > 0:
        w = math.sqrt(1 + t) / 2
        q = [w, (R[2][1] - R[1][2]) / (4 * w), (R[0][2] - R[2][0]) / (4 * w), (R[1][0] - R[0][1]) / (4 * w)]
    else:
        k = max(range(3), key=lambda i: R[i][i])
        i, j = (k + 1) % 3, (k + 2) % 3
        r = math.sqrt(1 + R[k][k] - R[i][i] - R[j][j]) * 2
        q = [0.0, 0.0, 0.0, 0.0]
        q[0] = (R[j][i] - R[i][j]) / r
        q[1 + k] = r / 4
        q[1 + i] = (R[i][k] + R[k][i]) / r
        q[1 + j] = (R[j][k] + R[k][j]) / r
    return [-c for c in q] if q[0] < 0 else q


def dire(texte):
    print("pont_simulink : " + texte, flush=True)


def entier16(x):
    return max(-32768, min(32767, int(round(x))))


# ------------------------------------------------------------------ liaison avec Simulink
class Liaison:
    """Trois ports locaux en écoute. Simulink est le client, comme il le sera de l'ESP32."""

    def __init__(self):
        self.ecoutes = {}
        for port in (PORT_CONFIG, PORT_TELEMETRIE, PORT_COMMANDE):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((HOTE, port))
            s.listen(1)
            self.ecoutes[port] = s
        self.telemetrie = None
        self.commande = None

    @staticmethod
    def lire(s, n):
        """Lit exactement n octets ; None si la connexion est fermée."""
        d = b""
        while len(d) < n:
            try:
                m = s.recv(n - len(d))
            except OSError:
                return None
            if not m:
                return None
            d += m
        return d

    def attendre(self, port, delai):
        e = self.ecoutes[port]
        pret, _, _ = select.select([e], [], [], delai)
        if not pret:
            return None
        s, _ = e.accept()
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return s

    def attendre_config(self):
        """Attend que MATLAB envoie ses réglages. Renvoie (connexion, liste des 51 nombres)."""
        while True:
            s = self.attendre(PORT_CONFIG, None)
            s.settimeout(5)
            d = self.lire(s, 4 * N_CONFIG)
            if d is not None:
                return s, list(struct.unpack(f"<{N_CONFIG}f", d))
            s.close()

    def ouvrir(self, delai=30):
        """Après les réglages, Simulink ouvre ses deux liaisons de données."""
        self.fermer()
        self.telemetrie = self.attendre(PORT_TELEMETRIE, delai)
        self.commande = self.attendre(PORT_COMMANDE, delai) if self.telemetrie else None
        if not self.commande:
            self.fermer()
            return False
        return True

    def fermer(self):
        for s in (self.telemetrie, self.commande):
            if s:
                try:
                    s.close()
                except OSError:
                    pass
        self.telemetrie = self.commande = None


# ------------------------------------------------------------------ le banc
class Banc:
    def __init__(self):
        self.robot = Supervisor()
        ici = os.path.dirname(os.path.abspath(__file__))
        self.donnees = json.load(open(os.path.join(ici, "banc.json"), encoding="utf-8"))
        self.pas_ms = int(self.robot.getBasicTimeStep())
        self.dt = self.pas_ms / 1000.0
        assert self.pas_ms == self.donnees["pas_ms"], "pas de calcul du monde différent de celui de banc.json"
        r = self.robot
        self.moteurs_cardan = [r.getDevice("moteur_roulis"), r.getDevice("moteur_tangage")]
        self.angles_cardan = [r.getDevice("angle_roulis"), r.getDevice("angle_tangage")]
        self.moteurs_roues = [r.getDevice(f"moteur_roue_{k}") for k in (1, 2, 3, 4)]
        self.angles_roues = [r.getDevice(f"angle_roue_{k}") for k in (1, 2, 3, 4)]
        self.orientation = r.getDevice("bno055_orientation")
        self.gyroscope = r.getDevice("bno055_gyroscope")
        self.accelerometre = r.getDevice("bno055_accelerometre")
        for c in self.angles_cardan + self.angles_roues + [self.orientation, self.gyroscope, self.accelerometre]:
            c.enable(self.pas_ms)
        self.noeud_monde = r.getFromDef("MONDE")
        self.liaisons = [r.getFromDef("ROULIS"), r.getFromDef("TANGAGE")] + [r.getFromDef(f"ROUE{k}") for k in (1, 2, 3, 4)]
        self.noeud_dispositif = r.getFromDef("DISPOSITIF")
        self.noeud_paliers = r.getFromDef("PALIERS")
        self.noeud_physique = r.getFromDef("PHYSIQUE_DISPOSITIF")
        self.pivot_mm = self.donnees["pivot_monde_mm"]
        self.c = None

    # -------------------------------------------------------------- réglages et position de départ
    def configurer(self, v):
        """Applique les réglages de MATLAB et remet le banc en position de départ, à l'arrêt. Renvoie False si refusé."""
        c = dict(zip(NOMS_CONFIG, v))
        c["sens"] = [c.pop(f"sens{k}") for k in (1, 2, 3, 4)]
        m = v[len(NOMS_CONFIG):len(NOMS_CONFIG) + 9]         # R_montage_bno, rangée colonne par colonne
        c["R_montage"] = [[m[i + 3 * j] for j in range(3)] for i in range(3)]
        c["T_pont"] = v[47]
        c["t_lacher"], c["k_main"], c["c_main"] = v[48], v[49], v[50]
        cle = f"{c['pivot_mm']:g}"
        if cle not in self.donnees["pivots"]:
            dire(f"pivot_mm = {cle} refusé (positions possibles : {', '.join(self.donnees['pivots'])})")
            return False
        for nom in ("T_pont", "T_bno", "T_tcrt"):
            n = c[nom] / self.dt
            if abs(n - round(n)) > 1e-3 or round(n) < 1:
                dire(f"{nom} = {c[nom]:g} s refusé (multiple de {self.dt:g} s attendu)")
                return False
        self.c = c
        self.n_pont = round(c["T_pont"] / self.dt)
        self.n_bno = round(c["T_bno"] / self.dt)
        self.n_tcrt = round(c["T_tcrt"] / self.dt)
        self.n_esc = max(1, round(1 / (c["f_trame_esc"] * self.dt)))
        self.bloque = [c["blocage_roulis"] != 0, c["blocage_tangage"] != 0]
        self.q0 = [math.radians(c["q0_roulis_deg"]), math.radians(c["q0_tangage_deg"])]
        # 1) à plat, à l'arrêt, sans pesanteur
        self.noeud_monde.getField("gravity").setSFFloat(0.0)
        self._poser([0.0, 0.0])
        # 2) position du pivot sur le corps : le dispositif descend ou monte par rapport au centre de rotation
        if c["pivot_mm"] != self.pivot_mm:
            p = self.donnees["pivots"][cle]
            z = c["pivot_mm"] / 1000.0
            self.noeud_dispositif.getField("translation").setSFVec3f([0.0, 0.0, -z])
            self.noeud_paliers.getField("translation").setSFVec3f([0.0, 0.0, z])
            self.noeud_physique.getField("centerOfMass").setMFVec3f(0, p["G"])
            self.noeud_physique.getField("inertiaMatrix").setMFVec3f(0, p["I"][0])
            self.noeud_physique.getField("inertiaMatrix").setMFVec3f(1, p["I"][1])
            self.pivot_mm = c["pivot_mm"]
            self._poser([0.0, 0.0])
        # 3) position de départ, puis la pesanteur
        self._poser(self.q0)
        self.noeud_monde.getField("gravity").setSFFloat(c["g"])
        # états des modèles
        self.pas = 0                                       # pas de Webots depuis le départ
        self.imp = [c["imp_neutre"]] * 4                   # dernière commande reçue
        self.imp_lue = [c["imp_neutre"]] * 4               # impulsion lue par l'ESC à la dernière trame de 20 ms
        self.duree_neutre = [0.0] * 4
        self.arme = [False] * 4
        self.u = [0.0] * 4                                 # rapports cycliques
        self.V = [0.0] * 4                                 # tensions moyennes appliquées aux moteurs
        self.i = [0.0] * 4                                 # courants
        self.Cm = [0.0] * 4
        self.q = list(self.q0)
        self.dq = [0.0, 0.0]
        self.theta = [0.0] * 4
        self.w = [0.0] * 4
        self.seq = 0
        self.bno = None
        self.tcrt = None
        self.w_mes = [0.0] * 4
        self.alea = random.Random(55)
        self.poussee = [0.0, 0.0]
        self._tcrt()
        self._bno(rotation_cardan(*self.q0), [0.0, 0.0, 0.0], transposee_fois(rotation_cardan(*self.q0), [0.0, 0.0, c["g"]]))
        return True

    def _poser(self, q):
        """Met le cardan aux angles q et les roues à 0, tout à l'arrêt (un pas de Webots, sans effort)."""
        for liaison, angle in zip(self.liaisons, list(q) + [0.0] * 4):
            liaison.setJointPosition(angle)
        self.robot.simulationResetPhysics()
        for k, m in enumerate(self.moteurs_cardan):
            if self.c and self.bloque[k]:
                m.setPosition(q[k])
            else:
                m.setTorque(0.0)
        for m in self.moteurs_roues:
            m.setTorque(0.0)
        self.robot.step(self.pas_ms)

    # -------------------------------------------------------------- modèles
    def _esc(self):
        """ESC : lecture de l'impulsion à chaque trame (20 ms), armement, rapport cyclique."""
        c = self.c
        if self.pas % self.n_esc == 0:
            self.imp_lue = list(self.imp)
            for k in range(4):
                au_neutre = abs(self.imp_lue[k] - c["imp_neutre"]) <= c["fenetre_armement_us"]
                self.duree_neutre[k] = (self.duree_neutre[k] + 1 / c["f_trame_esc"]) if au_neutre else 0.0
                self.arme[k] = self.arme[k] or self.duree_neutre[k] >= c["t_armement"] or c["armement_actif"] == 0
        for k in range(4):
            e = min(c["imp_max"], max(c["imp_min"], self.imp_lue[k])) - c["imp_neutre"]
            if e > c["zone_morte_us"]:
                e -= c["zone_morte_us"]
            elif e < -c["zone_morte_us"]:
                e += c["zone_morte_us"]
            else:
                e = 0.0
            self.u[k] = c["sens"][k] * (e / (c["imp_max"] - c["imp_neutre"]) if self.arme[k] else 0.0)

    def _moteurs(self):
        """Tension de l'ESC (temps de réponse tau_esc) et courant du moteur (L di/dt = V - R i - Ke omega) sur un pas de
        Webots, la vitesse étant tenue constante. Renvoie le couple moyen sur le pas, frottement compris."""
        c = self.c
        h = self.dt / SOUS_PAS
        a_esc = math.exp(-h / c["tau_esc"]) if c["tau_esc"] > 0 else 0.0
        a_mot = math.exp(-c["R_moteur"] * h / c["L_moteur"])
        b_mot = (1 - a_mot) * c["L_moteur"] / (c["R_moteur"] * h)   # part du courant de départ dans la moyenne
        couples = []
        for k in range(4):
            Vc = self.u[k] * c["V_alim"]
            V, i, somme = self.V[k], self.i[k], 0.0
            for _ in range(SOUS_PAS):
                Vm = Vc + (V - Vc) * (1 - a_esc) * c["tau_esc"] / h if c["tau_esc"] > 0 else Vc   # tension moyenne du sous-pas
                V = Vc + (V - Vc) * a_esc
                i_inf = (Vm - c["Ke"] * self.w[k]) / c["R_moteur"]
                somme += i_inf + (i - i_inf) * b_mot
                i = i_inf + (i - i_inf) * a_mot
            self.V[k], self.i[k] = V, i
            self.Cm[k] = c["Kt"] * somme / SOUS_PAS
            couples.append(self.Cm[k] - c["f_roue"] * self.w[k])
        return couples

    def _cardan(self, k):
        """Couple sur un axe du cardan : frottement des roulements, raideur des câbles, butées (goupille dans sa lumière)."""
        c = self.c
        q, dq, lim = self.q[k], self.dq[k], math.radians(c["butee_deg"])
        couple = -c["b_cardan"] * dq - c["k_cables"] * q
        t = self.pas * self.dt
        if t < c["t_lacher"]:                              # tenu à la main à sa position de départ
            couple += c["k_main"] * (self.q0[k] - q) - c["c_main"] * dq
        couple += self.poussee[k]                          # poussée d'essai, reçue dans la trame de commande
        if q > lim:                                        # la butée repousse, elle ne retient jamais
            couple += min(0.0, -c["k_butee"] * (q - lim) - c["c_butee"] * dq)
        elif q < -lim:
            couple += max(0.0, -c["k_butee"] * (q + lim) - c["c_butee"] * dq)
        return couple

    def _tcrt(self):
        """TCRT5000 : un front à chaque rayon du disque ; vitesse = pas angulaire / durée entre deux fronts, sans signe."""
        c = self.c
        T = c["T_tcrt"]
        pas = 2 * math.pi / c["n_rayons"]
        if self.tcrt is None:
            self.tcrt = {"k": [math.floor(t / pas) for t in self.theta], "th": list(self.theta), "t": 0.0,
                         "front": [-math.inf] * 4, "w": [0.0] * 4}
        s = self.tcrt
        for j in range(4):
            th = self.theta[j]
            k = math.floor(th / pas)
            if k != s["k"][j]:
                th_f = (k if k > s["k"][j] else s["k"][j]) * pas          # dernier rayon franchi
                tf = s["t"] - T + T * (th_f - s["th"][j]) / (th - s["th"][j])
                if math.isfinite(s["front"][j]) and tf > s["front"][j]:
                    s["w"][j] = abs(k - s["k"][j]) * pas / (tf - s["front"][j])
                s["front"][j] = tf
            elif s["t"] - s["front"][j] > c["t_arret_tcrt"]:
                s["w"][j] = 0.0
            s["k"][j], s["th"][j] = k, th
        s["t"] += T
        self.w_mes = list(s["w"])

    def _bno(self, R, gyro, acc):
        """BNO055 en mode fusion, à partir de l'orientation vraie : registres d'Euler (cap, roulis, tangage), de vitesse,
        de quaternion et d'accélération, bruit de mesure compris. R, gyro, acc : dans les axes du dispositif."""
        c = self.c
        Rs = produit(R, c["R_montage"])
        w = transposee_fois(c["R_montage"], gyro)
        f = transposee_fois(c["R_montage"], acc)
        euler = [math.degrees(math.atan2(Rs[1][0], Rs[0][0])), math.degrees(math.atan2(Rs[2][1], Rs[2][2])),
                 -math.degrees(math.asin(max(-1.0, min(1.0, Rs[2][0]))))]
        b = c["bruit_bno"]
        g = self.alea.gauss
        self.bno = {"euler": [entier16((x + b * c["sigma_angle_deg"] * g(0, 1)) * 16) for x in euler],
                    "gyro": [entier16((math.degrees(x) + b * c["sigma_gyro_dps"] * g(0, 1)) * 16) for x in w],
                    "quat": [entier16(x * 16384) for x in quaternion_bruit(quaternion_rotation(Rs), [b * math.radians(c["sigma_angle_deg"]) * g(0, 1) for _ in range(3)])],
                    "acc": [entier16((x + b * c["sigma_acc"] * g(0, 1)) * 100) for x in f]}

    # -------------------------------------------------------------- un pas de Webots
    def avancer(self):
        self._esc()
        couples = self._moteurs()
        for k, m in enumerate(self.moteurs_roues):
            m.setTorque(couples[k])
        for k, m in enumerate(self.moteurs_cardan):
            if self.bloque[k]:
                m.setPosition(0.0)                         # goupille de blocage
            else:
                m.setTorque(self._cardan(k))
        if self.robot.step(self.pas_ms) == -1:
            return False
        self.pas += 1
        q = [s.getValue() for s in self.angles_cardan]
        th = [s.getValue() for s in self.angles_roues]
        self.dq = [(a - b) / self.dt for a, b in zip(q, self.q)]
        self.w = [(a - b) / self.dt for a, b in zip(th, self.theta)]
        self.q, self.theta = q, th
        if self.pas % self.n_tcrt == 0:
            self._tcrt()
        if self.pas % self.n_bno == 0:
            self._bno(rotation_quaternion(self.orientation.getQuaternion()), self.gyroscope.getValues(), self.accelerometre.getValues())
        return True

    # -------------------------------------------------------------- trames
    def lire_commande(self, d):
        """Trame de commande : A5 5A, 4 impulsions (uint16, µs), drapeaux, numéro (les 12 octets de l'ESP32 sans leur somme),
        poussée d'essai sur [roulis ; tangage] (2 × float32, N.m, jumeau seulement), somme des 20 premiers octets."""
        if d[0] != 0xA5 or d[1] != 0x5A or sum(d[:20]) % 256 != d[20]:
            return False
        self.poussee = list(struct.unpack_from("<2f", d, 12))
        imp = struct.unpack_from("<4H", d, 2)
        marche = d[10] & 1
        self.imp = [float(x) if marche else self.c["imp_neutre"] for x in imp]
        self.seq = d[11]
        return True

    def telemetrie(self):
        """Trame de télémétrie : celle de l'ESP32 (51 octets), puis les grandeurs réelles du jumeau (25 nombres)."""
        c = self.c
        etat = sum(1 << k for k in range(4) if self.arme[k])
        t_ms = int(round(self.pas * self.pas_ms)) & 0xFFFFFFFF
        d = struct.pack("<2BIBB3h3h4h3h4f", 0xB5, 0x5B, t_ms, etat, self.seq, *self.bno["euler"], *self.bno["gyro"],
                        *self.bno["quat"], *self.bno["acc"], *self.w_mes)
        d += bytes([sum(d) % 256])
        vrai = [math.degrees(x) for x in self.q] + [math.degrees(x) for x in self.dq] + self.w + self.i + self.Cm + self.V \
            + self.u + [sum(u * i for u, i in zip(self.u, self.i))]
        return d + struct.pack("<25f", *vrai)


def main():
    banc = Banc()
    liaison = Liaison()
    dire("jumeau Webots prêt. Lancer la simulation dans Simulink (procédé : Jumeau Webots).")
    while True:
        s, v = liaison.attendre_config()
        accord = banc.configurer(v)
        try:
            s.sendall(bytes([1 if accord else 0]))
            s.close()
        except OSError:
            accord = False
        if not accord or not liaison.ouvrir():
            continue
        dire(f"Simulink connecté (pivot {banc.c['pivot_mm']:g} mm, départ {banc.c['q0_roulis_deg']:g}° et "
              f"{banc.c['q0_tangage_deg']:g}°, une trame toutes les {banc.c['T_pont'] * 1000:g} ms).")
        en_marche = True
        while en_marche:
            try:
                liaison.telemetrie.sendall(banc.telemetrie())
            except OSError:
                break
            d = Liaison.lire(liaison.commande, N_COMMANDE)
            if d is None:
                break
            if not banc.lire_commande(d):
                dire("trame de commande invalide, ignorée")
            for _ in range(banc.n_pont):
                if not banc.avancer():
                    return
        liaison.fermer()
        dire(f"fin de la simulation à t = {banc.pas * banc.dt:.2f} s. En attente d'un nouveau lancement.")


if __name__ == "__main__":
    main()
