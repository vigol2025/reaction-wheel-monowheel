"""Liaisons d'assemblage SolidWorks (contraintes) à partir de la géométrie réelle des pièces.

Les composants sont insérés à leur place, puis seule la pièce de base reste fixe : chaque autre composant reçoit le
plus petit jeu de contraintes qui retire ses 6 degrés de liberté (5 pour un pivot qui garde sa rotation), cherché parmi
celles que donne la géométrie (faces planes en contact → coïncidence, cylindres de même axe → coaxiale, à rotation
bloquée ou non, plans parallèles écartés → distance) ; le compte se fait sur le rang de la jacobienne des contraintes,
avant de toucher à SolidWorks. Une coaxiale à rotation bloquée et une coïncidence suffisent à la plupart des pièces.
Les réglages du banc (hauteur d'axe, engagements des tubes, épaisseur du plateau) sont des contraintes de distance
nommées, à modifier dans SolidWorks. En dernier recours seulement, les plans de référence de la pièce sont liés à ceux
de l'assemblage. Chaque contrainte n'est gardée que si aucun composant ne bouge.

Repère : Transform2 donne la position de chaque composant par rapport à l'assemblage ouvert ; la géométrie des faces
est lue dans la pièce puis transformée (convention ligne : p' = p.R + t), en mm.
"""
import itertools
import types

import numpy as np
import pythoncom
import win32com.client

NUL = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)

COINC, COAX, PARAL, DIST, ANGLE = 0, 1, 3, 5, 6
ALIGNE, OPPOSE, PROCHE = 0, 1, 2             # swMateAlign : ALIGNED, ANTI_ALIGNED, CLOSEST
TOL_POS, TOL_ANG = 0.005, 1e-10              # mm, et écart des produits scalaires à ±1 (≈ 0,0008°)
NOMS_TYPES = {COINC: "coïncidence", COAX: "coaxiale", PARAL: "parallèle", DIST: "distance", ANGLE: "angle"}


def A(o, nom, *args):
    """Attribut COM en liaison dynamique : appelé s'il revient comme méthode, lu sinon."""
    a = getattr(o, nom)
    return a(*args) if isinstance(a, types.MethodType) else a


def transfo(comp):
    M = np.array(A(A(comp, "Transform2"), "ArrayData"))
    return M[:9].reshape(3, 3), M[9:12] * 1000.0


def feuilles(comp):
    enfants = A(comp, "GetChildren") or ()
    if not enfants:
        return [comp]
    return [f for e in enfants for f in feuilles(e)]


class Face:
    __slots__ = ("qui", "ent", "kind", "p", "n", "r", "aire", "lo", "hi", "nom")

    def __init__(self, qui, ent, kind, p, n, r=0.0, aire=0.0, lo=None, hi=None, nom=""):
        self.qui, self.ent, self.kind, self.p, self.n, self.r = qui, ent, kind, p, n, r
        self.aire, self.lo, self.hi, self.nom = aire, lo, hi, nom

    def __repr__(self):
        return f"<{self.kind} {self.qui} p={self.p.round(1)} n={self.n.round(3)} r={self.r:.2f}>"


def _boite(f, R, t):
    b = A(f, "GetBox")
    c = np.array([[b[i], b[j], b[k]] for i in (0, 3) for j in (1, 4) for k in (2, 5)]) * 1000.0
    c = c @ R + t
    return c.min(0), c.max(0)


