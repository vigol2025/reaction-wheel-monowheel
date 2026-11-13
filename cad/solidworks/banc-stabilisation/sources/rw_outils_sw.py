"""Outils SolidWorks du banc de stabilisation : ouverture, insertion d'un composant à sa place, rapport des
contraintes, butées d'angle. Repris des scripts du banc 2DDL (PFE HEI5)."""
import numpy as np
import pythoncom
import win32com.client
from win32com.client import gencache

from liaisons import ANGLE, A, plans_ref, transfo

TYPES = gencache.EnsureModule("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 33, 0)   # sldworks.tlb (makepy)
ID = np.eye(3)


def repere(z_dir, x_dir):
    """Rotation (vecteurs colonnes) dont les axes locaux x et z vont selon x_dir et z_dir ; y = z × x."""
    z = np.asarray(z_dir, float) / np.linalg.norm(z_dir)
    x = np.asarray(x_dir, float) / np.linalg.norm(x_dir)
    return np.column_stack([x, np.cross(z, x), z])


def transform(sw, R, t):
    """MathTransform SolidWorks : 9 termes de rotation (convention ligne, p' = p.M), translation en m, échelle."""
    R = np.asarray(R, float)
    data = [R[0][0], R[1][0], R[2][0], R[0][1], R[1][1], R[2][1], R[0][2], R[1][2], R[2][2],
            t[0] / 1000.0, t[1] / 1000.0, t[2] / 1000.0, 1.0, 0.0, 0.0, 0.0]
    mu = TYPES.IMathUtility(sw.GetMathUtility._oleobj_)       # l'appel non typé fait planter SolidWorks
    tr = mu.CreateTransform(win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in data]))
    return getattr(tr, "_oleobj_", tr)


def ouvrir(sw, chemin, lecture=False):
    e = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    typ = 2 if chemin.upper().endswith(".SLDASM") else 1
    d = sw.OpenDoc6(chemin, typ, 1 | (2 if lecture else 0), "", e, w)
    assert d is not None, (chemin, e.value)
    return d


def nouvel_assemblage(sw):
    return sw.NewDocument(sw.GetUserPreferenceStringValue(9), 0, 0, 0)


def ajouter(sw, asm, chemin, R, t):
    ouvrir(sw, chemin)
    err = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    sw.ActivateDoc3(asm.GetTitle, False, 0, err)        # l'assemblage doit être le document actif
    comp = asm.AddComponent5(chemin, 0, "", False, "", t[0] / 1000.0, t[1] / 1000.0, t[2] / 1000.0)
    assert comp is not None, chemin
    comp.Transform2 = transform(sw, R, t)
    return comp


def rapport(L, titre):
    print(f"{titre} : {len(L.liste)} contraintes", flush=True)
    for comp, typ, partenaire, valeur, nom, k1, k2 in L.liste:
        print(f"    {comp:30s} {typ:28s} avec {partenaire:34s} {valeur if valeur else '':>7} {nom}")
    b = L.bouge()
    print("  composants déplacés :", b if b else "aucun", flush=True)
    return b


def composant(asm, prefixe):
    for c in A(asm, "GetComponents", False):
        if A(c, "Name2").startswith(prefixe):
            return c
    raise KeyError(prefixe)


def butee(L, asm, mobile, reference, axe, limites, nom):
    """Contrainte d'angle limite entre un plan de référence de la pièce mobile et un de la pièce de référence, tous deux
    parallèles à l'axe de rotation ; angle au repos le plus proche de 90° ; limites issues des rotations extrêmes."""
    cm, cr = composant(asm, mobile), composant(asm, reference)
    Rm, tm = transfo(cm)
    Rr, tr = transfo(cr)
    u = np.asarray(axe, float)
    pm = [f for f in plans_ref(cm, A(cm, "Name2"), Rm, tm) if abs(f.n @ u) < 1e-6]
    pr = [f for f in plans_ref(cr, A(cr, "Name2"), Rr, tr) if abs(f.n @ u) < 1e-6]
    fm, fr = min(((a, b) for a in pm for b in pr), key=lambda ab: abs(np.degrees(np.arccos(np.clip(ab[0].n @ ab[1].n, -1, 1))) - 90))

    def angle(phi):
        a = np.radians(phi)
        K = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
        Ru = np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K
        return float(np.degrees(np.arccos(np.clip((Ru @ fm.n) @ fr.n, -1, 1))))
    a0, a1, a2 = angle(0.0), angle(limites[0]), angle(limites[1])
    lo, hi = min(a1, a2, a0), max(a1, a2, a0)
    m = L.essayer(ANGLE, fm, fr, 0.0, nom=nom, angle=np.radians(a0), sup=np.radians(hi), inf=np.radians(lo))
    L.journal(f"  {nom} : plans {fm.nom} / {fr.nom}, {a0:.1f}° au repos, limites {lo:.1f}° à {hi:.1f}° :"
              f" {'posée' if m is not None else 'REFUSÉE'}")
    if m is not None:
        L.liste.append((mobile, "angle limite", reference, round(a0, 1), nom, "refplan", "refplan"))
    return m
