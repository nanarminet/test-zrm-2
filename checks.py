"""Vérifications déterministes (sans IA) appliquées aux réponses et aux saisies.

Pourquoi en code : compter des mots, repérer « ne… pas » ou mesurer la répétition
entre phrases est plus fiable côté script que côté modèle. Ces règles sont simples
volontairement, pour que les développeurs puissent les porter en JS à l'identique.
"""
from __future__ import annotations

import re
import unicodedata

# --- Bornes de longueur (maquette : 10 à 20 mots ; borne basse abaissée à 8 sur demande) -----
MOTS_MIN = 8
MOTS_MAX = 20
# Deux phrases ne doivent pas partager plus de ce nombre de mots pleins.
CHEVAUCHEMENT_MAX = 1

# Un mot = suite de lettres/chiffres ; l'apostrophe et le trait d'union restent dans le mot
# (« j'atteins » = 1 mot, comme dans Word).
_MOT = re.compile(r"[\wÀ-ÿ]+(?:['’\-][\wÀ-ÿ]+)*")
_PIECE = re.compile(r"[\wÀ-ÿ]+")

# Négation grammaticale : « ne / n' » suivi (à 2 mots près) de pas, plus, jamais, rien…
_NEGATION = re.compile(
    r"\b(?:ne\s+|n['’]\s*)(?:[\wÀ-ÿ'’\-]+\s+){0,2}?(?:pas|plus|jamais|rien|aucun|aucune|guère|point)\b",
    re.IGNORECASE)

# Verbes de contrainte : formes conjuguées de vouloir / devoir / falloir.
# « pouvoir » est volontairement exclu : le livret recommande « Je peux… » (cf. savoir_motto.md).
_CONTRAINTE = re.compile(
    r"\b(?:il\s+(?:(?:ne|me|te|lui|nous|vous|leur)\s+|m['’]|t['’]|n['’])?(?:faut|faudrait|faudra)"
    r"|falloir|je\s+(?:dois|devrais|me\s+dois|veux|voudrais))\b",
    re.IGNORECASE)

_PREMIERE_PERSONNE = re.compile(r"\b(?:je|j['’])", re.IGNORECASE)

# Débuts de phrase qui sont des invitations à coup sûr : les « expressions utiles » du livret
# (Je peux, Je m'autorise, Je m'accorde, Je savoure, J'aime, Je m'offre, Je m'inspire) et « Je choisis de »
# (ajouté sur demande des consultantes : c'est un engagement envers soi, pas une constatation).
# Sert à ne jamais laisser le modèle refuser ces tournures ; la liste n'est PAS limitative pour le critère.
_INVITATION = re.compile(
    r"(?:^|[,;:]\s*|\bet\s+)(?:je\s+|j['’]\s*)(?:peux|m['’]\s*autorise|m['’]\s*accorde|m['’]\s*offre"
    r"|m['’]\s*inspire|savoure|aime|choisis\s+d(?:e|['’]))",
    re.IGNORECASE)

# Filet de sécurité (pas un outil clinique) : expressions explicites de détresse.
# Liste courte et prudente, à faire relire par des professionnels du Vinatier.
_DETRESSE = re.compile(
    r"suicid|me\s+tuer|me\s+supprimer|me\s+foutre\s+en\s+l'air|mettre\s+fin\s+[àa]\s+(?:mes\s+jours|ma\s+vie)"
    r"|envie\s+d'en\s+finir|veux\s+en\s+finir|vais\s+en\s+finir|en\s+finir\s+avec\s+(?:la\s+vie|tout)"
    r"|plus\s+envie\s+de\s+vivre|plus\s+de\s+raison\s+de\s+vivre|envie\s+de\s+mourir"
    r"|(?:veux|voudrais|aimerais)\s+(?:juste\s+)?mourir|me\s+faire\s+du\s+mal|disparaître\s+pour\s+toujours",
    re.IGNORECASE)

_STOP = set("""
le la les un une des du de d l à au aux en et ou où que qui qu quoi dont dans sur sous avec par pour sans vers chez
ce cet cette ces se s ne n pas plus mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs
je j tu il elle on nous vous ils elles me m te t moi toi lui y
est suis es sommes êtes sont ai as a avons avez ont être avoir été
comme mais donc or ni car si aussi tout toute tous toutes très bien même
""".split())