def faces(comp):
    """Faces planes et cylindriques d'une pièce (tous ses corps), dans le repère de l'assemblage."""
    R, t = transfo(comp)
    qui = A(comp, "Name2")
    out = []
    corps = list(A(comp, "GetBodies2", 0) or ())          # tous les corps : une pièce importée peut en avoir plusieurs
    if not corps and A(comp, "GetBody") is not None:
        corps = [A(comp, "GetBody")]
    for f in (f for b in corps for f in (A(b, "GetFaces") or ())):
        s = A(f, "GetSurface")
        lo, hi = _boite(f, R, t)
        aire = A(f, "GetArea") * 1e6
        if A(s, "IsPlane"):
            q = A(s, "PlaneParams")
            n = np.array(A(f, "Normal"))                       # normale sortante de la face (pièce)
            out.append(Face(qui, f, "plan", np.array(q[3:6]) * 1000.0 @ R + t, n @ R, 0.0, aire, lo, hi))
        elif A(s, "IsCylinder"):
            q = A(s, "CylinderParams")
            a = np.array(q[3:6]) @ R
            out.append(Face(qui, f, "cyl", np.array(q[:3]) * 1000.0 @ R + t, a / np.linalg.norm(a), q[6] * 1000.0,
                            aire, lo, hi))
    return out


def plans_ref(objet, qui, R=None, t=None):
    """Trois premiers plans de référence (face, dessus, droite : normales Z, Y, X du repère propre) ; objet = composant
    (R, t donnés) ou document d'assemblage (repère de l'assemblage)."""
    out = []
    normales = [np.array([0.0, 0.0, 1.0]), np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 0.0])]
    f = A(objet, "FirstFeature")
    while f is not None and len(out) < 3:
        if A(f, "GetTypeName2") == "RefPlane":
            n = normales[len(out)]
            p = t.copy() if t is not None else np.zeros(3)
            out.append(Face(qui, f, "refplan", p, n @ R if R is not None else n, nom=A(f, "Name")))
        f = A(f, "GetNextFeature")
    return out


def origine(comp, qui, t, titre_asm):
    """Origine d'un composant (point de l'esquisse d'origine), pour une distance à un plan de l'assemblage ;
    sélectionnée par son nom « Point1@Origine@composant@assemblage »."""
    f = A(comp, "FirstFeature")
    while f is not None:
        if A(f, "GetTypeName2") == "OriginProfileFeature":
            nom = f"Point1@{A(f, 'Name')}@{qui}@{titre_asm}"
            return Face(qui, ("EXTSKETCHPOINT", nom), "point", t.copy(), np.zeros(3), nom=nom)
        f = A(f, "GetNextFeature")
    return None


def trouver(F, kind, n=None, p=None, r=None, tol=0.05):
    """Faces de F d'un type donné, de normale ou d'axe n (au signe près pour les cylindres), passant par p, de rayon r."""
    out = []
    for f in F:
        if f.kind != kind:
            continue
        if n is not None:
            d = f.n @ np.asarray(n, float)
            if (kind == "cyl" and abs(abs(d) - 1) > 1e-4) or (kind != "cyl" and d < 1 - 1e-4):
                continue
        if p is not None:
            w = np.asarray(p, float) - f.p
            e = abs(w @ f.n) if kind != "cyl" else np.linalg.norm(w - (w @ f.n) * f.n)
            if e > tol:
                continue
        if r is not None and abs(f.r - r) > tol:
            continue
        out.append(f)
    return sorted(out, key=lambda f: -f.aire)


