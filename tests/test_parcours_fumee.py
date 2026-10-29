"""Test de fumée du parcours complet avec un FAUX streamlit (voir faux_streamlit.py).

Il déroule le parcours (du choix de l'image au récapitulatif) avec les vraies activités en mode simulation, vérifie la
logique (enchaînements, blocages, relances de vérification, pop-up, pannes, détresse, conservation
des saisies) et l'absence d'emojis dans tout ce qui est affiché. Il ne remplace pas un essai réel
dans le navigateur.
"""
import importlib
import runpy
import sys
from pathlib import Path

import pytest

import activites
import llm
import schemas
from faux_streamlit import Arret, FauxSt, Relance

import checks

RACINE = Path(__file__).resolve().parent.parent
MOCK = llm.Config("mock", "Simulation", "", "mock", "")


@pytest.fixture
def st(monkeypatch):
    faux = FauxSt()
    monkeypatch.setitem(sys.modules, "streamlit", faux)
    sys.modules.pop("parcours", None)
    yield faux
    sys.modules.pop("parcours", None)


@pytest.fixture
def p(st):
    return importlib.import_module("parcours")


def tourner(st, p, *clics, config=MOCK, max_relances=8):
    """Une interaction : le script tourne ; clics ne valent que pour la 1re exécution (les suivantes = relances)."""
    st.clics = set(clics)
    for _ in range(max_relances):
        st.debut()
        try:
            p.executer(config)
            relance = False
        except Relance:
            relance = True
        st.fin()
        callbacks = st.en_attente
        for fonction, arguments in callbacks:
            fonction(*arguments)
        st.clics = set()
        if not (relance or callbacks):
            return
    raise AssertionError("trop de relances")


def etat(st):
    return st.session_state


def suivant(st, p, config=MOCK):
    tourner(st, p, f"suiv_{etat(st).ecran}", config=config)


def saisir(st, cle, valeur):
    """Saisie de l'apprenant dans un widget (écrit sans passer par le script)."""
    etat(st)._d[cle] = valeur


def cocher_mots(st, n=3):
    """L'apprenant coche les n premiers mots de la liste de l'image."""
    for i in range(n):
        saisir(st, f"w_choix_mot_{i}", True)


def depart(st, p):
    tourner(st, p)
    assert etat(st).ecran == "choix_image_consignes"


def jusqu_a_la_grille(st, p):
    depart(st, p)
    suivant(st, p)
    assert etat(st).ecran == "choix_image"


def choisir_image(st, p, image_id=7):
    tourner(st, p, f"choisir_{image_id}", "image_valider")


def jusqu_au_souhait(st, p, souhait="retrouver du calme"):
    jusqu_a_la_grille(st, p)
    choisir_image(st, p)
    assert etat(st).ecran == "raisons_image"
    saisir(st, "w_raisons", "Elle m'apaise")
    suivant(st, p)
    assert etat(st).ecran == "mots"
    cocher_mots(st)
    while etat(st).ecran != "souhait":
        suivant(st, p)
    saisir(st, "w_souhait", souhait)
    suivant(st, p)


def jusqu_au_motto(st, p, souhait="retrouver du calme"):
    jusqu_au_souhait(st, p, souhait)
    while etat(st).ecran != "motto_propositions":
        suivant(st, p)


def jusqu_a_la_redaction(st, p, motto="Je cultive le calme"):
    jusqu_au_motto(st, p)
    suivant(st, p)
    assert etat(st).ecran == "motto_redaction"
    saisir(st, "w_motto_saisie", motto)


def verdict(conforme=True, suggestion="Je m'offre un ciel clair."):
    ok = {i: {"respecte": True, "explication": ""} for i in schemas.IDS_CRITERES}
    if not conforme:
        ok["langage"] = {"respecte": False, "explication": "Trop plat."}
    donnees = activites.construire_verdict({"criteres": ok, "suggestion": suggestion, "detresse": False},
        "Je cultive le calme")
    return activites.ResultatActivite("verification_motto", donnees)


# ------------------------------------------------------------------ configuration
def test_app_sans_cle_affiche_l_aide_et_s_arrete(st, monkeypatch):
    for nom in ("OLLAMA_API_KEY", "MISTRAL_API_KEY", "LLM_PROVIDER", "LLM_API_KEY"):
        monkeypatch.delenv(nom, raising=False)
    st.debut()
    with pytest.raises(Arret):
        runpy.run_path(str(RACINE / "app.py"), run_name="__main__")
    assert "Aucune clé API" in st.textes("error") and "OLLAMA_API_KEY" in st.textes("markdown")
    assert st.sortie[0][0] == "set_page_config"


