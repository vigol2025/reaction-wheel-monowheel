"""Construction de pièces SolidWorks natives par l'API COM (pywin32).

Les formes sont données dans le repère du banc (mm) : X le long du bord de table, Y vers le haut,
Z vers l'extérieur de la table. Chaque pièce a sa propre origine ; les coordonnées sont converties
en repère pièce, puis en repère d'esquisse selon le plan choisi :
  face   : (u, v) = (X, Y), profondeur selon +Z, esquisse (x, y) = (X, Y)
  dessus : (u, v) = (X, Z), profondeur selon +Y, esquisse (x, y) = (X, -Z)
  droite : (u, v) = (Z, Y), profondeur selon +X, esquisse (x, y) = (-Z, Y)
"""
import math

import pythoncom
import win32com.client
import win32com.client.dynamic

NUL = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
PLANS = {"face": "Plan de face", "dessus": "Plan de dessus", "droite": "Plan de droite"}


def application():
    """Instance SolidWorks en liaison dynamique (les liaisons typées makepy changent la signature des appels). Une
    session visible est celle de l'utilisateur : les scripts ferment tous les documents, ils refusent donc de s'y
    attacher."""
    sw = win32com.client.dynamic.Dispatch("SldWorks.Application")
    assert not sw.Visible, "une session SolidWorks visible est ouverte : la fermer d'abord"
    return sw


def conges(poly, rayons):
    """Polygone (u, v) et rayon par sommet -> segments ('l', p1, p2) et arcs ('a', centre, p1, p2, sens)."""
    n = len(poly)
    if not isinstance(rayons, (list, tuple)):
        rayons = [rayons] * n
    aire = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    trigo = 1 if aire > 0 else -1
    coins = []
    for i in range(n):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % n]
        r = rayons[i]
        if r <= 0:
            coins.append((p1, p1, None, 0))
            continue
        a = (p0[0] - p1[0], p0[1] - p1[1])
        b = (p2[0] - p1[0], p2[1] - p1[1])
        la, lb = math.hypot(*a), math.hypot(*b)
        a, b = (a[0] / la, a[1] / la), (b[0] / lb, b[1] / lb)
        ang = math.acos(max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1])))
        t = r / math.tan(ang / 2)
        ta = (p1[0] + a[0] * t, p1[1] + a[1] * t)
        tb = (p1[0] + b[0] * t, p1[1] + b[1] * t)
        bis = (a[0] + b[0], a[1] + b[1])
        lbis = math.hypot(*bis)
        h = r / math.sin(ang / 2)
        c = (p1[0] + bis[0] / lbis * h, p1[1] + bis[1] / lbis * h)
        croix = (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0])
        coins.append((ta, tb, c, 1 if croix > 0 else -1))   # +1 : arc parcouru dans le sens trigonométrique
    segs = []
    for i in range(n):
        ta, tb, c, s = coins[i]
        if c is not None:
            segs.append(("a", c, ta, tb, s))
        suivant = coins[(i + 1) % n][0]
        if math.hypot(suivant[0] - tb[0], suivant[1] - tb[1]) > 1e-9:
            segs.append(("l", tb, suivant))
    return segs