# ------------------------------------------------------------------ degrés de liberté (jacobienne des contraintes)
def _base(d):
    e1 = np.cross(d, [1.0, 0, 0]) if abs(d[0]) < 0.9 else np.cross(d, [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(d, e1)


def lignes(typ, fm, fp, centre, verrou=False):
    """Équations linéarisées, torseur (ω, v) de la pièce mobile, positions rapportées à son centre (en m)."""
    out = []
    if typ == COAX:
        d, p = fm.n, (fm.p - centre) / 1000.0
        for e in _base(d):
            out.append(np.r_[np.cross(d, e), 0, 0, 0])
            out.append(np.r_[np.cross(p, e), e])
        if verrou:
            out.append(np.r_[d, 0, 0, 0])
    elif typ in (COINC, DIST):
        if fm.kind in ("cyl", "point"):                     # distance d'un axe ou d'un point à un plan
            n, p = fp.n, (fm.p - centre) / 1000.0
            out.append(np.r_[np.cross(p, n), n])
        else:
            n, p = fm.n, (fm.p - centre) / 1000.0
            for e in _base(n):
                out.append(np.r_[np.cross(n, e), 0, 0, 0])
            out.append(np.r_[np.cross(p, n), n])
    elif typ == PARAL:
        for e in _base(fm.n):
            out.append(np.r_[np.cross(fm.n, e), 0, 0, 0])
    elif typ == ANGLE:
        c = np.cross(fm.n, fp.n)
        out.append(np.r_[c / max(np.linalg.norm(c), 1e-12), 0, 0, 0])
    return out


def rang(L):
    return int(np.linalg.matrix_rank(np.array(L), tol=1e-6)) if L else 0


# ------------------------------------------------------------------ candidats géométriques
def _chevauche(a, b, marge=0.2):
    return bool(np.all(a.lo - marge <= b.hi) and np.all(b.lo - marge <= a.hi))


def _intervalle(p, d, lo, hi):
    c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    s = (c - p) @ d
    return s.min(), s.max()


def candidats(FM, FP, ordre=None):
    """[(priorité, type, face mobile, face partenaire, valeur)], la plus petite priorité d'abord ; à priorité égale,
    le partenaire déclaré le premier (ordre : nom -> rang) passe avant les autres."""
    ordre = ordre or {}
    out = []
    cyl_m = [f for f in FM if f.kind == "cyl" and f.r > 0.4]
    cyl_p = [f for f in FP if f.kind == "cyl" and f.r > 0.4]
    for c in cyl_m:
        for q in cyl_p:
            if abs(abs(c.n @ q.n) - 1) > TOL_ANG:
                continue
            w = q.p - c.p
            if np.linalg.norm(w - (w @ c.n) * c.n) > TOL_POS:
                continue
            a0, a1 = _intervalle(c.p, c.n, c.lo, c.hi)
            b0, b1 = _intervalle(c.p, c.n, q.lo, q.hi)
            recouvre = min(a1, b1) - max(a0, b0) > -0.2
            out.append(((0 if recouvre else 2, ordre.get(q.qui, 9), round(abs(c.r - q.r), 2), -c.r), COAX, c, q, 0.0))
    pl_m = [f for f in FM if f.kind == "plan" and f.aire > 1.0]
    pl_p = [f for f in FP if f.kind == "plan" and f.aire > 1.0]
    for f in pl_m:
        for g in pl_p:
            dot = f.n @ g.n
            if abs(abs(dot) - 1) > TOL_ANG:
                continue
            ecart = (f.p - g.p) @ g.n
            if abs(ecart) <= TOL_POS:
                contact = dot < 0 and _chevauche(f, g)
                out.append(((1 if contact else 3, ordre.get(g.qui, 9), -min(f.aire, g.aire), 0), COINC, f, g, 0.0))
            else:
                proche = _chevauche(f, g, marge=abs(ecart) + 1.0)
                out.append(((4 if proche else 5, ordre.get(g.qui, 9), abs(ecart), 0), DIST, f, g, abs(ecart)))
    out.sort(key=lambda c: c[0])
    return out


# ------------------------------------------------------------------ création des contraintes dans SolidWorks
class Lieur:
    def __init__(self, sw, asm, journal=print):
        self.sw, self.asm, self.journal = sw, asm, journal
        self.sm = A(asm, "SelectionManager")
        self.ref0 = {}                                   # positions initiales des composants : contrôle
        self.liste = []                                  # (composant, type, partenaire, valeur, nom, verrou)
        self.bavard = False

    def memoriser(self):
        for c in A(self.asm, "GetComponents", False):
            self.ref0[A(c, "Name2")] = transfo(c)

    def bouge(self):
        """Composants déplacés par rapport à leur place d'origine : [(nom, écart en mm)]."""
        out = []
        for c in A(self.asm, "GetComponents", False):
            nom = A(c, "Name2")
            if nom not in self.ref0:
                continue
            R, t = transfo(c)
            R0, t0 = self.ref0[nom]
            e = max(np.abs(t - t0).max(), np.abs(R - R0).max() * 100)     # rotation : bras de levier de 100 mm
            if e > 0.01:
                out.append((nom, round(float(e), 3)))
        return out

    def _selectionner(self, ent, est_feature):
        if isinstance(ent, tuple):                       # (type, nom) : sélection par le nom
            return A(A(self.asm, "Extension"), "SelectByID2", ent[1], ent[0], 0.0, 0.0, 0.0, True, 1, NUL, 0)
        if est_feature:
            return A(ent, "Select2", True, 1)
        sd = A(self.sm, "CreateSelectData")
        sd.Mark = 1
        return A(ent, "Select4", True, sd)

    def contrainte(self, typ, f1, f2, valeur=0.0, inverser=False, verrou=False, nom=None, angle=0.0, sup=0.0,
                   inf=0.0, alignement=PROCHE):
        """Contrainte entre deux faces (ou plans de référence) ; valeur en mm, angles en rad."""
        A(self.asm, "ClearSelection2", True)
        ok = (self._selectionner(f1.ent, f1.kind in ("refplan", "point"))
              and self._selectionner(f2.ent, f2.kind in ("refplan", "point")))
        if not ok:
            A(self.asm, "ClearSelection2", True)
            return None
        err = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        if self.bavard:
            self.journal(f"      essai {NOMS_TYPES[typ]} {f1.qui} / {f2.qui} {valeur:.2f} inv={inverser} verrou={verrou}", flush=True)
        lim_d = (sup / 1000.0, inf / 1000.0) if typ == DIST else (0.0, 0.0)
        lim_a = (sup, inf) if typ == ANGLE else (0.0, 0.0)
        m = self.asm.AddMate5(typ, alignement, inverser, valeur / 1000.0, lim_d[0], lim_d[1], 0.0, 0.0, angle,
                              lim_a[0], lim_a[1], False, verrou, 0, err)
        A(self.asm, "ClearSelection2", True)
        if m is None or err.value != 1:
            self.derniere_erreur = err.value          # swAddMateError : 2 type, 3 alignement, 4 sélection, 5 surcontraint
            if m is not None:                         # créée malgré l'erreur : on l'enlève
                f = self.derniere()
                if f is not None:
                    self.supprimer(f)
            return None
        f = self.derniere()                           # la fonction de la contrainte (IMate2 ne se sélectionne pas)
        if nom and f is not None:
            try:
                f.Name = nom
            except Exception:
                pass
        return f

    def groupe(self):
        f = A(self.asm, "FirstFeature")
        while f is not None:
            if A(f, "GetTypeName2") == "MateGroup":
                return f
            f = A(f, "GetNextFeature")
        return None

    def derniere(self):
        """Dernière contrainte du dossier des contraintes (la plus récente)."""
        g = self.groupe()
        m, der = (A(g, "GetFirstSubFeature") if g is not None else None), None
        while m is not None:
            der = m
            m = A(m, "GetNextSubFeature")
        return der

    def nombre(self):
        g = self.groupe()
        m, n = (A(g, "GetFirstSubFeature") if g is not None else None), 0
        while m is not None:
            n += 1
            m = A(m, "GetNextSubFeature")
        return n

    def supprimer(self, f):
        n0 = self.nombre()
        A(self.asm, "ClearSelection2", True)
        A(f, "Select2", False, 0)
        A(self.asm, "EditDelete")
        A(self.asm, "ClearSelection2", True)
        if self.nombre() != n0 - 1:
            self.journal(f"  ! suppression de contrainte impossible : {A(f, 'Name')}", flush=True)

    def essayer(self, typ, f1, f2, valeur=0.0, verrou=False, nom=None, **kw):
        """Contrainte gardée seulement si aucun composant ne bouge ; une distance est essayée dans les deux sens.
        Entre deux faces planes, l'alignement suit les normales actuelles (alignées ou opposées)."""
        if "alignement" not in kw and f1.kind in ("plan", "refplan") and f2.kind in ("plan", "refplan")                 and typ in (COINC, DIST, PARAL):
            kw["alignement"] = ALIGNE if f1.n @ f2.n > 0 else OPPOSE
        for inverser in ((False, True) if typ == DIST else (False,)):
            m = self.contrainte(typ, f1, f2, valeur, inverser, verrou, nom, **kw)
            if m is None:
                if self.bavard:
                    self.journal(f"        refusée par SolidWorks (code {getattr(self, 'derniere_erreur', '?')})", flush=True)
                continue
            b = self.bouge()
            if not b:
                return m
            if self.bavard:
                self.journal(f"        bouge : {b[:3]}", flush=True)
            self.supprimer(m)
        return None


def reserve(FM, FP, ordre=None, tourne=True, refs_m=(), refs_asm=(), point=None):
    """Contraintes possibles d'un composant : [(type, face mobile, face partenaire, valeur, verrou, options)] et le nombre
    des physiques, en tête (faces en contact, coaxiales, dans l'ordre des candidats ; une coaxiale à rotation bloquée
    passe avant la même sans blocage) ; puis celles de repli, sur les plans de l'assemblage : plans de référence
    coïncidents ou à distance, origine de la pièce, plans parallèles, angle."""
    phys = []
    for prio, typ, fm, fp, valeur in candidats(FM, FP, ordre):
        if typ == COAX and tourne:
            phys.append((COAX, fm, fp, 0.0, True, {}))
        phys.append((typ, fm, fp, valeur, False, {}))
    plans, para, angles = [], [], []
    for fm in refs_m:
        for fp in refs_asm:
            c = float(np.clip(fm.n @ fp.n, -1, 1))
            if abs(abs(c) - 1) <= TOL_ANG:
                ecart = abs((fm.p - fp.p) @ fp.n)
                plans.append((COINC, fm, fp, 0.0, False, {}) if ecart <= TOL_POS else (DIST, fm, fp, ecart, False, {}))
                para.append((PARAL, fm, fp, 0.0, False, {}))
            else:
                angles.append((ANGLE, fm, fp, 0.0, False, {"angle": float(np.arccos(c))}))
    origine_pl = []
    if point is not None:
        for fp in refs_asm:
            ecart = (point.p - fp.p) @ fp.n
            origine_pl.append((COINC, point, fp, 0.0, False, {}) if abs(ecart) <= TOL_POS
                              else (DIST, point, fp, abs(ecart), False, {}))
    return phys + plans + origine_pl + para + angles, len(phys)


def _projecteur(rows):
    u, s, vt = np.linalg.svd(np.array(rows))
    v = vt[:int((s > 1e-6).sum())]
    return v.T @ v


def plan_minimal(J, R, centre, cible, xi=None, exclus=(), fin=None, kmax=4, largeur=60):
    """Plus petit jeu de contraintes de R (indices, dans l'ordre de R) qui porte le rang de J à la cible, sans gêner
    le pivot xi ; à nombre égal, le premier dans l'ordre de R. Une contrainte qui bloque exactement les mêmes
    mouvements qu'une précédente (autre face du même cylindre ou du même plan) n'est pas retenue. Une coaxiale à
    rotation bloquée est remplacée par la même sans blocage quand le jeu n'en a pas besoin. None si aucun jeu n'existe
    avec au plus kmax contraintes."""
    base = rang(J)
    utiles, vus = [], []
    for i, (typ, fm, fp, valeur, verrou, kw) in enumerate(R[:fin]):
        if i in exclus:
            continue
        rows = lignes(typ, fm, fp, centre, verrou)
        if xi is not None and any(abs(r @ xi) > 1e-6 for r in rows):
            continue
        if rang(J + rows) <= base:
            continue
        P = _projecteur(rows)
        if any(np.allclose(P, Q, atol=1e-6) for Q in vus):
            continue
        vus.append(P)
        utiles.append((i, rows))
        if len(utiles) >= largeur:
            break
    for k in range(1, min(kmax, cible - base) + 1):
        for combo in itertools.combinations(utiles, k):
            if rang(J + [r for _, rows in combo for r in rows]) >= cible:
                plan = [i for i, _ in combo]
                for n, i in enumerate(plan):
                    typ, fm, fp, valeur, verrou, kw = R[i]
                    if not verrou or i + 1 >= len(R) or R[i + 1][:3] != (COAX, fm, fp) or i + 1 in exclus:
                        continue
                    autres = [r for j in plan if j != i for r in lignes(*R[j][:3], centre, R[j][4])]
                    if rang(J + autres + lignes(COAX, fm, fp, centre)) >= cible:
                        plan[n] = i + 1
                return plan
    return None


def lier_composant(L, nom, FM, FP, pivot=None, speciales=(), refs_m=(), refs_asm=(), point=None, ordre=None):
    """Contraint un composant (faces FM) sur ses partenaires (faces FP) avec le moins de contraintes possible.
    pivot = (point, direction) : rotation laissée libre. speciales = [(type, face mobile, face partenaire, valeur, nom
    [, verrou])]
    posées d'abord (réglages). Les contraintes physiques sont préférées à celles de repli, même plus nombreuses."""
    centre = np.mean([f.p for f in FM], 0) if FM else np.zeros(3)
    J, poses = [], []
    cible = 5 if pivot is not None else 6
    xi_pivot = None
    if pivot is not None:
        p, d = np.asarray(pivot[0], float), np.asarray(pivot[1], float)
        xi_pivot = np.r_[d, np.cross((p - centre) / 1000.0, d)]

    def tenter(typ, fm, fp, valeur, nom_c=None, verrou=False, **kw):
        rows = lignes(typ, fm, fp, centre, verrou)
        if rang(J + rows) <= rang(J):
            return None
        if xi_pivot is not None and any(abs(r @ xi_pivot) > 1e-6 for r in rows):
            return None
        m = L.essayer(typ, fm, fp, valeur, verrou=verrou, nom=nom_c, **kw)
        if m is None:
            return None
        J.extend(rows)
        poses.append([typ, fm, fp, valeur, nom_c, verrou, m])
        return m

    for typ, fm, fp, valeur, nom_c, *verrou in speciales:
        if tenter(typ, fm, fp, valeur, nom_c, verrou=bool(verrou and verrou[0])) is None:
            L.journal(f"  ! réglage refusé pour {nom} : {nom_c}")
    R, n_phys = reserve(FM, FP, ordre, pivot is None, refs_m, refs_asm, point)
    exclus = set()
    for _ in range(30):
        if rang(J) >= cible:
            break
        plan = (plan_minimal(J, R, centre, cible, xi_pivot, exclus, fin=n_phys)
                or plan_minimal(J, R, centre, cible, xi_pivot, exclus, kmax=3))
        for c in range(cible - 1, rang(J), -1):       # pas de jeu complet : la contrainte qui retire le plus d'abord
            if plan is not None:
                break
            plan = plan_minimal(J, R, centre, c, xi_pivot, exclus, kmax=1)
        if plan is None:
            break
        j0, n0 = len(J), len(poses)
        for i in plan:
            typ, fm, fp, valeur, verrou, kw = R[i]
            if tenter(typ, fm, fp, valeur, verrou=verrou, **kw) is None:
                exclus.add(i)                         # refusée ou fait bouger une pièce : on défait ce jeu et on recommence
                for pose in poses[n0:]:
                    L.supprimer(pose[6])
                del poses[n0:], J[j0:]
                break
    for typ, fm, fp, valeur, nom_c, verrou, m in poses:
        L.liste.append((nom, NOMS_TYPES[typ] + (" (rotation bloquée)" if verrou else ""), fp.qui,
                        round(float(valeur), 2), nom_c or "", fm.kind, fp.kind))
    return rang(J), poses
