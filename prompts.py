"""Chargement et assemblage des prompts (fichiers .md du dossier `prompts/`).

Les prompts sont des fichiers texte pour pouvoir être relus et modifiés sans toucher
au code. Les blocs communs (règles, savoir ZRM) sont insérés à la place des repères
`{{...}}`.
"""
from __future__ import annotations

from pathlib import Path

VERSION_PROMPTS = "2026-10-29-v0.2"
DOSSIER = Path(__file__).parent / "prompts"
MAX_CHARS_SAISIE = 600  # longueur maximale d'un champ libre envoyé au modèle

_BLOCS = {
    "{{REGLES_COMMUNES}}": "regles_communes.md",
    "{{SAVOIR_MOTTO}}": "savoir_motto.md",
    "{{SAVOIR_RESSOURCES}}": "savoir_ressources.md",
}
ACTIVITES = ("motto_propositions", "motto_verification", "aide_memoire", "mouvements", "souhait_lecture")


def _lire(nom: str) -> str:
    return (DOSSIER / nom).read_text(encoding="utf-8").strip()


def construire_system(activite: str) -> str:
    if activite not in ACTIVITES:
        raise ValueError(f"activité inconnue : {activite}")
    texte = _lire(f"{activite}.md")
    for repere, fichier in _BLOCS.items():
        texte = texte.replace(repere, _lire(fichier))
    return texte


def nettoyer_saisie(texte: str) -> str:
    """Neutralise les balises et tronque : la saisie ne doit pas pouvoir fermer `<saisie_apprenant>`."""
    texte = (texte or "").replace("<", "‹").replace(">", "›").strip()
    return texte[:MAX_CHARS_SAISIE]


def formater_saisies(**champs: str) -> str:
    """Bloc <saisie_apprenant> : une balise par champ renseigné."""
    lignes = ["<saisie_apprenant>"]
    for nom, valeur in champs.items():
        valeur = nettoyer_saisie(valeur)
        if valeur:
            lignes.append(f"<{nom}>{valeur}</{nom}>")
    lignes.append("</saisie_apprenant>")
    return "\n".join(lignes)
