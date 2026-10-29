"""Contrat JSON des 4 appels IA.

Le même contrat sert pour Ollama et pour Mistral. Il est envoyé au fournisseur
(`response_format` de type `json_schema`) ET revérifié ici par `valider`, car un
fournisseur peut ignorer le schéma. Les nombres d'éléments ne sont volontairement
pas dans le schéma (`minItems` / `maxItems` ne sont pas garantis partout) : ils
sont contrôlés dans `valider`.
"""
from __future__ import annotations

import checks

NB_PHRASES = 5          # panier à idées du motto
NB_AIDE_MEMOIRE = 4     # par colonne (fixes / mobiles)
NB_MOUVEMENTS = 3       # par colonne (macro / micro)
CATEGORIES = ("objet", "odeur", "musique")

# Les 10 critères de la maquette « 3. Formulation du motto » (prompt de vérification).
# « principal » = les 3 critères du top 3 du livret.
CRITERES = [
    {"id": "approche", "priorite": "principal",
     "intitule": "Un objectif d'approche (ce que je veux, pas ce que j'évite)"},
    {"id": "controle", "priorite": "principal",
     "intitule": "100 % sous mon contrôle (je ne dépends de personne d'autre)"},
    {"id": "emotions", "priorite": "principal",
     "intitule": "Un bilan émotionnel positif (au moins 70 % d'émotions positives)"},
    {"id": "invitation", "priorite": "autre",
     "intitule": "Formulé comme une invitation, une incitation ou une autorisation"},
    {"id": "langage", "priorite": "autre",
     "intitule": "Un langage simple, coloré, imagé, poétique"},
    {"id": "generalite", "priorite": "autre",
     "intitule": "Une formulation générale (pas de contexte particulier)"},
    {"id": "premiere_personne", "priorite": "autre",
     "intitule": "La première personne (« je ») et les adjectifs possessifs (« mon », « ma », « mes »)"},
    {"id": "present", "priorite": "autre",
     "intitule": "Écrit au présent"},
    {"id": "comparaison", "priorite": "autre",
     "intitule": "Sans comparaison"},
    {"id": "contrainte", "priorite": "autre",
     "intitule": "Sans verbe ni formule de contrainte (vouloir, devoir, falloir…)"},
]
IDS_CRITERES = [c["id"] for c in CRITERES]


def _chaines() -> dict:
    return {"type": "array", "items": {"type": "string"}}


def _idees() -> dict:
    return {"type": "array", "items": {
        "type": "object",
        "properties": {"idee": {"type": "string"},
                       "categorie": {"type": "string", "enum": list(CATEGORIES)}},
        "required": ["idee", "categorie"], "additionalProperties": False}}


def _objet(proprietes: dict) -> dict:
    return {"type": "object", "properties": proprietes,
            "required": list(proprietes), "additionalProperties": False}


_BOOL = {"type": "boolean"}
_CRITERE = _objet({"respecte": _BOOL, "explication": {"type": "string"}})

SCHEMAS = {
    "propositions_motto": _objet({"phrases": {"type": "array", "items": _objet({"mots": {
        "type": "array", "items": _objet({"texte": {"type": "string"},
                                          "nature": {"type": "string", "enum": list(checks.NATURES)}})}})},
                                  "detresse": _BOOL}),
    "verification_motto": _objet({
        "criteres": _objet({i: _CRITERE for i in IDS_CRITERES}),
        "suggestion": {"type": "string"},
        "detresse": _BOOL}),
    "aide_memoire": _objet({"fixes": _idees(), "mobiles": _idees(), "detresse": _BOOL}),
    "mouvements": _objet({"macro": _chaines(), "micro": _chaines(), "detresse": _BOOL}),
    "lecture_souhait": _objet({"detresse": _BOOL}),
}


