"""Pose des contraintes d'un assemblage ouvert, d'après des règles (liaisons.py fait la géométrie et les degrés de
liberté). Règle : (préfixe du composant, préfixes des partenaires, porteurs, pivot, réglages), dans l'ordre de pose.
- porteurs : préfixes des pièces d'un sous-ensemble utilisées pour le contraindre (None : toutes ses pièces) ;
- pivot : (point, direction) en mm dans le repère de l'assemblage, rotation laissée libre ;
- réglages : fonction (faces du composant, faces des partenaires[, plans de l'assemblage]) -> [(type, face, face, valeur,
  nom)] ;
- en option, un 6e terme : fonction (rotation, translation en mm du composant) -> clé de tri, pour imposer l'ordre de pose
  des composants de la règle (un écrou ne s'appuie sur le précédent que si celui-ci est déjà posé).
"""
import time

from liaisons import A, Lieur, faces, feuilles, lier_composant, origine, plans_ref, transfo
from swbuild import NUL


def contraindre(sw, asm, base, regles, journal=print, souples=(), bavard=False):
    """base : préfixe du composant fixe. souples : préfixes des sous-ensembles rendus flexibles (pivots internes)."""
    L = Lieur(sw, asm, journal)
    L.bavard = bavard
    comps = {A(c, "Name2"): c for c in A(asm, "GetComponents", True)}
    A(asm, "ClearSelection2", True)
    for n, c in comps.items():
        if not n.startswith(base) and A(c, "IsFixed"):
            A(c, "Select4", True, NUL, False)
    A(asm, "UnfixComponent")
    A(asm, "ClearSelection2", True)
    for n, c in comps.items():                                # la base est la seule pièce fixe
        if n.startswith(base) and not A(c, "IsFixed"):
            A(c, "Select4", True, NUL, False)
    A(asm, "FixComponent")
    A(asm, "ClearSelection2", True)
    for n, c in comps.items():
        if n.startswith(tuple(souples)):
            c.Solving = 1                                     # swComponentFlexibleSolving
    L.memoriser()
    cache = {}

    def faces_de(feuille):
        k = A(feuille, "Name2")
        if k not in cache:
            cache[k] = faces(feuille)
        return cache[k]

    poses = [n for n in comps if n.startswith(base)]
    refs_asm = plans_ref(asm, "assemblage")
    titre = A(asm, "GetTitle").rsplit(".", 1)[0] if A(asm, "GetTitle").upper().endswith(".SLDASM") else A(asm, "GetTitle")
    bilan = []
    for regle in regles:
        prefixe, partenaires, porteurs, pivot, reglages = regle[:5]
        noms = [n for n in comps if n.startswith(prefixe) and n not in poses]
        if len(regle) > 5 and regle[5]:                       # ordre de pose imposé : clé (R, t) -> valeur triable
            noms.sort(key=lambda n: regle[5](*transfo(comps[n])))
        for n in noms:
            c = comps[n]
            fl = [f for f in feuilles(c) if porteurs is None or A(f, "Name2").split("/", 1)[-1].startswith(tuple(porteurs))]
            FM = [x for f in fl for x in faces_de(f)]
            FP, ordre = [], {}
            for p in poses:
                for f in feuilles(comps[p]):
                    nf = A(f, "Name2")
                    rangs = [i for i, pre in enumerate(partenaires) if nf.startswith(pre)]
                    if rangs:
                        FP += faces_de(f)
                        ordre[nf] = rangs[0]
            t0 = time.time()
            R, t = transfo(c)
            refs_m = plans_ref(c, n, R, t)
            spec = ((reglages(FM, FP, refs_asm) if reglages.__code__.co_argcount >= 3 else reglages(FM, FP))
                    if reglages else ())
            rg, faits = lier_composant(L, n, FM, FP, pivot, spec, refs_m, refs_asm, origine(c, n, t, titre), ordre)
            bilan.append((n, rg, len(faits)))
            journal(f"  {n:34s} rang {rg} / {5 if pivot is not None else 6}, {len(faits)} contraintes"
                    f" ({time.time() - t0:.0f} s)", flush=True)
            poses.append(n)
    A(asm, "EditRebuild3")
    return L, bilan
