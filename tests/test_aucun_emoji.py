"""Aucun emoji ni pictogramme dans le dépôt (code, textes, prompts, données) : demande explicite du projet.

Le dossier tests/ est exclu : il contient volontairement des emojis comme données d'essai du détecteur."""
from pathlib import Path

import checks

RACINE = Path(__file__).resolve().parent.parent
SUFFIXES = {".py", ".md", ".toml", ".json", ".txt"}


def test_aucun_emoji_dans_les_fichiers_du_depot():
    trouves = []
    for chemin in RACINE.rglob("*"):
        if (chemin.suffix in SUFFIXES and chemin.is_file()
                and not any(part in {"__pycache__", ".pytest_cache", ".git", "tests"} for part in chemin.parts)):
            for n, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
                if checks.contient_emoji(ligne):
                    trouves.append(f"{chemin.relative_to(RACINE)}:{n}: {ligne.strip()[:80]}")
    assert not trouves, "\n".join(trouves)