def test_app_en_simulation_commence_au_choix_de_l_image(st, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    st.debut()
    runpy.run_path(str(RACINE / "app.py"), run_name="__main__")
    assert st.sortie[0][0] == "set_page_config" and "Choisir l'image" in st.textes("header")


# ------------------------------------------------------------------ parcours
def test_le_poc_commence_par_les_consignes_du_choix_de_l_image(st, p):
    depart(st, p)
    assert "prec_choix_image_consignes" not in st.boutons                  # premier écran du POC
    texte = st.textes()
    assert "mini-podcast de relaxation" in texte and "Comment bien choisir votre image" in texte
    assert "Mini-podcast de relaxation (lancer la séquence)" in texte
    assert "bilan émotionnel" in st.textes("markdown") and "Faisons le test" not in texte


def test_grille_de_45_images_et_choix_avec_confirmation(st, p):
    jusqu_a_la_grille(st, p)
    assert len([g for g, t in st.sortie if g == "image"]) == 45
    assert all(f"choisir_{i}" in st.boutons for i in range(1, 46))
    assert st.boutons["suiv_choix_image"] is True            # aucune image encore choisie
    tourner(st, p, "choisir_7")                              # ouvre la confirmation, ne valide rien
    assert ("dialog", "Confirmer votre choix") in st.sortie and etat(st).image_id is None
    tourner(st, p, "choisir_7", "image_annuler")
    assert etat(st).image_id is None and etat(st).ecran == "choix_image"
    tourner(st, p, "choisir_7", "image_valider")
    assert etat(st).image_id == 7 and etat(st).ecran == "raisons_image"


def test_changer_d_image_efface_les_mots_choisis(st, p):
    jusqu_au_souhait(st, p)
    assert len(p.mots_choisis()) == 3
    etat(st).ecran = "choix_image"
    tourner(st, p)
    choisir_image(st, p, 12)
    assert etat(st).image_id == 12 and p.mots_choisis() == []
    assert not [k for k in etat(st)._d if k.startswith("w_choix_mot_")]
    suivant(st, p)
    assert etat(st).ecran == "mots" and st.boutons["suiv_mots"] is True        # au moins un mot requis
    assert "Sélectionnez au moins un mot" in st.textes("caption")


def test_re_choisir_la_meme_image_conserve_les_mots(st, p):
    jusqu_au_souhait(st, p)
    mots = p.mots_choisis()
    etat(st).ecran = "choix_image"
    tourner(st, p)
    choisir_image(st, p, 7)
    assert p.mots_choisis() == mots and len(mots) == 3


def test_mots_en_liste_de_cases_a_cocher_a_droite_de_l_image(st, p):
    jusqu_a_la_grille(st, p)
    choisir_image(st, p)
    suivant(st, p)
    mots = p.images()[7]["mots"]
    assert [t for g, t in st.sortie if g == "checkbox"] == mots          # un mot = une case, dans l'ordre
    assert not any(g == "pills" for g, _ in st.sortie)
    assert st.boutons["suiv_mots"] is True
    cocher_mots(st, 1)
    tourner(st, p)
    assert st.boutons["suiv_mots"] is False and p.mots_choisis() == mots[:1]


def test_les_saisies_survivent_aux_ecrans_non_affiches(st, p):
    jusqu_au_souhait(st, p, souhait="mon souhait")
    saisir(st, "w_raisons", "mes raisons")
    for _ in range(6):                          # plusieurs écrans sans ces widgets
        suivant(st, p)
    assert etat(st).w_souhait == "mon souhait" and etat(st).w_raisons == "mes raisons"
    assert len(p.mots_choisis()) == 3


def test_souhait_vide_bouton_actif_mais_message_et_pas_d_avance(st, p):
    jusqu_a_la_grille(st, p)
    choisir_image(st, p)
    suivant(st, p)
    cocher_mots(st, 1)
    while etat(st).ecran != "souhait":
        suivant(st, p)
    assert st.boutons["suiv_souhait"] is False                  # actif d'emblée, y compris champ vide
    saisir(st, "w_souhait", "   ")
    suivant(st, p)
    assert etat(st).ecran == "souhait" and "Écrivez votre souhait" in st.textes("warning")
    saisir(st, "w_souhait", "a")
    suivant(st, p)
    assert etat(st).ecran == "besoins_conclusion"


def test_propositions_motto_avec_image_mots_et_souhait(st, p, monkeypatch):
    appels = []
    reel = activites.proposer_mottos

    def espion(config, **kw):
        appels.append(kw)
        return reel(config, **kw)
    monkeypatch.setattr(activites, "proposer_mottos", espion)
    jusqu_au_motto(st, p)
    assert len(appels) == 1 and appels[0]["souhait"] == "retrouver du calme"
    assert appels[0]["image_jpeg"][:2] == b"\xff\xd8"                    # JPEG
    assert all(m in appels[0]["idees"] for m in p.mots_choisis())
    assert "(généré par IA)" in st.textes("caption")
    assert len([g for g, t in st.sortie if g == "pills"]) == 5


def test_image_non_envoyee_si_desactivee(st, p, monkeypatch):
    appels = []
    reel = activites.proposer_mottos
    monkeypatch.setattr(activites, "proposer_mottos", lambda c, **kw: (appels.append(kw), reel(c, **kw))[1])
    config = llm.Config("mock", "Simulation", "", "mock", "", envoyer_image=False)
    jusqu_au_motto_avec(st, p, config)
    assert appels and appels[0]["image_jpeg"] is None


def jusqu_au_motto_avec(st, p, config):
    etat(st).image_id = 7
    cocher_mots(st, 2)
    saisir(st, "w_souhait", "du calme")
    etat(st).ecran = "motto_propositions"
    tourner(st, p, config=config)


def test_seuls_les_verbes_et_noms_sont_cliquables_dans_les_phrases(st, p):
    jusqu_au_motto(st, p)
    res = etat(st).res_phrases
    pills = [t for g, t in st.sortie if g == "pills"]
    assert len(pills) == 5
    for phrase, options in zip(res.donnees["phrases"], pills):
        assert options.split(" | ") == phrase["cliquables"]
        assert not {"je", "mon", "ma", "mes", "de", "et", "à", "le", "la", "un", "des"} & set(options.split(" | "))
    rendus = [t for g, t in st.sortie if g == "markdown" and "**" in t and "tendresse" in t]
    assert rendus and "**tendresse**" in rendus[0] and "**mes**" not in rendus[0]
    assert "Les mots en gras sont cliquables" in st.textes("caption")


def test_pas_de_generation_de_nouvelles_phrases(st, p, monkeypatch):
    appels = []
    reel = activites.proposer_mottos
    monkeypatch.setattr(activites, "proposer_mottos", lambda c, **kw: (appels.append(1), reel(c, **kw))[1])
    jusqu_au_motto(st, p)
    assert "autres_phrases" not in st.boutons and "autres phrases" not in st.textes().lower()
    for _ in range(3):                       # réaffichages, retour arrière, avance : toujours le même appel
        tourner(st, p)
    tourner(st, p, "prec_motto_propositions")
    suivant(st, p)
    assert len(appels) == 1


def test_mots_cliques_conserves_et_affiches_a_la_redaction(st, p):
    jusqu_au_motto(st, p)
    res = etat(st).res_phrases
    choisis = res.donnees["phrases"][0]["cliquables"][:2] + res.donnees["phrases"][3]["cliquables"][:1]
    saisir(st, f"w_seg_{res.id}_1", choisis[:2])
    saisir(st, f"w_seg_{res.id}_4", choisis[2:])
    suivant(st, p)
    assert etat(st).ecran == "motto_redaction"
    assert " / ".join(choisis) in st.textes("markdown")


def test_motto_conforme_passe_directement_a_la_synthese(st, p):
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    assert etat(st).ecran == "motto_feedback" and etat(st).motto == "Je cultive le calme"
    assert "parfaitement formulé" in st.textes("success")
    assert "Quelques points" not in st.textes() and "w_amelio_1" not in etat(st)._d
    suivant(st, p)
    assert etat(st).ecran == "motto_final"
    assert "Je cultive le calme" in st.textes("success") and not any(g == "dialog" for g, _ in st.sortie)


def test_motto_non_conforme_affiche_seulement_ce_qui_ne_va_pas_et_un_exemple(st, p, monkeypatch):
    monkeypatch.setattr(activites, "verifier_motto", lambda *a, **k: verdict(False))
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    texte = st.textes()
    assert "Trop plat." in texte and "Exemple de formulation conforme" in texte and "ciel clair" in texte
    assert "parfaitement formulé" not in texte
    assert "- **Un langage simple, coloré, imagé, poétique** : Trop plat." in texte
    assert "- **Un objectif d'approche" not in texte                  # les critères respectés ne sont pas listés
    cle = f"w_amelio_{etat(st).version_amelio}"
    assert etat(st)._d[cle] == ""                                      # champ vide au départ


def test_non_conforme_sans_modification_ouvre_le_popup_puis_continuer(st, p, monkeypatch):
    appels = []
    monkeypatch.setattr(activites, "verifier_motto", lambda *a, **k: (appels.append(k), verdict(False))[1])
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    tourner(st, p, "suiv_motto_feedback")
    assert ("dialog", "Votre motto n'est pas encore conforme") in st.sortie and etat(st).ecran == "motto_feedback"
    assert "Trop plat." in st.textes()
    assert len(appels) == 1                                            # motto inchangé : pas de nouvel appel IA
    tourner(st, p)                                                     # nouvelle exécution : le pop-up ne se rouvre pas seul
    assert not any(g == "dialog" for g, _ in st.sortie)
    tourner(st, p, "suiv_motto_feedback")
    assert etat(st).get("alerte_motto") is None                        # consommé à l'ouverture
    etat(st).alerte_motto = True                                       # le pop-up est ouvert : clic dans le pop-up
    tourner(st, p, "alerte_continuer")
    assert etat(st).ecran == "motto_final"


def test_popup_ameliorer_reste_sur_l_ecran(st, p, monkeypatch):
    monkeypatch.setattr(activites, "verifier_motto", lambda *a, **k: verdict(False))
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    tourner(st, p, "suiv_motto_feedback")
    etat(st).alerte_motto = True
    tourner(st, p, "alerte_ameliorer")
    assert etat(st).ecran == "motto_feedback" and not any(g == "dialog" for g, _ in st.sortie)


def test_motto_modifie_declenche_une_nouvelle_verification(st, p, monkeypatch):
    file = [verdict(False), verdict(True)]
    appels = []

    def faux_verifier(config, *, motto):
        appels.append(motto)
        return file.pop(0)
    monkeypatch.setattr(activites, "verifier_motto", faux_verifier)
    jusqu_a_la_redaction(st, p, "Je prends du temps")
    tourner(st, p, "suiv_motto_redaction")
    saisir(st, f"w_amelio_{etat(st).version_amelio}", "Je m'offre un ciel clair")
    tourner(st, p, "suiv_motto_feedback")
    assert appels == ["Je prends du temps", "Je m'offre un ciel clair"]
    assert etat(st).ecran == "motto_final" and etat(st).motto == "Je m'offre un ciel clair"
    assert not any(g == "dialog" for g, _ in st.sortie)               # conforme : pas d'alerte


def test_motto_modifie_toujours_non_conforme_alerte_avec_le_nouveau_verdict(st, p, monkeypatch):
    file = [verdict(False), verdict(False)]
    monkeypatch.setattr(activites, "verifier_motto", lambda config, *, motto: file.pop(0))
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    saisir(st, f"w_amelio_{etat(st).version_amelio}", "Encore un essai")
    tourner(st, p, "suiv_motto_feedback")
    assert etat(st).motto == "Encore un essai" and ("dialog", "Votre motto n'est pas encore conforme") in st.sortie
    assert etat(st).ecran == "motto_feedback"


def test_revenir_a_la_redaction_sans_changer_le_motto_ne_rappelle_pas_l_ia(st, p, monkeypatch):
    appels = []
    monkeypatch.setattr(activites, "verifier_motto", lambda c, *, motto: (appels.append(motto), verdict(True))[1])
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    tourner(st, p, "prec_motto_feedback")
    assert etat(st).ecran == "motto_redaction"
    tourner(st, p, "suiv_motto_redaction")
    assert len(appels) == 1 and etat(st).ecran == "motto_feedback"


def test_motto_vide_bouton_actif_mais_message_et_pas_de_verification(st, p, monkeypatch):
    appels = []
    monkeypatch.setattr(activites, "verifier_motto", lambda c, *, motto: (appels.append(motto), verdict(True))[1])
    jusqu_a_la_redaction(st, p, motto="   ")
    tourner(st, p)
    assert st.boutons["suiv_motto_redaction"] is False
    tourner(st, p, "suiv_motto_redaction")
    assert etat(st).ecran == "motto_redaction" and "Écrivez votre motto" in st.textes("warning") and not appels
    saisir(st, "w_motto_saisie", "a")
    tourner(st, p, "suiv_motto_redaction")
    assert appels == ["a"] and etat(st).ecran == "motto_feedback"


def test_panne_ia_sur_les_phrases_puis_reprise(st, p, monkeypatch):
    reel = activites.proposer_mottos
    etat_panne = {"panne": True}

    def instable(config, **kw):
        if etat_panne["panne"]:
            raise llm.LLMIndisponible("HTTP 503")
        return reel(config, **kw)
    monkeypatch.setattr(activites, "proposer_mottos", instable)
    jusqu_au_motto(st, p)
    assert "momentanément indisponible" in st.textes("warning") and "HTTP 503" in st.textes("code")
    assert st.boutons["suiv_motto_propositions"] is True and "reessayer_motto_propositions" in st.boutons
    assert etat(st).w_souhait == "retrouver du calme"                   # rien n'est perdu
    etat_panne["panne"] = False
    tourner(st, p, "reessayer_motto_propositions")
    assert etat(st).res_phrases is not None and st.boutons["suiv_motto_propositions"] is False


def test_detresse_dans_le_souhait_affiche_15_et_3114_sur_les_ecrans_ia(st, p):
    jusqu_au_motto(st, p, souhait="j'ai envie d'en finir")
    w = st.textes("warning")
    assert "15" in w and "3114" in w and "117" not in w


def test_pas_de_message_de_detresse_dans_le_cas_normal(st, p):
    jusqu_au_motto(st, p)
    assert "3114" not in st.textes()


def test_ressources_aide_memoire_au_moins_un_par_colonne(st, p):
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    suivant(st, p)
    while etat(st).ecran != "aide_ia":
        suivant(st, p)
    res = etat(st).res_aide
    assert res is not None and "(généré par IA)" in st.textes("caption")
    assert len([g for g, t in st.sortie if g == "checkbox"]) == 8
    assert st.boutons["suiv_aide_ia"] is True and "au moins un" in st.textes("caption")
    saisir(st, f"w_aide_g_{res.id}_0", True)
    tourner(st, p)
    assert st.boutons["suiv_aide_ia"] is True                           # une seule colonne
    saisir(st, f"w_aide_d_{res.id}_1", True)
    tourner(st, p)
    assert st.boutons["suiv_aide_ia"] is False


def test_parcours_complet_jusqu_a_la_fin(st, p):
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    suivant(st, p)                                       # -> motto_final
    assert etat(st).ecran == "motto_final"
    while etat(st).ecran != "aide_ia":
        suivant(st, p)
    res_aide = etat(st).res_aide
    saisir(st, f"w_aide_g_{res_aide.id}_0", True)
    saisir(st, f"w_aide_d_{res_aide.id}_0", True)
    saisir(st, f"w_aide_d_{res_aide.id}_2", True)
    suivant(st, p)
    assert etat(st).ecran == "aide_libres"
    saisir(st, "w_libre_aide_0", "un galet dans ma poche")
    saisir(st, "w_libre_aide_type_0", "Mobile")
    saisir(st, "w_libre_aide_1", "un tableau dans le salon")
    suivant(st, p)
    assert etat(st).ecran == "aide_recap"
    recap = st.textes("markdown")
    assert res_aide.donnees["fixes"][0]["idee"] in recap and "un galet dans ma poche" in recap
    assert "un tableau dans le salon" in recap
    assert res_aide.donnees["fixes"][1]["idee"] not in recap            # non coché

    while etat(st).ecran != "mouvements_ia":
        suivant(st, p)
    res_mouv = etat(st).res_mouv
    assert "adaptez-les" in st.textes("caption")
    saisir(st, f"w_mouv_g_{res_mouv.id}_0", True)
    saisir(st, f"w_mouv_d_{res_mouv.id}_2", True)
    suivant(st, p)
    assert etat(st).ecran == "mouvements_libres"
    saisir(st, "w_libre_mouv_0", "je tends les bras vers le ciel <b>")
    suivant(st, p)
    assert etat(st).ecran == "recap"                       # le POC s'arrête une fois les mouvements choisis

    ecran = st.textes("markdown")
    assert "Elle m'apaise" in ecran and "retrouver du calme" in ecran and "Je cultive le calme" in ecran
    assert res_aide.donnees["fixes"][0]["idee"] in ecran and "un galet dans ma poche" in ecran
    assert res_mouv.donnees["macro"][0] in ecran and "tends les bras" in ecran
    assert res_mouv.donnees["micro"][2] in ecran
    assert res_mouv.donnees["macro"][1] not in ecran                      # non coché
    for mot in p.mots_choisis():
        assert mot in ecran

    nom, mime, donnees = st.telechargements["telecharger_recap"]
    contenu = donnees.decode("utf-8")
    assert nom.endswith(".html") and mime == "text/html" and contenu.startswith("<!DOCTYPE html>")
    assert "data:image/jpeg;base64," in contenu                           # image intégrée : fichier autonome
    assert "Elle m&#x27;apaise" in contenu and "je tends les bras vers le ciel &lt;b&gt;" in contenu
    assert "<b>" not in contenu                                           # saisie échappée, jamais interprétée
    assert res_aide.donnees["fixes"][0]["idee"].replace("'", "&#x27;") in contenu

    assert "suiv_recap" not in st.boutons                                 # dernier écran : pas de « Suivant »
    tourner(st, p, "recap_recommencer")
    assert etat(st).ecran == "choix_image_consignes" and not etat(st).get("image_id")


def test_recapitulatif_incomplet_signale_ce_qui_manque(st, p):
    jusqu_au_souhait(st, p)
    etat(st).ecran = "recap"
    tourner(st, p)
    assert "Non renseigné" in st.textes("markdown")
    assert "Mon récapitulatif" in st.textes("header")


def test_recapitulatif_signale_un_motto_non_conforme(st, p, monkeypatch):
    monkeypatch.setattr(activites, "verifier_motto", lambda *a, **k: verdict(False))
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    tourner(st, p, "suiv_motto_feedback")
    etat(st).ecran = "recap"
    tourner(st, p)
    assert "ne respecte pas encore tous les critères" in st.textes("markdown")


def test_les_resultats_de_l_ia_sont_relances_si_les_entrees_changent(st, p):
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    while etat(st).ecran != "aide_ia":
        suivant(st, p)
    premier = etat(st).res_aide.id
    tourner(st, p)
    assert etat(st).res_aide.id == premier                               # mêmes entrées : pas de nouvel appel
    etat(st).motto = "Autre motto"
    tourner(st, p)
    assert etat(st).res_aide.id != premier


def test_aucun_emoji_affiche_sur_tout_le_parcours(st, p):
    vus = set()
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    for ecran in p.ORDRE:
        etat(st).ecran = ecran
        tourner(st, p)
        for genre, texte in st.sortie:
            assert not checks.contient_emoji(texte), (ecran, genre, texte)
        vus.add(ecran)
    assert vus == set(p.ORDRE) and p.ORDRE[0] == "choix_image_consignes" and p.ORDRE[-1] == "recap"
    assert "menu" not in p.ORDRE and "sociales_saisie" not in p.ORDRE


def test_chaque_ecran_a_une_fonction_et_tous_les_textes_existent(p):
    c = p.contenus()
    for ecran in p.ORDRE:
        assert callable(p.ECRANS[ecran])
    assert len(p.images()) == 45 and all(e["mots"] for e in p.images().values())
    assert len(c["criteres"]) == 10


# ------------------------------------------------------------------ accessibilité, aide-mémoire, récapitulatif
def test_chaque_temoignage_de_sophie_a_sa_transcription_ecrite(st, p):
    c = p.contenus()
    attendus = {"choix_image_consignes": "image", "mots": "idees", "souhait_intro": "souhait",
                "motto_synthese": "motto", "aide_panier": "aide_memoire", "mouvements_types": "mouvements"}
    jusqu_au_souhait(st, p)
    for ecran, cle in attendus.items():
        etat(st).ecran = ecran
        tourner(st, p)
        assert ("expander", "Lire la transcription du témoignage") in st.sortie, ecran
        assert c["transcriptions"][cle].strip() in st.textes("markdown"), ecran
        assert len(c["transcriptions"][cle]) > 200
    assert "géraniums" in c["transcriptions"]["image"] and "pompon rouge" in c["transcriptions"]["aide_memoire"]


def test_aide_panier_menu_deroulant_image_et_motto_apres_la_phrase_pour_commencer(st, p):
    jusqu_a_la_redaction(st, p)
    tourner(st, p, "suiv_motto_redaction")
    etat(st).ecran = "aide_panier"
    tourner(st, p)
    genres = [(g, t) for g, t in st.sortie if g in ("markdown", "expander", "info", "image")]
    textes = [t for g, t in genres]
    i_phrase = next(i for i, t in enumerate(textes) if "Pour commencer, ayez en tête votre motto et votre image." in t)
    i_menu = textes.index("Revoir mon image et relire mon motto")
    i_suite = next(i for i, t in enumerate(textes) if "Nous allons maintenant faire un panier aux idées" in t)
    assert i_phrase < i_menu < i_suite
    assert any(g == "info" and "Je cultive le calme" in t for g, t in genres[i_menu:i_suite])
    assert any(g == "image" for g, t in genres[i_menu:i_suite])


def test_recap_bouton_recommencer_a_cote_du_telechargement_en_haut(st, p):
    jusqu_au_souhait(st, p)
    etat(st).ecran = "recap"
    tourner(st, p)
    ordre = [t for g, t in st.sortie if g in ("download", "button") or t == "Mon récapitulatif"]
    i_titre = ordre.index("Mon récapitulatif")
    i_tel = ordre.index("Télécharger mon récapitulatif")
    i_rec = ordre.index("Recommencer à zéro")             # 1re occurrence : bouton du récapitulatif (la barre latérale vient avant)
    assert "recap_recommencer" in st.boutons
    sortie_texte = [t for g, t in st.sortie]
    assert sortie_texte.index("Télécharger mon récapitulatif") < len(sortie_texte) - sortie_texte[::-1].index("Recommencer à zéro")
    haut = sortie_texte.index("Mon récapitulatif")
    assert sortie_texte.index("Télécharger mon récapitulatif") - haut < 4
    idx_rec = [n for n, (g, t) in enumerate(st.sortie) if t == "Recommencer à zéro"][-1]
    idx_tel = sortie_texte.index("Télécharger mon récapitulatif")
    assert idx_tel < idx_rec < sortie_texte.index("Mon image") if "Mon image" in sortie_texte else idx_tel < idx_rec
    assert idx_rec - idx_tel <= 2                          # côte à côte, juste après le téléchargement


# ------------------------------------------------------------------ souhait lu par l'IA, composeur de phrase
def jusqu_au_souhait_saisi(st, p, souhait):
    jusqu_a_la_grille(st, p)
    choisir_image(st, p)
    suivant(st, p)
    cocher_mots(st, 2)
    while etat(st).ecran != "souhait":
        suivant(st, p)
    saisir(st, "w_souhait", souhait)


def test_le_souhait_est_lu_par_l_ia_une_seule_fois_par_texte(st, p, monkeypatch):
    appels = []
    reel = activites.lire_souhait
    monkeypatch.setattr(activites, "lire_souhait", lambda c, **kw: (appels.append(kw["souhait"]), reel(c, **kw))[1])
    jusqu_au_souhait_saisi(st, p, "retrouver du calme")
    suivant(st, p)
    assert etat(st).ecran == "besoins_conclusion" and appels == ["retrouver du calme"]
    tourner(st, p, "prec_besoins_conclusion")
    suivant(st, p)                                            # même texte : pas de nouvel appel
    assert appels == ["retrouver du calme"] and etat(st).ecran == "besoins_conclusion"
    tourner(st, p, "prec_besoins_conclusion")
    saisir(st, "w_souhait", "retrouver du calme et de la joie")
    suivant(st, p)
    assert len(appels) == 2


def test_detresse_reperee_par_l_ia_dans_le_souhait_affiche_le_meme_message_que_le_motto(st, p, monkeypatch):
    import simulation
    monkeypatch.setitem(simulation._DONNEES, "lecture_souhait", {"detresse": True})
    jusqu_au_souhait_saisi(st, p, "que tout s'arrête doucement")        # aucun mot-clé : seul le modèle le repère
    suivant(st, p)
    assert etat(st).ecran == "souhait"                                   # on reste pour afficher le message
    w = st.textes("warning")
    assert "15" in w and "3114" in w and "117" not in w
    assert w.count("3114") == 1
    suivant(st, p)                                                       # la personne décide : même texte, on avance
    assert etat(st).ecran == "besoins_conclusion"


def test_detresse_par_mots_cles_dans_le_souhait_s_affiche_aussi_sans_ia(st, p):
    jusqu_au_souhait_saisi(st, p, "j'ai envie d'en finir")
    tourner(st, p)
    assert "3114" in st.textes("warning")                                # dès l'écran, avant tout clic
    suivant(st, p)
    assert etat(st).ecran == "souhait"
    suivant(st, p)
    assert etat(st).ecran == "besoins_conclusion"


def test_panne_ia_a_la_lecture_du_souhait_bloque_avec_reessayer(st, p, monkeypatch):
    etat_panne = {"panne": True}
    reel = activites.lire_souhait

    def instable(config, **kw):
        if etat_panne["panne"]:
            raise llm.LLMIndisponible("HTTP 503")
        return reel(config, **kw)
    monkeypatch.setattr(activites, "lire_souhait", instable)
    jusqu_au_souhait_saisi(st, p, "retrouver du calme")
    suivant(st, p)
    assert etat(st).ecran == "souhait" and "momentanément indisponible" in st.textes("warning")
    assert etat(st).w_souhait == "retrouver du calme"
    etat_panne["panne"] = False
    suivant(st, p)
    assert etat(st).ecran == "besoins_conclusion"


def choix_de_mots(st, p):
    """Va à la rédaction avec 3 mots retenus : renvoie la liste des mots (ordre de sélection)."""
    jusqu_au_motto(st, p)
    res = etat(st).res_phrases
    choisis = res.donnees["phrases"][0]["cliquables"][:2] + res.donnees["phrases"][3]["cliquables"][:1]
    saisir(st, f"w_seg_{res.id}_1", choisis[:2])
    saisir(st, f"w_seg_{res.id}_4", choisis[2:])
    suivant(st, p)
    assert etat(st).ecran == "motto_redaction"
    return choisis


def test_composeur_au_dessus_du_champ_libre_avec_texte_libre_entre_les_mots(st, p):
    mots = choix_de_mots(st, p)
    tourner(st, p)
    sortie = [t for g, t in st.sortie]
    i_compo = sortie.index("**Composer ma phrase avec les mots retenus**")
    i_champ = len(sortie) - 1 - sortie[::-1].index("Vérifier mon motto")
    assert i_compo < i_champ
    for mot in mots:                                                     # une zone de texte libre à la suite de chaque mot
        assert f"w_comp_apres_{mot.lower()}" in etat(st).keys()
    assert "w_comp_avant" in etat(st).keys()
    assert "Aperçu de ma phrase :" in st.textes("markdown")


def test_composeur_glisser_deposer_ordre_et_texte_libre_places_dans_le_champ(st, p, monkeypatch):
    mots = choix_de_mots(st, p)
    monkeypatch.setattr(p, "sort_items", lambda items: list(reversed(items)))       # l'apprenant inverse l'ordre
    saisir(st, "w_comp_avant", "Je")
    saisir(st, f"w_comp_apres_{mots[0].lower()}", "et j'")
    tourner(st, p)
    attendu = checks.assembler_phrase("Je", [(m, "et j'" if m == mots[0] else "") for m in reversed(mots)])
    assert attendu in st.textes("markdown")
    tourner(st, p, "comp_inserer")
    assert etat(st).w_motto_saisie == attendu


def test_composeur_sans_composant_garde_l_ordre_de_la_selection(st, p, monkeypatch):
    mots = choix_de_mots(st, p)
    monkeypatch.setattr(p, "sort_items", None)
    tourner(st, p)
    assert "glisser-déposer n'est pas disponible" in st.textes("caption")
    assert " ".join(mots) in st.textes("markdown")


def test_composeur_ignore_un_ordre_incoherent_du_composant(st, p, monkeypatch):
    mots = choix_de_mots(st, p)
    monkeypatch.setattr(p, "sort_items", lambda items: ["mot inconnu"])
    tourner(st, p)
    assert " ".join(mots) in st.textes("markdown")


def test_composeur_sans_mot_retenu(st, p):
    jusqu_a_la_redaction(st, p)
    tourner(st, p)
    assert "Retenez des mots" in st.textes("caption") and "comp_inserer" not in st.boutons


def test_texte_libre_du_composeur_passe_aussi_par_le_filet_de_detresse(st, p):
    choix_de_mots(st, p)
    saisir(st, "w_comp_avant", "j'ai envie d'en finir")
    tourner(st, p)
    assert "3114" in st.textes("warning")
