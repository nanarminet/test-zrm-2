import pytest

import checks


@pytest.mark.parametrize("texte,attendu", [
    ("Je cultive le calme", 4),
    ("Je m'autorise à me balader sur mon îlot de liberté.", 10),   # « m'autorise » = 1 mot
    ("Dans cette étable, j'ai mon mot à dire !", 8),
    ("porte-clés", 1),
    ("", 0),
])
def test_compter_mots(texte, attendu):
    assert checks.compter_mots(texte) == attendu


@pytest.mark.parametrize("texte", [
    "Je n'ai pas peur d'affronter la vie",
    "Je ne cherche plus à fuir",
    "Je ne me juge jamais",
    "Je n’emprunte pas le chemin de la colère",      # apostrophe typographique
    "JE NE LAISSE PAS LA PEUR M'ARRÊTER",
])
def test_negation_detectee(texte):
    assert checks.trouver_negation(texte)


@pytest.mark.parametrize("texte", [
    "Je cultive le calme",
    "La neige plus douce m'apaise",       # « ne » dans « neige » ne doit pas compter
    "Je suis nerveux plus que jamais".replace("plus que jamais", "mais je respire"),
    "J'ai plus confiance en moi",         # comparaison (critère 9), pas une négation
    "Je prends de la hauteur et mon esprit est vaste comme le ciel.",
])
def test_negation_non_detectee(texte):
    assert checks.trouver_negation(texte) is None


@pytest.mark.parametrize("texte", [
    "Il faut que je savoure la vie",
    "Je dois me reposer",
    "Je veux être calme",
    "Il faudrait que je respire",
    "Je voudrais être serein",
    "Il me faut du repos",
    "Il ne faut pas que je craque",
    "Il n’y a qu’à… et il faut y arriver",
])
def test_contrainte_detectee(texte):
    assert checks.trouver_contrainte(texte)


@pytest.mark.parametrize("texte", [
    "Je peux savourer la vie",             # « Je peux… » est admis par le livret
    "Je m'autorise à vouloir le meilleur".replace("vouloir", "rêver"),
    "Je cultive la douceur",
])
def test_contrainte_non_detectee(texte):
    assert checks.trouver_contrainte(texte) is None


def test_premiere_personne():
    assert checks.a_premiere_personne("Je marche sur mon chemin")
    assert checks.a_premiere_personne("Avec force, j'ai confiance en moi")
    assert checks.a_premiere_personne("Puissante comme une ourse, j’avance")
    assert not checks.a_premiere_personne("La douceur de la vie est savourée.")
    assert not checks.a_premiere_personne("Jardin joyeux")      # « Ja… » ne compte pas


@pytest.mark.parametrize("texte", [
    "j'ai envie d'en finir",
    "Je pense au suicide",
    "je voudrais mourir",
    "Je veux me tuer",
    "J’ai envie de mourir",
    "je veux mettre fin à mes jours",
])
def test_detresse_detectee(texte):
    assert checks.detecter_detresse(texte)


@pytest.mark.parametrize("texte", [
    "Je suis fatigué mais je tiens bon",
    "Retrouver du calme au quotidien",
    "je veux finir mon travail",
    "",
])
def test_detresse_non_detectee(texte):
    assert not checks.detecter_detresse(texte)


def test_detresse_plusieurs_textes_et_none():
    assert checks.detecter_detresse("calme", None, "envie de mourir")
    assert not checks.detecter_detresse(None, "")


def test_mots_pleins_ignore_outils_accents_pluriels():
    assert checks.mots_pleins("Je cultive les valeurs de mon jardin") == {"cultive", "valeur", "jardin"}
    assert checks.mots_pleins("ÎLOT lumière") == checks.mots_pleins("ilot lumiere")


def test_chevauchements():
    phrases = ["Je cultive le calme du jardin", "Je savoure le jardin et le calme", "Je danse avec la vague"]
    exces = checks.chevauchements(phrases)
    assert [(i, j) for i, j, _ in exces] == [(1, 2)]
    assert set(exces[0][2]) == {"calme", "jardin"}
    assert checks.chevauchements(["Je danse sous la lune", "Je savoure le jardin"]) == []


