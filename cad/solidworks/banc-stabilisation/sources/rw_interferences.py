"""Détection d'interférences de SolidWorks sur Banc_stabilisation.SLDASM rouvert (pièces de tous les niveaux), avec les
vrais modèles (A2212 et disques d'origine). Les recouvrements voulus sont classés à part : goupilles emmanchées
Ø3 dans des trous Ø2,9, disque Ø3,19 serré sur l'arbre Ø3,2, pièces internes des modèles du commerce.

Usage : python -I rw_interferences.py   (SolidWorks fermé)
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from liaisons import A
from rw_outils_sw import ouvrir
from swbuild import application

VOULUS = (("RW-24_Goupille", "RW-06_Croisillon"), ("RW-24_Goupille", "RW-05_Collier"), ("disque", "A2212"))


def voulu(a, b):
    for x, y in VOULUS:
        if (x in a and y in b) or (x in b and y in a):
            return True
    return a.split("/")[:-1] == b.split("/")[:-1] and ("A2212" in a or "disque_vis" in a)


def main():
    sw = application()
    try:
        asm = ouvrir(sw, os.path.join(os.path.dirname(ICI), "Banc_stabilisation.SLDASM"))
        A(asm, "ForceRebuild3", False)
        idm = asm.InterferenceDetectionManager
        idm.TreatCoincidenceAsInterference = False
        idm.TreatSubAssembliesAsComponents = False
        idm.IncludeMultibodyPartInterferences = False
        inter = idm.GetInterferences or []
        defauts, attendus = [], []
        for it in inter:
            noms = [c.Name2 for c in it.Components]
            v = round(it.Volume * 1e9, 2)
            (attendus if voulu(*noms) else defauts).append((noms, v))
        idm.Done()
        print(f"interférences : {len(inter)} ; voulues (emmanchements, modèles du commerce) : {len(attendus)} ; à corriger : {len(defauts)}")
        for n, v in defauts:
            print("   À CORRIGER", n, v, "mm3")
        for n, v in attendus:
            print("   voulue", n, v, "mm3")
    finally:
        sw.CloseAllDocuments(True)
        try:
            sw.ExitApp()
        except Exception:
            pass


if __name__ == "__main__":
    main()
