"""Extrait les 45 images et leurs mots d'un export .pptx de « Mots_Images_ZRM ».

Usage :  python scripts/extraire_images_mots.py data/Mots_Images_ZRM.pptx
Sortie  : images/image_01.jpg ... image_45.jpg  +  data/mots_images.json
Les mots sont lus dans les NOTES de chaque diapositive. Seuls des artefacts techniques sont nettoyés
(mot coupé en deux par l'éditeur, doublons, annotation entre parenthèses) ; rien d'autre n'est réécrit.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image

RACINE = Path(__file__).resolve().parent.parent
COTE_MAX = 900

# Seules corrections de fond apportées aux mots des notes : accents manquants, sans ambiguïté.
CORRECTIONS = {"Mediterranée": "Méditerranée", "Calin": "Câlin"}

_PARA = re.compile(r"<a:p>.*?</a:p>|<a:p [^>]*>.*?</a:p>", re.S)
_TEXTE = re.compile(r"<a:t>([^<]*)</a:t>")


def _texte_notes(xml: str) -> str:
    # runs d'un même paragraphe collés sans séparateur (l'éditeur coupe parfois un mot en deux runs)
    paragraphes = ["".join(_TEXTE.findall(p)) for p in _PARA.findall(xml)]
    return " ".join(p for p in paragraphes if p.strip())


def _orientation(xml_diapo: str) -> tuple[int, bool, bool]:
    """Rotation (degrés, sens horaire), retournement horizontal / vertical de l'image DANS la diapositive."""
    pic = re.search(r"<p:pic>.*?</p:pic>", xml_diapo, re.S)
    xfrm = re.search(r"<a:xfrm([^>]*)>", pic.group(0)) if pic else None
    attrs = xfrm.group(1) if xfrm else ""
    rot = re.search(r'rot="(-?\d+)"', attrs)
    return (int(rot.group(1)) // 60000 if rot else 0), 'flipH="1"' in attrs, 'flipV="1"' in attrs


def _mots(brut: str) -> list[str]:
    vus, mots = set(), []
    for morceau in brut.replace("\u000b", ",").split(","):
        m = re.sub(r"\s*\([^)]*\)", "", morceau).strip()      # annotation « (positif) »
        m = re.sub(r"\s+", " ", m)
        if not m:
            continue
        m = m[0].upper() + m[1:]
        m = CORRECTIONS.get(m, m)
        if m.lower() not in vus:
            vus.add(m.lower())
            mots.append(m)
    return mots


def main(chemin: str) -> None:
    z = zipfile.ZipFile(chemin)
    n = len([x for x in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", x)])
    (RACINE / "images").mkdir(exist_ok=True)
    sortie = []
    for i in range(1, n + 1):
        rel = z.read(f"ppt/slides/_rels/slide{i}.xml.rels").decode("utf8")
        media = re.findall(r'Target="\.\./media/([^"]+)"', rel)
        notes = re.findall(r'Target="\.\./notesSlides/([^"]+)"', rel)
        if len(media) != 1 or len(notes) != 1:
            raise SystemExit(f"diapositive {i} : {len(media)} image(s), {len(notes)} note(s) (attendu : 1 et 1)")
        brut = _texte_notes(z.read("ppt/notesSlides/" + notes[0]).decode("utf8"))
        image = Image.open(BytesIO(z.read("ppt/media/" + media[0]))).convert("RGB")
        rot, flip_h, flip_v = _orientation(z.read(f"ppt/slides/slide{i}.xml").decode("utf8"))
        if flip_h:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if flip_v:
            image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if rot % 360:
            image = image.rotate(-rot, expand=True)      # PIL tourne dans le sens anti-horaire
        image.thumbnail((COTE_MAX, COTE_MAX))
        fichier = f"image_{i:02d}.jpg"
        image.save(RACINE / "images" / fichier, format="JPEG", quality=85, optimize=True)
        sortie.append({"id": i, "fichier": fichier, "mots": _mots(brut), "notes_brutes": brut})
    (RACINE / "data" / "mots_images.json").write_text(
        json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{n} images, {sum(len(s['mots']) for s in sortie)} mots")


if __name__ == "__main__":
    main(sys.argv[1])
