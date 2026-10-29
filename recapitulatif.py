"""Récapitulatif de fin de parcours : contenu affiché à l'écran et fichier HTML téléchargeable.

Sans Streamlit, pour rester testable. Le fichier téléchargé est autonome (l'image est intégrée) :
il s'ouvre dans un navigateur et s'imprime ou s'enregistre en PDF depuis celui-ci.
"""
from __future__ import annotations

import base64
from html import escape


def sections(d: dict, c: dict) -> list[tuple[str, list[str], bool]]:
    """[(titre, lignes, en_liste)] : les choix de l'apprenant puis les ressources associées.

    `d` : voir parcours.recap_donnees(). `c` : bloc [recap] de contenus/textes.toml.
    """
    vide = [c["vide"]]

    def texte(valeur: str) -> tuple[list[str], bool]:
        return ([valeur], False) if valeur else (vide, False)

    def liste(valeurs: list[str]) -> tuple[list[str], bool]:
        return (valeurs, True) if valeurs else (vide, False)

    motto = [f"« {d['motto']} »"] if d["motto"] else vide
    if d["motto"] and d["motto_non_conforme"]:
        motto = motto + [c["motto_non_conforme"]]
    lignes_motto = (motto, False)
    return [
        (c["raisons"], *texte(d["raisons"])),
        (c["mots"], *liste(d["mots"])),
        (c["mots_complementaires"], *liste(d["mots_complementaires"])),
        (c["reflexion"], *texte(d["reflexion"])),
        (c["souhait"], *texte(d["souhait"])),
        (c["motto"], *lignes_motto),
        (c["aide_fixes"], *liste(d["aide_fixes"])),
        (c["aide_mobiles"], *liste(d["aide_mobiles"])),
        (c["mouv_macro"], *liste(d["mouv_macro"])),
        (c["mouv_micro"], *liste(d["mouv_micro"])),
    ]


_STYLE = """
body { font-family: Arial, Helvetica, sans-serif; color: #222; max-width: 720px; margin: 2rem auto; padding: 0 1rem;
       line-height: 1.5; }
h1 { font-size: 1.6rem; } h2 { font-size: 1.1rem; margin: 1.6rem 0 .3rem; }
img { max-width: 320px; height: auto; border-radius: 6px; }
p, ul { margin: .2rem 0; }
"""


def html(d: dict, c: dict, image_jpeg: bytes | None = None) -> str:
    """Document HTML autonome : tout est échappé (les saisies de l'apprenant ne sont jamais interprétées)."""
    corps = [f"<h1>{escape(c['titre_document'])}</h1>"]
    if image_jpeg:
        b64 = base64.b64encode(image_jpeg).decode("ascii")
        corps.append(f"<h2>{escape(c['image'])}</h2><img src=\"data:image/jpeg;base64,{b64}\" "
                     f"alt=\"{escape(c['image_alt'])}\">")
    for titre, lignes, en_liste in sections(d, c):
        if en_liste:
            bloc = "<ul>" + "".join(f"<li>{escape(ligne)}</li>" for ligne in lignes) + "</ul>"
        else:
            bloc = "".join(f"<p>{escape(ligne).replace(chr(10), '<br>')}</p>" for ligne in lignes)
        corps.append(f"<h2>{escape(titre)}</h2>{bloc}")
    return ("<!DOCTYPE html>\n<html lang=\"fr\"><head><meta charset=\"utf-8\">"
            f"<title>{escape(c['titre_document'])}</title><style>{_STYLE}</style></head><body>\n"
            + "\n".join(corps) + "\n</body></html>\n")