# --- Emojis et pictogrammes (interdits dans les réponses du modèle) -----------------------
# Blocs Unicode des emojis et pictogrammes courants. Les flèches simples (→ ←), les guillemets « »,
# « … », ©, ® et ™ ne sont volontairement PAS dans la liste.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF"    # émoticônes, symboles, transports, drapeaux, pictogrammes étendus
    "\U00002600-\U000027BF"      # symboles divers et dingbats (coches, croix, étoiles, soleil...)
    "\U00002B00-\U00002BFF"      # flèches et symboles divers (étoile, cercles, carrés)
    "\U0000231A-\U0000231B\U000023E9-\U000023FA"   # montre, sablier, lecteur, alarme
    "\U0000203C\U00002049"       # !! et !?
    "\U0000FE0F\U0000200D\U000020E3]")   # sélecteur d'emoji, liaison, keycap


def contient_emoji(texte: str) -> bool:
    return bool(_EMOJI.search(texte or ""))


def retirer_emojis(texte: str) -> str:
    """Supprime les emojis et nettoie les espaces laissés (le reste du texte est intact)."""
    propre = _EMOJI.sub("", texte or "")
    propre = re.sub(r"[ \t]{2,}", " ", propre)
    return re.sub(r" +([,.])", r"\1", propre).strip()     # pas « ; : ! ? » : l'espace est française


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


_STOP_NORM = {_sans_accents(s) for s in _STOP}


# --- Mots cliquables des phrases proposées ---------------------------------------------------
# Seuls les verbes, noms communs, noms propres et adjectifs sont cliquables ; le reste (pronoms, déterminants,
# prépositions, conjonctions, adverbes…) ne l'est pas. La nature de chaque mot est donnée par
# le modèle ; le code corrige ce qui est certain (mots-outils) et vérifie qu'il reste assez de mots cliquables.
NATURES = ("verbe", "nom_commun", "nom_propre", "adjectif", "autre")
NATURES_CLIQUABLES = ("verbe", "nom_commun", "nom_propre", "adjectif")
MOTS_CLIQUABLES_MIN = 3     # par phrase
MOTS_PAR_PHRASE_MIN = 5
MOTS_PAR_PHRASE_MAX = 25

# Mots-outils jamais cliquables, même si le modèle les a étiquetés autrement (liste volontairement
# limitée aux déterminants, pronoms, prépositions, conjonctions et négations ; sans accents ôtés :
# « à » (préposition) n'est pas « a » (verbe avoir)).
MOTS_OUTILS = frozenset("""
le la les l un une des du de d au aux ce cet cette ces ça ceci cela celui celle ceux celles
mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs
je j tu il elle on nous vous ils elles me m te t se s moi toi lui eux soi y en
qui que qu quoi dont où lequel laquelle lesquels lesquelles
et ou ni mais donc or car si comme quand lorsque puisque que
à avec sans sous sur dans par pour vers chez entre contre selon malgré parmi depuis pendant durant
ne n pas plus jamais rien aucun aucune
tout tous toute toutes chaque quelque quelques plusieurs autre autres même mêmes tel telle
""".split())

_ELISION = re.compile(r"^(qu|jusqu|lorsqu|puisqu|[cdjlmnst])['’](.+)$", re.IGNORECASE)
_PONCTUATION = re.compile(r"^([«(\"“‘]*)(.*?)([,;:.!?…»)\"”’]*)$", re.DOTALL)


def decouper_mot(texte: str, nature: str, *, debut_de_phrase: bool = False) -> list[dict]:
    """Découpe un mot du modèle en morceaux affichables : [{"texte", "cliquable"}, ...].

    La ponctuation et l'élision (« j' », « l' », « qu' »…) sont des morceaux non cliquables à part ;
    le mot lui-même est cliquable si sa nature l'est et s'il n'est pas un mot-outil. Recoller les morceaux
    redonne exactement `texte`. Le morceau cliquable porte aussi "mot" : le mot nettoyé, tel qu'on le retient.
    """
    avant, coeur, apres = _PONCTUATION.match(texte).groups()
    elision = ""
    m = _ELISION.match(coeur)
    if m:
        elision, coeur = coeur[:len(m.group(1)) + 1], m.group(2)
    morceaux = []
    for t in (avant, elision):
        if t:
            morceaux.append({"texte": t, "cliquable": False})
    if coeur:
        cliquable = nature in NATURES_CLIQUABLES and coeur.lower() not in MOTS_OUTILS
        morceau = {"texte": coeur, "cliquable": cliquable}
        if cliquable:
            mot = coeur
            if debut_de_phrase and not elision and nature != "nom_propre":
                mot = mot[0].lower() + mot[1:]     # « Porté » en début de phrase se retient « porté »
            morceau["mot"] = mot
        morceaux.append(morceau)
    if apres:
        morceaux.append({"texte": apres, "cliquable": False})
    return morceaux


