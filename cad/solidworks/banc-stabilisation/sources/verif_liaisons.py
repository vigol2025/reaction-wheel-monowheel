"""Contrôle d'un assemblage contraint, rouvert depuis le disque : état des contraintes (erreurs), composants fixes,
composants qui ne sont pas complètement contraints (avec les contraintes qui les tiennent), boîte de chaque pièce, et
export STEP de l'assemblage reconstruit (%TEMP%/<nom>_rouvert.step) pour comparer la position des pièces à un STEP de
référence.

Usage : python -I verif_liaisons.py <assemblage .SLDASM>   (SolidWorks fermé)
"""
import json
import os
import sys

import pythoncom
import win32com.client

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rw_outils_sw import ouvrir
from liaisons import A
from swbuild import application


def contraintes(doc):
    out = []
    f = A(doc, "FirstFeature")
    while f is not None:
        if A(f, "GetTypeName2") == "MateGroup":
            m = A(f, "GetFirstSubFeature")
            while m is not None:
                avert = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False)
                code = m.GetErrorCode2(avert)
                out.append((A(m, "Name"), A(m, "GetTypeName2"), code if not avert.value else f"avertissement {code}"))
                m = A(m, "GetNextSubFeature")
        f = A(f, "GetNextFeature")
    return out


ETATS = {2: "sous-contraint", 3: "complètement contraint", 4: "surcontraint"}   # GetConstrainedStatus


def par_composant(doc):
    """{composant du premier niveau : [(contrainte, type)]} d'après les entités de chaque contrainte."""
    out = {}
    f = A(doc, "FirstFeature")
    while f is not None:
        if A(f, "GetTypeName2") == "MateGroup":
            m = A(f, "GetFirstSubFeature")
            while m is not None:
                mate = A(m, "GetSpecificFeature2")
                for i in range(A(mate, "GetMateEntityCount")):
                    c = A(A(mate, "MateEntity", i), "ReferenceComponent")
                    nom = A(c, "Name2").split("/")[0] if c is not None else "assemblage"
                    out.setdefault(nom, []).append((A(m, "Name"), A(m, "GetTypeName2")))
                m = A(m, "GetNextSubFeature")
        f = A(f, "GetNextFeature")
    return out


def main():
    chemin = sys.argv[1]
    sw = application()
    try:
        asm = ouvrir(sw, chemin)
        A(asm, "ForceRebuild3", False)
        boites = {}
        for c in A(asm, "GetComponents", False):
            if A(c, "GetChildren"):
                continue
            b = A(c, "GetBox", False, False)
            boites[A(c, "Name2")] = [round(v * 1000, 1) for v in b] if b else None
        m = contraintes(asm)
        erreurs = [x for x in m if x[2] not in (0, None)]
        fixes = [A(c, "Name2") for c in A(asm, "GetComponents", True) if A(c, "IsFixed")]
        print(f"{os.path.basename(chemin)} : {len(boites)} pièces, {len(m)} contraintes au premier niveau, "
              f"{len(erreurs)} en erreur, composants fixes : {fixes}")
        for e in erreurs[:20]:
            print("   erreur", e)
        liees = par_composant(asm)
        for c in A(asm, "GetComponents", True):
            nom, etat = A(c, "Name2"), A(c, "GetConstrainedStatus")
            if not A(c, "IsFixed") and etat != 3:
                print(f"   {nom} : {ETATS.get(etat, etat)}, contraintes {[t for _, t in liees.get(nom, [])]}")
        sortie = os.path.splitext(os.path.basename(chemin))[0] + "_boites.json"
        json.dump(boites, open(os.path.join(os.environ.get("TEMP", "."), sortie), "w", encoding="utf-8"), indent=0)
        print("boîtes écrites dans", sortie)
        step = os.path.join(os.environ.get("TEMP", "."), os.path.splitext(os.path.basename(chemin))[0] + "_rouvert.step")
        assert A(asm, "SaveAs3", step, 0, 3) == 0, step
        print("STEP de l'assemblage rouvert :", step)
    finally:
        sw.CloseAllDocuments(True)
        try:
            sw.ExitApp()
        except Exception:
            pass


if __name__ == "__main__":
    main()