def _liste_de_textes(valeur, nom: str, attendu: int, problemes: list[str]) -> None:
    if not isinstance(valeur, list) or len(valeur) != attendu:
        n = len(valeur) if isinstance(valeur, list) else "?"
        problemes.append(f"« {nom} » doit contenir exactement {attendu} éléments (reçu : {n}).")
        return
    if not all(isinstance(v, str) and v.strip() for v in valeur):
        problemes.append(f"« {nom} » ne doit contenir que des textes non vides.")


def _liste_d_idees(valeur, nom: str, problemes: list[str]) -> None:
    if not isinstance(valeur, list) or len(valeur) != NB_AIDE_MEMOIRE:
        n = len(valeur) if isinstance(valeur, list) else "?"
        problemes.append(f"« {nom} » doit contenir exactement {NB_AIDE_MEMOIRE} idées (reçu : {n}).")
        return
    for i, v in enumerate(valeur, 1):
        if not (isinstance(v, dict) and isinstance(v.get("idee"), str) and v["idee"].strip()):
            problemes.append(f"« {nom} » n°{i} : champ « idee » manquant ou vide.")
        elif v.get("categorie") not in CATEGORIES:
            problemes.append(f"« {nom} » n°{i} : « categorie » doit valoir {', '.join(CATEGORIES)}.")


def valider(nom: str, donnees) -> list[str]:
    """Renvoie la liste des écarts au contrat (liste vide = conforme)."""
    if not isinstance(donnees, dict):
        return ["la réponse doit être un objet JSON."]
    p: list[str] = []
    if not isinstance(donnees.get("detresse"), bool):
        p.append("« detresse » doit être un booléen.")
    if nom == "propositions_motto":
        phrases = donnees.get("phrases")
        if not isinstance(phrases, list) or len(phrases) != NB_PHRASES:
            n = len(phrases) if isinstance(phrases, list) else "?"
            p.append(f"« phrases » doit contenir exactement {NB_PHRASES} éléments (reçu : {n}).")
        else:
            for i, ph in enumerate(phrases, 1):
                mots = ph.get("mots") if isinstance(ph, dict) else None
                if not isinstance(mots, list) or not all(
                        isinstance(m, dict) and isinstance(m.get("texte"), str) and m["texte"].strip()
                        and m.get("nature") in checks.NATURES for m in mots):
                    p.append(f"phrase {i} : « mots » doit être une liste d'objets "
                             f"{{texte non vide, nature parmi {', '.join(checks.NATURES)}}}.")
                elif not checks.MOTS_PAR_PHRASE_MIN <= len(mots) <= checks.MOTS_PAR_PHRASE_MAX:
                    p.append(f"phrase {i} : {len(mots)} mots découpés (attendu : de {checks.MOTS_PAR_PHRASE_MIN} "
                             f"à {checks.MOTS_PAR_PHRASE_MAX}).")
    elif nom == "verification_motto":
        crit = donnees.get("criteres")
        if not isinstance(crit, dict):
            p.append("« criteres » doit être un objet.")
        else:
            for i in IDS_CRITERES:
                c = crit.get(i)
                if not (isinstance(c, dict) and isinstance(c.get("respecte"), bool)
                        and isinstance(c.get("explication"), str)):
                    p.append(f"critère « {i} » absent ou mal formé (attendu : respecte + explication).")
        if not isinstance(donnees.get("suggestion"), str):
            p.append("« suggestion » doit être un texte (vide si tout est respecté).")
    elif nom == "aide_memoire":
        _liste_d_idees(donnees.get("fixes"), "fixes", p)
        _liste_d_idees(donnees.get("mobiles"), "mobiles", p)
    elif nom == "mouvements":
        _liste_de_textes(donnees.get("macro"), "macro", NB_MOUVEMENTS, p)
        _liste_de_textes(donnees.get("micro"), "micro", NB_MOUVEMENTS, p)
    elif nom != "lecture_souhait":       # ce contrat ne contient que « detresse », déjà contrôlé plus haut
        p.append(f"contrat inconnu : {nom}")
    return p
