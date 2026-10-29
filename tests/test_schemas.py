import copy

import schemas
import simulation


def _ok(nom):
    return copy.deepcopy(simulation._DONNEES[nom])


def test_donnees_simulees_conformes_au_contrat():
    for nom in schemas.SCHEMAS:
        assert schemas.valider(nom, _ok(nom)) == [], nom


def test_dix_criteres_dont_trois_principaux():
    assert len(schemas.CRITERES) == 10
    assert [c["id"] for c in schemas.CRITERES if c["priorite"] == "principal"] == ["approche", "controle", "emotions"]


def test_schemas_json_stricts():
    def parcourir(noeud):
        if isinstance(noeud, dict):
            if noeud.get("type") == "object":
                assert noeud["additionalProperties"] is False
                assert sorted(noeud["required"]) == sorted(noeud["properties"])
            assert "minItems" not in noeud and "maxItems" not in noeud
            for v in noeud.values():
                parcourir(v)
        elif isinstance(noeud, list):
            for v in noeud:
                parcourir(v)
    for s in schemas.SCHEMAS.values():
        parcourir(s)


def test_phrases_mauvais_nombre():
    d = _ok("propositions_motto")
    d["phrases"].pop()
    assert any("exactement 5" in p for p in schemas.valider("propositions_motto", d))


def test_phrases_mots_hors_bornes_ou_mal_formes():
    d = _ok("propositions_motto")
    d["phrases"][0]["mots"] = d["phrases"][0]["mots"][:3]
    d["phrases"][1]["mots"][0] = {"texte": " ", "nature": "verbe"}
    d["phrases"][2]["mots"][0] = {"texte": "Je", "nature": "pronom"}
    d["phrases"][3] = {"segments": ["ancien", "format"]}
    p = " | ".join(schemas.valider("propositions_motto", d))
    assert "phrase 1 : 3 mots découpés" in p
    assert "phrase 2 : « mots »" in p and "phrase 3 : « mots »" in p and "phrase 4 : « mots »" in p


def test_detresse_doit_etre_booleen():
    d = _ok("mouvements")
    d["detresse"] = "non"
    assert any("detresse" in p for p in schemas.valider("mouvements", d))
    del d["detresse"]
    assert schemas.valider("mouvements", d)


def test_critere_manquant():
    d = _ok("verification_motto")
    del d["criteres"]["present"]
    assert any("present" in p for p in schemas.valider("verification_motto", d))


def test_aide_memoire_categorie_invalide_et_nombre():
    d = _ok("aide_memoire")
    d["fixes"][0]["categorie"] = "gout"
    d["mobiles"].pop()
    p = " | ".join(schemas.valider("aide_memoire", d))
    assert "categorie" in p and "exactement 4" in p


def test_mouvements_vide():
    d = _ok("mouvements")
    d["micro"][1] = "  "
    assert schemas.valider("mouvements", d)


def test_pas_un_objet_et_contrat_inconnu():
    assert schemas.valider("mouvements", ["a"])
    assert schemas.valider("inconnu", {"detresse": False})
