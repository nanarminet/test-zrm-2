"""Réponses SIMULÉES (LLM_PROVIDER=mock) : aucune IA n'est appelée.

Sert uniquement à essayer l'interface et à tester le code sans clé. Les contenus
sont figés et ne disent rien de la qualité réelle du modèle.
"""
from __future__ import annotations

import json

import schemas
from llm import Reponse

_NATURES = {"a": "autre", "v": "verbe", "n": "nom_commun", "p": "nom_propre", "j": "adjectif"}


def _phrase(notation: str) -> dict:
    """« mot|nature mot|nature … » -> {"mots": [{"texte", "nature"}]} (a autre, v verbe, n nom commun, p nom propre, j adjectif)."""
    mots = []
    for element in notation.split():
        texte, code = element.rsplit("|", 1)
        mots.append({"texte": texte, "nature": _NATURES[code]})
    return {"mots": mots}


_PHRASES = [_phrase(n) for n in (
    "Je|a m'autorise|v à|a me|a balader|v librement|a sur|a mon|a îlot|n de|a lumière|n douce.|j",
    "Avec|a tendresse,|n je|a cultive|v mes|a valeurs|n et|a j'ouvre|v grand|a mes|a fenêtres|n au|a vent.|n",
    "Je|a savoure|v chaque|a matin|n le|a chant|n joyeux|j de|a mon|a jardin|n intérieur.|j",
    "Porté|v par|a la|a vague,|n je|a danse|v avec|a confiance|n au|a rythme|n de|a mon|a souffle.|n",
    "Je|a m'offre|v un|a regard|n curieux|j et|a j'accueille|v la|a beauté|n des|a petites|j choses.|n",
)]

_DONNEES = {
    "propositions_motto": {"phrases": _PHRASES, "detresse": False},
    "verification_motto": {
        "criteres": {i: {"respecte": True, "explication": ""} for i in schemas.IDS_CRITERES},
        "suggestion": "Je cultive le calme et je m'ouvre à la douceur de mon jardin intérieur.",
        "detresse": False},
    "aide_memoire": {
        "fixes": [{"idee": "l'image du motto aimantée sur le frigo", "categorie": "objet"},
                  {"idee": "un fond d'écran apaisant sur l'ordinateur de bureau", "categorie": "objet"},
                  {"idee": "une bougie au parfum de pin posée sur le bureau, avec un ruban ajouté", "categorie": "odeur"},
                  {"idee": "un carillon à vent accroché près de la fenêtre", "categorie": "musique"}],
        "mobiles": [{"idee": "un porte-clés en forme de plume", "categorie": "objet"},
                    {"idee": "un marque-page orné d'un petit dessin du paysage", "categorie": "objet"},
                    {"idee": "un fond d'écran du paysage sur le téléphone", "categorie": "objet"},
                    {"idee": "la sonnerie du téléphone remplacée par un chant d'oiseau", "categorie": "musique"}],
        "detresse": False},
    "lecture_saisie": {"detresse": False},
    "mouvements": {
        "macro": ["ouvrir grand les bras comme des ailes", "tourner lentement le haut du corps",
                  "lever les bras au-dessus de la tête en respirant"],
        "micro": ["poser les mains sur les genoux", "bouger ses doigts les uns après les autres",
                  "relâcher les épaules en expirant"],
        "detresse": False},
}


def reponse_simulee(nom: str, messages: list[dict]) -> Reponse:
    donnees = _DONNEES[nom]
    return Reponse(donnees=json.loads(json.dumps(donnees)), brut=json.dumps(donnees, ensure_ascii=False),
                   usage={"prompt_tokens": 0, "completion_tokens": 0}, latence_s=0.0, format_utilise="simulation")