_MARKDOWN = re.compile(r"([\\`*_\[\]~$<>#|:])")


def echapper_markdown(texte: str) -> str:
    """Empêche le texte du modèle d'être interprété comme du Markdown (gras, liens, codes :emoji:…)."""
    return _MARKDOWN.sub(r"\\\1", texte)


def compter_mots(texte: str) -> int:
    return len(_MOT.findall(texte))


def trouver_negation(texte: str) -> str | None:
    m = _NEGATION.search(texte)
    return m.group(0) if m else None


def trouver_contrainte(texte: str) -> str | None:
    m = _CONTRAINTE.search(texte)
    return m.group(0) if m else None


_SANS_ESPACE_AVANT = re.compile(r"^[,.;:!?…»)\]]")
_SANS_ESPACE_APRES = re.compile(r"(?:['’«(\[]|\s)$")


def assembler_phrase(avant: str, couples: list[tuple[str, str]]) -> str:
    """Phrase composée par l'apprenant : texte libre, puis chaque mot suivi de son texte libre.

    Les espaces sont normalisés ; pas d'espace avant « , . ; : ! ? … » ni après une apostrophe (« j' » + « ouvre »).
    """
    morceaux = [avant] + [t for mot, apres in couples for t in (mot, apres)]
    phrase = ""
    for m in (x.strip() for x in morceaux):
        if not m:
            continue
        if phrase and not _SANS_ESPACE_AVANT.match(m) and not _SANS_ESPACE_APRES.search(phrase):
            phrase += " "
        phrase += m
    return phrase


def a_invitation_explicite(texte: str) -> bool:
    """Vrai si le motto contient un début de phrase admis d'office comme invitation (voir _INVITATION)."""
    return bool(_INVITATION.search(texte.strip()))


def a_premiere_personne(texte: str) -> bool:
    return bool(_PREMIERE_PERSONNE.search(texte))


def detecter_detresse(*textes: str) -> bool:
    return any(_DETRESSE.search((t or "").replace("’", "'")) for t in textes)


def mots_pleins(texte: str) -> set[str]:
    """Mots porteurs de sens (hors mots-outils), sans accents ni pluriel simple."""
    resultat = set()
    for piece in _PIECE.findall(_sans_accents(texte).lower()):
        if piece in _STOP_NORM or len(piece) <= 2:
            continue
        resultat.add(piece[:-1] if len(piece) > 3 and piece[-1] in "sx" else piece)
    return resultat


def chevauchements(phrases: list[str]) -> list[tuple[int, int, list[str]]]:
    """Paires de phrases qui partagent plus de CHEVAUCHEMENT_MAX mots pleins."""
    ensembles = [mots_pleins(p) for p in phrases]
    exces = []
    for i in range(len(phrases)):
        for j in range(i + 1, len(phrases)):
            commun = sorted(ensembles[i] & ensembles[j])
            if len(commun) > CHEVAUCHEMENT_MAX:
                exces.append((i + 1, j + 1, commun))
    return exces


def verifier_phrase_motto(phrase: str, *, bornes: bool = True) -> list[str]:
    """Écarts mécaniques d'une phrase de motto (liste vide = rien à signaler)."""
    p = []
    if bornes:
        n = compter_mots(phrase)
        if not MOTS_MIN <= n <= MOTS_MAX:
            p.append(f"compte {n} mots (attendu : de {MOTS_MIN} à {MOTS_MAX})")
    if (neg := trouver_negation(phrase)):
        p.append(f"contient une négation (« {neg} »)")
    if (contr := trouver_contrainte(phrase)):
        p.append(f"contient une formule de contrainte (« {contr} »)")
    if not a_premiere_personne(phrase):
        p.append("n'est pas écrite à la première personne (« je »)")
    return p
