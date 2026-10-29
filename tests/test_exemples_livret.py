import json
from pathlib import Path

import pytest

import activites
import checks
import llm

DONNEES = json.loads((Path(__file__).resolve().parent.parent / "data" / "exemples_livret.json").read_text("utf-8"))
MOTTOS = DONNEES["mottos_officiels"]


@pytest.mark.parametrize("motto", MOTTOS)
def test_mottos_officiels_sans_defaut_mecanique(motto):
    assert checks.verifier_phrase_motto(motto, bornes=False) == []


def test_longueurs_des_mottos_officiels_documentees():
    """Garde-fou : les bornes 10-20 mots de la maquette ne sont pas celles du livret."""
    longueurs = [checks.compter_mots(m) for m in MOTTOS]
    assert min(longueurs) < checks.MOTS_MIN      # des mottos officiels sont plus courts que 10 mots
    assert max(longueurs) <= checks.MOTS_MAX


@pytest.mark.parametrize("ex", DONNEES["exemples_ko_mecaniques"], ids=lambda e: e["motto"][:30])
def test_exemples_ko_detectes_par_le_code(ex):
    fonction = {"negation": checks.trouver_negation, "contrainte": checks.trouver_contrainte,
                "premiere_personne": lambda t: None if checks.a_premiere_personne(t) else "absente"}[ex["detecte"]]
    assert fonction(ex["motto"])
    # le verdict final doit les marquer en échec même si le modèle les avait validés
    ok = {i: {"respecte": True, "explication": ""} for i in activites.schemas.IDS_CRITERES}
    verdict = activites.construire_verdict({"criteres": ok, "suggestion": "", "detresse": False}, ex["motto"])
    crit = {c["id"]: c for c in verdict["criteres"]}
    assert crit[ex["critere_force"]]["respecte"] is False and crit[ex["critere_force"]]["source"] == "code"
    assert verdict["conforme"] is False


@pytest.mark.parametrize("motto", DONNEES["exemples_ok_mecaniques"])
def test_exemples_ok_non_marques_par_le_code(motto):
    ok = {i: {"respecte": True, "explication": ""} for i in activites.schemas.IDS_CRITERES}
    verdict = activites.construire_verdict({"criteres": ok, "suggestion": "", "detresse": False}, motto)
    assert verdict["conforme"] is True, [c for c in verdict["criteres"] if not c["respecte"]]