def test_verifier_phrase_motto():
    bonne = "Je m'autorise à me balader librement sur mon îlot de lumière douce."
    assert checks.verifier_phrase_motto(bonne) == []
    courte = "Je cultive le calme"
    assert any("mots" in p for p in checks.verifier_phrase_motto(courte))
    assert checks.verifier_phrase_motto(courte, bornes=False) == []
    mauvaise = "Il ne faut pas que le monde me fasse peur dans la vie de tous les jours ici"
    problemes = " | ".join(checks.verifier_phrase_motto(mauvaise))
    assert "négation" in problemes and "contrainte" in problemes and "première personne" in problemes


# ------------------------------------------------------------------ emojis
def test_detection_des_emojis_et_pictogrammes():
    for t in ("Bravo 🌿", "Super 😀", "Fait ✅", "Non ❌", "Cœur ❤️", "Étoile ⭐", "Soleil ☀", "Lecture ⏳"):
        assert checks.contient_emoji(t), t


def test_pas_de_faux_positif_sur_la_typographie_francaise():
    for t in ("« Je m'autorise… » (©) ; ça va ? Oui : bien !", "Flèche → et ← simples", "⅓ et ⅔ du temps", "Œuvre 100 %"):
        assert not checks.contient_emoji(t), t


def test_retirer_emojis_garde_le_reste_intact():
    assert checks.retirer_emojis("Je cultive le calme 🌿 et la douceur.") == "Je cultive le calme et la douceur."
    assert checks.retirer_emojis("Super ! ✅") == "Super !"
    assert checks.retirer_emojis("Voici : ❤️ le texte , propre .") == "Voici : le texte, propre."


# ------------------------------------------------------------------ découpage des mots cliquables
def test_decouper_mot_elision_et_ponctuation():
    assert checks.decouper_mot("j'ouvre", "verbe") == [{"texte": "j'", "cliquable": False},
                                                       {"texte": "ouvre", "cliquable": True, "mot": "ouvre"}]
    assert checks.decouper_mot("vie.", "nom_commun")[1] == {"texte": ".", "cliquable": False}
    assert checks.decouper_mot("qu\u2019elle", "autre") == [{"texte": "qu\u2019", "cliquable": False},
                                                          {"texte": "elle", "cliquable": False}]


def test_decouper_mot_recolle_exactement():
    for t in ("j'ouvre", "(Paris),", "vie.", "aujourd'hui", "peut-être", "l\u2019été…", "«calme»"):
        assert "".join(x["texte"] for x in checks.decouper_mot(t, "nom_commun")) == t


def test_seuls_verbes_noms_communs_et_noms_propres_sont_cliquables():
    for nature, attendu in (("verbe", True), ("nom_commun", True), ("nom_propre", True), ("autre", False)):
        assert checks.decouper_mot("lumière", nature)[0]["cliquable"] is attendu


def test_mots_outils_jamais_cliquables_meme_etiquetes_verbe():
    for mot in ("je", "Mon", "des", "du", "à", "avec", "qui", "en", "pas", "et"):
        assert not checks.decouper_mot(mot, "verbe")[0]["cliquable"], mot
    assert checks.decouper_mot("a", "verbe")[0]["cliquable"]            # « a » = verbe avoir, différent de « à »
    assert checks.decouper_mot("est", "verbe")[0]["cliquable"]


def test_majuscule_de_debut_de_phrase_retiree_sauf_nom_propre():
    assert checks.decouper_mot("Porté", "verbe", debut_de_phrase=True)[0]["mot"] == "porté"
    assert checks.decouper_mot("Lyon", "nom_propre", debut_de_phrase=True)[0]["mot"] == "Lyon"
    assert checks.decouper_mot("Porté", "verbe")[0]["mot"] == "Porté"


def test_echapper_markdown():
    assert checks.echapper_markdown("a*b_c [x](y) :smile: <b>") == "a\\*b\\_c \\[x\\](y) \\:smile\\: \\<b\\>"