class Piece:
    def __init__(self, sw, origine=(0.0, 0.0, 0.0)):
        self.sw = sw
        self.d = sw.NewDocument(sw.GetUserPreferenceStringValue(8), 0, 0, 0)
        self.o = origine
        self.sm = self.d.SketchManager
        self.sm.AddToDB = True
        self.fm = self.d.FeatureManager

    # -- conversions repère banc -> repère pièce -> repère d'esquisse
    def _local(self, plan, u, v):
        ox, oy, oz = self.o
        if plan == "face":
            return u - ox, v - oy
        if plan == "dessus":
            return u - ox, v - oz
        return u - oz, v - oy

    def _prof(self, plan, w):
        ox, oy, oz = self.o
        return w - {"face": oz, "dessus": oy, "droite": ox}[plan]

    def _pt(self, plan, p):
        u, v = self._local(plan, *p)
        x, y = {"face": (u, v), "dessus": (u, -v), "droite": (-u, v)}[plan]
        return x / 1000.0, y / 1000.0

    # -- esquisses
    def _esquisse(self, plan, formes):
        self.d.ClearSelection2(True)
        assert self.d.Extension.SelectByID2(PLANS[plan], "PLANE", 0, 0, 0, False, 0, NUL, 0), plan
        self.sm.InsertSketch(True)
        for f in formes:
            if f[0] == "cercle":
                x, y = self._pt(plan, f[1])
                self.sm.CreateCircleByRadius(x, y, 0, f[2] / 1000.0)
            elif f[0] == "rect":
                (u0, v0), (u1, v1) = f[1], f[2]
                self._contour(plan, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], f[3] if len(f) > 3 else 0)
            elif f[0] == "poly":
                self._contour(plan, f[1], f[2] if len(f) > 2 else 0)
        self.sm.InsertSketch(True)

    def _contour(self, plan, poly, rayons):
        miroir = -1 if plan in ("dessus", "droite") else 1
        for s in conges(poly, rayons):
            if s[0] == "l":
                (x1, y1), (x2, y2) = self._pt(plan, s[1]), self._pt(plan, s[2])
                self.sm.CreateLine(x1, y1, 0, x2, y2, 0)
            else:
                c, a, b, sens = s[1:]
                (xc, yc), (x1, y1), (x2, y2) = self._pt(plan, c), self._pt(plan, a), self._pt(plan, b)
                self.sm.CreateArc(xc, yc, 0, x1, y1, 0, x2, y2, 0, sens * miroir)

    # -- fonctions volumiques, bornées en profondeur entre w0 et w1 (repère banc)
    def _depart(self, plan, w):
        """Plan de départ décalé de w (repère banc) : condition de départ, décalage, inversion."""
        a = self._prof(plan, w)
        return (3 if abs(a) > 1e-9 else 0), abs(a) / 1000.0, a < 0

    def extrusion(self, plan, formes, w0, w1, nom=None):
        """Bossage entre w0 et w1 : départ à la borne basse, extrusion selon +normale."""
        self._esquisse(plan, formes)
        w0, w1 = sorted((w0, w1))
        t0, dec, inv = self._depart(plan, w0)
        f = self.fm.FeatureExtrusion3(True, False, False, 0, 0, (w1 - w0) / 1000.0, 0, False, False, False, False, 0, 0,
                                      False, False, False, False, True, True, True, t0, dec, inv)
        assert f is not None, ("extrusion", nom)
        if nom:
            f.Name = nom
        return f

    def enlevement(self, plan, formes, w0, w1, nom=None):
        """Enlèvement entre w0 et w1 : départ à la borne haute, enlèvement selon -normale (sens par défaut,
        vérifié indépendant de la position de la matière)."""
        self._esquisse(plan, formes)
        w0, w1 = sorted((w0, w1))
        t0, dec, inv = self._depart(plan, w1)
        f = self.fm.FeatureCut4(True, False, False, 0, 0, (w1 - w0) / 1000.0, 0, False, False, False, False, 0, 0,
                                False, False, False, False, False, True, True, False, False, False, t0, dec, inv, False)
        assert f is not None, ("enlèvement", nom)
        if nom:
            f.Name = nom
        return f

    # -- contrôle et finitions
    def boite(self):
        """Boîte englobante en repère banc (mm)."""
        b = [v * 1000 for v in self.d.GetPartBox(True)]
        ox, oy, oz = self.o
        return [round(b[0] + ox, 2), round(b[1] + oy, 2), round(b[2] + oz, 2),
                round(b[3] + ox, 2), round(b[4] + oy, 2), round(b[5] + oz, 2)]

    def volume(self):
        return self.d.Extension.CreateMassProperty.Volume * 1e9

    def proprietes(self, **kv):
        cpm = self.d.Extension.CustomPropertyManager("")
        for k, v in kv.items():
            cpm.Add3(k, 30, str(v), 2)

    def matiere(self, noms=("6061-T6 (SS)", "Alliage 6061", "6061 Alloy")):
        for n in noms:
            self.d.SetMaterialPropertyName2("", "", n)
            base = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, "")
            nom = self.d.GetMaterialPropertyName2("", base)
            if nom:
                return nom
        return None

    def enregistrer(self, chemin, step=None):
        assert self.d.SaveAs3(chemin, 0, 1) == 0, chemin
        if step:
            self.d.SaveAs3(step, 0, 3)

    def fermer(self):
        self.sw.CloseDoc(self.d.GetTitle)


class PieceImportee(Piece):
    """Pièce dont la géométrie vient d'un STEP construit hors de SolidWorks (dans le repère du banc), importée comme
    corps solide. 3D Interconnect est coupé le temps de l'import, sinon la pièce resterait liée au STEP."""

    def __init__(self, sw, step):
        self.sw = sw
        avant = sw.GetUserPreferenceToggle(691)            # swMultiCAD_Enable3DInterconnect
        sw.SetUserPreferenceToggle(691, False)
        try:
            err = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            self.d = sw.LoadFile4(step, "r", sw.GetImportFileData(step), err)
        finally:
            sw.SetUserPreferenceToggle(691, avant)
        assert self.d is not None, (step, err.value)
        self.o = (0.0, 0.0, 0.0)
        self.sm = self.d.SketchManager
        self.fm = self.d.FeatureManager
