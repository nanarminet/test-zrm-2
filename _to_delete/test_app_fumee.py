"""Test de fumée de app.py avec un FAUX module streamlit.

Streamlit n'est pas nécessaire ici : on vérifie la logique de l'application (enchaînement
des étapes, erreurs, détresse, retours) avec les vraies activités en mode simulation.
Cela ne remplace pas un essai réel dans le navigateur : les noms d'API Streamlit utilisés
ont été vérifiés dans la documentation, mais ce test ne les exécute pas pour de vrai.
"""
import contextlib
import io
import runpy
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

import activites
import llm
import schemas

APP = str(Path(__file__).resolve().parent.parent / "app.py")


class Etat(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v

    def __delattr__(self, k):
        del self[k]


class Arret(Exception):
    pass


class Relance(Exception):
    pass


class FauxSt(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = Etat()
        self.secrets = Etat()
        self.clics = set()
        self.en_attente = []
        self.fichier = None
        self.sortie = []          # (type, texte)
        self.sidebar = contextlib.nullcontext()

    # --- affichage
    def _ecrit(self, genre):
        return lambda texte="", *a, **k: self.sortie.append((genre, str(texte)))

    def __getattr__(self, nom):
        if nom in {"title", "header", "subheader", "markdown", "caption", "code", "info", "success", "warning",
                   "error", "text", "json"}:
            return self._ecrit(nom)
        if nom in {"set_page_config", "image", "divider", "progress"}:
            return lambda *a, **k: self.sortie.append((nom, str(a[:1])))
        raise AttributeError(nom)

    def columns(self, n):
        return [contextlib.nullcontext() for _ in range(n)]

    def expander(self, *a, **k):
        return contextlib.nullcontext()

    def spinner(self, *a, **k):
        return contextlib.nullcontext()

    def stop(self):
        raise Arret()

    def rerun(self):
        raise Relance()

    # --- widgets
    def toggle(self, label, value=False, **k):
        return value

    def download_button(self, *a, **k):
        self.sortie.append(("download", a[0]))

    def file_uploader(self, *a, **k):
        return self.fichier

    def text_area(self, label, value="", key=None, **k):
        if key is None:
            return value
        return self.session_state.setdefault(key, value)

    def radio(self, label, options, index=0, key=None, **k):
        return self.session_state.setdefault(key, options[index])

    def button(self, label, on_click=None, args=None, disabled=False, **k):
        if label in self.clics and not disabled:
            if on_click:      # Streamlit exécute le callback AVANT la relance du script : on l'imite dans lancer()
                self.en_attente.append((on_click, tuple(args or ())))
            return True
        return False

    def textes(self, genre=None):
        return "\n".join(t for g, t in self.sortie if genre in (None, g))


@pytest.fixture
def st(monkeypatch):
    faux = FauxSt()
    monkeypatch.setitem(sys.modules, "streamlit", faux)
    for nom in ("OLLAMA_API_KEY", "MISTRAL_API_KEY", "LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    return faux


def lancer(st, *clics, max_relances=6):
    """Exécute le script ; les clics ne valent que pour la 1re exécution (les suivantes = relances)."""
    st.clics = set(clics)
    for _ in range(max_relances):
        st.sortie, st.en_attente = [], []
        try:
            runpy.run_path(APP, run_name="__main__")
            relance = False
        except Relance:
            relance = True
        callbacks = st.en_attente
        for fonction, arguments in callbacks:
            fonction(*arguments)
        st.clics = set()
        if not (relance or callbacks):
            return
    raise AssertionError("trop de relances")


def png():
    tampon = io.BytesIO()
    Image.new("RGB", (800, 600), (30, 140, 90)).save(tampon, format="PNG")
    return tampon.getvalue()


class Fichier:
    name = "image.png"

    def getvalue(self):
        return png()


def preparer_etape1(st):
    st.fichier = Fichier()
    st.session_state.update(idees="liberté, calme", souhait="retrouver de la sérénité")


# ------------------------------------------------------------------ tests
def test_configuration_absente_affiche_l_aide_et_s_arrete(st, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER")
    with pytest.raises(Arret):
        runpy.run_path(APP, run_name="__main__")
    assert "Aucune clé API" in st.textes("error") and "OLLAMA_API_KEY" in st.textes("markdown")


def test_parcours_complet(st):
    preparer_etape1(st)
    lancer(st)
    assert st.session_state.etape == 1 and not st.session_state.get("res_phrases")

    lancer(st, "Proposer 5 phrases")
    assert st.session_state.etape == 2 and len(st.session_state.res_phrases.donnees["phrases"]) == 5
    assert "Je m'autorise à me balader librement" in st.textes()          # phrase proposée affichée

    lancer(st, "Vérifier mon motto")
    assert st.session_state.etape == 3
    assert st.session_state.motto.startswith("Je m'autorise")
    assert "parfaitement formulé" in st.textes("success")

    lancer(st, "Passer à la suite")
    lancer(st)                                   # le callback a changé l'étape ; réaffichage
    assert st.session_state.etape == 4
    sortie = st.textes()
    assert "Aide-mémoire" in sortie and "Mouvements" in sortie
    assert "carillon à vent" in sortie and "ouvrir grand les bras" in sortie
    assert "à adapter" in sortie or "adaptez-les" in sortie
    assert len(st.session_state.journal) == 4    # 1 phrases + 1 vérif + 1 aide-mémoire + 1 mouvements


def test_mode_test_affiche_le_journal(st):
    preparer_etape1(st)
    lancer(st, "Proposer 5 phrases")
    assert "Journal des appels" in st.textes("subheader")
    assert any(g == "download" for g, _ in st.sortie)


def test_bouton_desactive_sans_image(st):
    st.session_state.update(idees="a", souhait="b")
    lancer(st, "Proposer 5 phrases")
    assert st.session_state.etape == 1 and "Ajoutez une image" in st.textes("caption")


def test_panne_ia_suspend_l_etape_sans_perdre_la_saisie(st, monkeypatch):
    def panne(*a, **k):
        raise llm.LLMIndisponible("HTTP 503")
    monkeypatch.setattr(activites, "proposer_mottos", panne)
    preparer_etape1(st)
    lancer(st, "Proposer 5 phrases")
    assert st.session_state.etape == 1 and st.session_state.idees == "liberté, calme"
    assert "momentanément indisponible" in st.textes("warning")


def test_detresse_affiche_le_message_avec_15_et_3114(st):
    preparer_etape1(st)
    st.session_state.souhait = "j'ai envie d'en finir"
    lancer(st, "Proposer 5 phrases")
    assert st.session_state.etape == 2
    w = st.textes("warning")
    assert "15" in w and "3114" in w and "117" not in w


def test_suggestion_ramene_a_l_etape_2_avec_le_motto_prerempli(st, monkeypatch):
    preparer_etape1(st)
    lancer(st, "Proposer 5 phrases")
    ok = {i: {"respecte": True, "explication": ""} for i in schemas.IDS_CRITERES}
    ok["langage"] = {"respecte": False, "explication": "Trop plat."}
    verdict = activites.construire_verdict(
        {"criteres": ok, "suggestion": "Je m'offre un ciel clair.", "detresse": False}, "Je prends du temps")
    res = activites.ResultatActivite("verification_motto", verdict)
    monkeypatch.setattr(activites, "verifier_motto", lambda *a, **k: res)
    st.session_state["motto_" + str(st.session_state.version) + "_0"] = "Je prends du temps"
    lancer(st, "Vérifier mon motto")
    assert st.session_state.etape == 3 and "Trop plat." in st.textes("markdown")
    assert "Utiliser cette proposition" not in st.textes() and not verdict["conforme"]
    lancer(st, "Utiliser cette proposition")
    lancer(st)
    assert st.session_state.etape == 2 and st.session_state.phrase_perso == "Je m'offre un ciel clair."
    # l'option « propre motto » est présélectionnée, avec la suggestion dans le champ
    assert st.session_state[f"motto_{st.session_state.version}_5"] == "Je m'offre un ciel clair."


def test_recommencer_efface_tout(st):
    preparer_etape1(st)
    lancer(st, "Proposer 5 phrases")
    lancer(st, "Recommencer à zéro")
    lancer(st)
    assert st.session_state.etape == 1 and st.session_state.journal == []
