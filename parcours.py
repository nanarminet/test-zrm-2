"""Parcours ZRM simulé : écrans fixes (textes des PowerPoint) + 4 activités IA.

Les textes viennent de `contenus/textes.toml` ; les réponses de l'IA, de `activites.py`.
Ce module ne contient aucune règle sur la qualité des réponses (voir `checks.py` et `activites.py`).

Principes d'état (Streamlit) :
  - tous les widgets ont une clé qui commence par `w_` ; leur valeur est réaffectée au début de chaque
    exécution (`S[k] = S[k]`), sinon Streamlit l'efface dès que l'écran n'est plus affiché ;
  - les résultats de l'IA et les choix structurants sont des clés ordinaires (sans `w_`).
"""
from __future__ import annotations

import json
import logging
import tomllib
from functools import lru_cache
from pathlib import Path

import streamlit as st

try:                                     # composant tiers (requirements.txt) : glisser-déposer des mots
    from streamlit_sortables import sort_items
except ImportError:                      # sans lui, les mots restent dans l'ordre de la sélection
    sort_items = None

import activites
import checks
import llm
import prompts
import recapitulatif
import textes

RACINE = Path(__file__).parent
log = logging.getLogger("zrm.parcours")
S = st.session_state

NB_LIBRES = 3          # champs de saisie libre par écran
COLONNES_GRILLE = 5    # images par ligne dans la grille de choix


# ----------------------------------------------------------------------------- contenus
@lru_cache(maxsize=1)
def contenus() -> dict:
    with open(RACINE / "contenus" / "textes.toml", "rb") as f:
        return tomllib.load(f)


@lru_cache(maxsize=1)
def images() -> dict[int, dict]:
    """{id: {"chemin": Path, "mots": [...]}} pour les 45 images (mots fixes par image)."""
    with open(RACINE / "data" / "mots_images.json", encoding="utf-8") as f:
        donnees = json.load(f)
    return {e["id"]: {"chemin": RACINE / "images" / e["fichier"], "mots": e["mots"]}
            for e in sorted(donnees, key=lambda e: e["id"])}


@lru_cache(maxsize=64)
def _image_pour_ia(image_id: int) -> bytes:
    return activites.preparer_image(images()[image_id]["chemin"].read_bytes())


C = contenus()
G = C["general"]

ORDRE = [
    # 1. Découverte de ses besoins (le POC commence au choix de l'image)
    "choix_image_consignes", "choix_image", "raisons_image", "mots", "mots_complementaires", "reflexion", "souhait_intro", "souhait",
    "besoins_conclusion",
    # 2. Formulation du motto
    "motto_intro", "motto_infographie", "motto_synthese", "motto_navigation", "motto_propositions",
    "motto_redaction", "motto_feedback", "motto_final",
    # 3. Identification des ressources (le POC s'arrête une fois les mouvements choisis)
    "ressources_intro", "ressources_video", "aide_theorie", "aide_panier", "aide_ia", "aide_libres",
    "aide_recap", "mouvements_theorie", "mouvements_types", "mouvements_ia", "mouvements_libres",
    # Récapitulatif téléchargeable
    "recap",
]
DEBUT_ETAPES = ["choix_image_consignes", "motto_intro", "ressources_intro"]
ECRANS_AVEC_SAISIE = {"raisons_image", "mots_complementaires", "reflexion", "souhait", "motto_propositions",
                      "motto_redaction", "motto_feedback", "aide_ia", "aide_libres", "mouvements_ia",
                      "mouvements_libres"}

_config: llm.Config | None = None      # fixée par executer()


# ----------------------------------------------------------------------------- état
def _defauts() -> dict:
    d = {"ecran": ORDRE[0], "image_id": None, "detresse_ia": False,
         "res_phrases": None, "sig_phrases": None,
         "motto": "", "res_verdict": None, "version_amelio": 0,
         "res_aide": None, "sig_aide": None, "res_mouv": None, "sig_mouv": None,
         "w_raisons": "", "w_reflexion": "",
         "w_souhait": "", "w_motto_saisie": "", "lu_souhait": "", "lu_raisons_image": ""}
    for i in range(NB_LIBRES):
        d[f"w_mots_libres_{i}"] = ""
        d[f"w_libre_aide_{i}"] = ""
        d[f"w_libre_aide_type_{i}"] = C["aide_libres"]["types"][0]
        d[f"w_libre_mouv_{i}"] = ""
        d[f"w_libre_mouv_type_{i}"] = C["mouvements_libres"]["types"][0]
        d[f"w_sociales_{i}"] = ""
    return d


def init_etat() -> None:
    for cle, valeur in _defauts().items():
        S.setdefault(cle, valeur)
    for cle in [k for k in S.keys() if k.startswith("w_")]:
        S[cle] = S[cle]       # garde la saisie même si l'écran n'est pas affiché pendant une exécution


def oublier(prefixe: str) -> None:
    for cle in [k for k in S.keys() if k.startswith(prefixe)]:
        del S[cle]


def recommencer() -> None:
    for cle in list(S.keys()):
        del S[cle]


def aller(ecran: str) -> None:
    S.ecran = ecran


def _pas(delta: int) -> None:
    S.ecran = ORDRE[max(0, min(len(ORDRE) - 1, ORDRE.index(S.ecran) + delta))]


def avancer() -> None:
    _pas(1)


def reculer() -> None:
    _pas(-1)


# ----------------------------------------------------------------------------- données saisies
def mots_choisis() -> list[str]:
    """Mots de l'image cochés (une case par mot, dans l'ordre de la liste)."""
    if not S.image_id:
        return []
    return [m for i, m in enumerate(images()[S.image_id]["mots"]) if S.get(f"w_choix_mot_{i}")]


def mots_complementaires() -> list[str]:
    return [t for t in (S.get(f"w_mots_libres_{i}", "").strip() for i in range(NB_LIBRES)) if t]


def idees_favorites() -> str:
    return ", ".join(mots_choisis() + mots_complementaires())


def souhait() -> str:
    return S.w_souhait.strip()


def libres(prefixe: str, types: bool = True) -> list[tuple[str, str]]:
    """Idées libres saisies : [(texte, type)]."""
    sortie = []
    for i in range(NB_LIBRES):
        t = S.get(f"w_{prefixe}_{i}", "").strip()
        if t:
            sortie.append((t, S.get(f"w_{prefixe}_type_{i}", "") if types else ""))
    return sortie


def selection_courante() -> list[str]:
    """Mots cliqués dans les phrases proposées, dans l'ordre des phrases."""
    choix = []
    if S.res_phrases is not None:
        for n in range(1, len(S.res_phrases.donnees["phrases"]) + 1):
            choix += S.get(f"w_seg_{S.res_phrases.id}_{n}") or []
    vus, sortie = set(), []
    for c in choix:
        if c.lower() not in vus:
            vus.add(c.lower())
            sortie.append(c)
    return sortie


def textes_libres() -> list[str]:
    cles = [k for k in S.keys() if k.startswith(("w_raisons", "w_reflexion", "w_souhait", "w_motto_saisie",
                                                   "w_sociales", "w_mots_libres_", "w_amelio_", "w_comp_",
                                                   "w_libre_aide_", "w_libre_mouv_"))]
    return [str(S[k]) for k in cles if isinstance(S[k], str)] + [S.motto]


# ----------------------------------------------------------------------------- éléments d'affichage
def md(bloc: str, champ: str = "corps") -> None:
    st.markdown(C[bloc][champ])


def titre(bloc: str) -> None:
    st.header(C[bloc]["titre"])


def media(libelle: str) -> None:
    """Emplacement d'un média (audio, vidéo, infographie) non inclus dans ce test."""
    with st.container(border=True):
        st.markdown(f"**{libelle}**")
        st.caption(G["media"])


def temoignage(texte: str, cle: str) -> None:
    """Texte d'introduction + emplacement de l'audio + transcription écrite (accessibilité)."""
    st.markdown(texte)
    media(G["temoignage_media"])
    with st.expander(G["transcription_titre"]):
        st.markdown(C["transcriptions"][cle])


def image_choisie(largeur: int = 280) -> None:
    if S.image_id:
        st.image(str(images()[S.image_id]["chemin"]), width=largeur)


def synthese() -> None:
    """Image + idées favorites + souhait (panneau « Ma synthèse » et écran de fin de motto)."""
    gauche, droite = st.columns([1, 1])
    with gauche:
        image_choisie(240)
    with droite:
        mots = mots_choisis() + mots_complementaires()
        st.markdown("**Mes idées favorites :** " + (", ".join(mots) if mots else "-"))
        st.markdown("**Mon souhait :** " + (souhait() or "-"))


def panneaux_motto() -> None:
    """Rappels consultables à tout moment pendant la formulation du motto."""
    m = C["motto_navigation"]
    with st.expander(m["criteres_titre"]):
        for c in C["criteres"]:
            st.markdown(f"**{c['intitule']}**  \nExemple conforme : {c['ok']}  \nExemple non conforme : {c['ko']}")
    with st.expander(m["synthese_titre"]):
        synthese()


def afficher_detresse() -> None:
    if S.ecran in ECRANS_AVEC_SAISIE and (S.detresse_ia or checks.detecter_detresse(*textes_libres())):
        st.warning(textes.DETRESSE)


def nav(*, suivant: bool = True, libelle: str | None = None, precedent: bool = True, sur_suivant=None,
        dernier: bool = False) -> None:
    """Boutons Précédent / Suivant.

    `sur_suivant` : fonction appelée au clic sur le bouton de droite, à la place de l'écran suivant
    (vérification du motto, par exemple). Sans lui, le bouton passe à l'écran suivant.
    """
    st.write("")
    gauche, droite = st.columns(2)
    with gauche:
        if precedent and S.ecran != ORDRE[0]:
            st.button(G["precedent"], key=f"prec_{S.ecran}", on_click=reculer)
    with droite:
        if dernier:
            return
        if sur_suivant is None:
            st.button(libelle or G["suivant"], key=f"suiv_{S.ecran}", type="primary", disabled=not suivant,
                      on_click=avancer)
        elif st.button(libelle or G["suivant"], key=f"suiv_{S.ecran}", type="primary", disabled=not suivant):
            sur_suivant()


# ----------------------------------------------------------------------------- appels à l'IA
def appel(libelle: str, fonction, **kwargs):
    """Lance une activité ; renvoie (résultat, message d'erreur). Ne lève pas d'exception de l'IA."""
    try:
        with st.spinner(libelle):
            res = fonction(_config, **kwargs)
    except llm.LLMError as e:
        log.warning("echec activite=%s : %s", getattr(fonction, "__name__", "?"), e)
        return None, str(e)
    if res.detresse:
        S.detresse_ia = True
    if res.alertes:
        log.info("activite=%s alertes=%s", res.activite, res.alertes)
    return res, ""


def erreur_ia(message: str) -> None:
    st.warning(textes.SUSPENSION)
    with st.expander(G["detail_technique"]):
        st.code(message)
    st.button(G["reessayer"], key=f"reessayer_{S.ecran}")


def assurer(cle: str, signature: tuple, libelle: str, fonction, **kwargs):
    """Résultat de l'activité pour cette signature d'entrées ; relancé si les entrées ont changé."""
    if S.get(cle) is not None and S.get("sig_" + cle[4:]) == signature:
        return S[cle]
    res, erreur = appel(libelle, fonction, **kwargs)
    if res is None:
        erreur_ia(erreur)
        return None
    S[cle], S["sig_" + cle[4:]] = res, signature
    return res


def image_pour_ia() -> bytes | None:
    if S.image_id and _config.envoyer_image:
        return _image_pour_ia(S.image_id)
    return None


# ----------------------------------------------------------------------------- écrans : 1. besoins
def ecran_choix_image_consignes() -> None:
    c = C["choix_image_consignes"]
    titre("choix_image_consignes")
    st.markdown(c["podcast"])
    media(c["podcast_media"])
    st.markdown(c["consignes"])
    temoignage(c["temoignage"], "image")
    nav()


@st.dialog(C["choix_image"]["dialogue_titre"], width="medium")
def dialogue_image(image_id: int) -> None:
    c = C["choix_image"]
    st.markdown(c["dialogue_corps"])
    st.image(str(images()[image_id]["chemin"]), width=360)
    gauche, droite = st.columns(2)
    with gauche:
        if st.button(c["dialogue_annuler"], key="image_annuler"):
            st.rerun()
    with droite:
        if st.button(c["dialogue_valider"], key="image_valider", type="primary"):
            if S.image_id != image_id:       # autre image : les mots associés changent, la sélection repart de zéro
                S.image_id = image_id
                oublier("w_choix_mot_")
            aller("raisons_image")
            st.rerun()


def ecran_choix_image() -> None:
    c = C["choix_image"]
    titre("choix_image")
    md("choix_image")
    if S.image_id:
        st.caption("Image actuellement choisie :")
        image_choisie(160)
    ids = list(images())
    for debut in range(0, len(ids), COLONNES_GRILLE):
        colonnes = st.columns(COLONNES_GRILLE)
        for colonne, image_id in zip(colonnes, ids[debut:debut + COLONNES_GRILLE]):
            with colonne:
                st.image(str(images()[image_id]["chemin"]), width="stretch")
                if st.button(c["bouton"], key=f"choisir_{image_id}"):
                    dialogue_image(image_id)
    nav(suivant=bool(S.image_id))


def lire_puis_avancer(champ: str, texte: str) -> None:
    """L'IA lit le texte libre (détresse) avant de passer à l'écran suivant.

    Un appel par texte différent. Si une détresse est repérée (modèle ou mots-clés), le message s'affiche
    sur l'écran et on y reste ; un nouveau clic avec le même texte laisse continuer.
    """
    if S[f"lu_{champ}"] != texte:
        res, erreur = appel(G["attente_lecture"], activites.lire_saisie, champ=champ, texte=texte)
        if res is None:
            erreur_ia(erreur)
            return
        S[f"lu_{champ}"] = texte
        if res.detresse:
            st.rerun()
    avancer()
    st.rerun()


def ecran_raisons_image() -> None:
    titre("raisons_image")
    image_choisie(320)
    md("raisons_image")
    st.text_area(C["raisons_image"]["champ"], key="w_raisons", max_chars=1000)
    afficher_detresse()

    def suivant() -> None:
        texte = S.w_raisons.strip()
        if texte:
            lire_puis_avancer("raisons_image", texte)
        else:                                  # rien à lire : on avance
            avancer()
            st.rerun()
    nav(sur_suivant=suivant)


def ecran_mots() -> None:
    c = C["mots"]
    titre("mots")
    temoignage(c["temoignage"], "idees")
    md("mots")
    with st.expander(c["panier_titre"]):
        md("mots", "panier")
    gauche, droite = st.columns(2)
    with gauche:
        image_choisie(360)
    with droite:
        st.markdown(f"**{c['label']}**")
        for i, mot in enumerate(images()[S.image_id]["mots"]):
            st.checkbox(mot, key=f"w_choix_mot_{i}")
    if not mots_choisis():
        st.caption(c["minimum"])
    nav(suivant=bool(mots_choisis()))


def ecran_mots_complementaires() -> None:
    c = C["mots_complementaires"]
    titre("mots_complementaires")
    gauche, droite = st.columns([1, 1])
    with gauche:
        image_choisie(240)
    with droite:
        st.markdown("**Mots sélectionnés :** " + ", ".join(mots_choisis()))
    md("mots_complementaires")
    for i in range(NB_LIBRES):
        st.text_input(f"Mot complémentaire {i + 1}", key=f"w_mots_libres_{i}", max_chars=60,
                      placeholder=c["placeholder"], label_visibility="collapsed")
    nav()


def ecran_reflexion() -> None:
    c = C["reflexion"]
    titre("reflexion")
    md("reflexion")
    st.markdown(f"**{c['question']}**")
    st.markdown(c["consigne"])
    st.text_area(c["question"], key="w_reflexion", max_chars=1000, label_visibility="collapsed")
    nav()


def ecran_souhait_intro() -> None:
    c = C["souhait_intro"]
    titre("souhait_intro")
    md("souhait_intro")
    with st.expander(c["autres_titre"]):
        md("souhait_intro", "autres")
    temoignage(c["temoignage"], "souhait")
    st.markdown(c["souhait_sophie"])
    nav()


def ecran_souhait() -> None:
    c = C["souhait"]
    titre("souhait")
    md("souhait")
    st.caption("Pour commencer, vous pouvez écrire : " + " ou ".join(f"« {a} »" for a in c["amorces"]))
    st.text_area(c["champ"], key="w_souhait", max_chars=600)

    def suivant() -> None:
        texte = souhait()
        if not texte:
            st.warning(c["erreur_vide"])
            return
        lire_puis_avancer("souhait", texte)
    afficher_detresse()
    nav(sur_suivant=suivant)


def ecran_besoins_conclusion() -> None:
    c = C["besoins_conclusion"]
    titre("besoins_conclusion")
    md("besoins_conclusion")
    with st.expander(c["regle_titre"]):
        md("besoins_conclusion", "regle")
    nav()


# ----------------------------------------------------------------------------- écrans : 2. motto
def ecran_motto_intro() -> None:
    titre("motto_intro")
    md("motto_intro")
    nav()


def ecran_motto_infographie() -> None:
    titre("motto_infographie")
    md("motto_infographie")
    media(C["motto_infographie"]["media"])
    nav()


def ecran_motto_synthese() -> None:
    c = C["motto_synthese"]
    titre("motto_synthese")
    md("motto_synthese")
    synthese()
    temoignage(c["temoignage"], "motto")
    st.markdown(c["motto_sophie"])
    nav()


def ecran_motto_navigation() -> None:
    titre("motto_navigation")
    md("motto_navigation")
    nav()


def ecran_motto_propositions() -> None:
    c = C["motto_propositions"]
    titre("motto_propositions")
    st.caption(G["genere_ia"])
    afficher_detresse()
    md("motto_propositions")
    st.caption(c["aide_cliquables"])
    panneaux_motto()
    res = assurer("res_phrases", (S.image_id, idees_favorites(), souhait()), G["attente"],
                  activites.proposer_mottos, image_jpeg=image_pour_ia(), idees=idees_favorites(), souhait=souhait())
    if res is not None:
        for n, phrase in enumerate(res.donnees["phrases"], 1):
            with st.container(border=True):
                st.markdown(phrase["rendu"])
                st.pills(f"Mots cliquables de la phrase {n}", phrase["cliquables"], selection_mode="multi",
                         key=f"w_seg_{res.id}_{n}", label_visibility="collapsed")
    nav(suivant=res is not None)


def inserer_phrase(phrase: str) -> None:
    """Rappel du bouton « placer cette phrase » (exécuté avant le réaffichage : la clé du champ est modifiable)."""
    S.w_motto_saisie = phrase[:300]


def composeur_phrase(choix: list[str]) -> None:
    """Composer une phrase : mots retenus à glisser-déposer, avec du texte libre avant, entre et après."""
    c = C["motto_redaction"]
    st.markdown(f"**{c['composeur_titre']}**")
    if not choix:
        st.caption(c["composeur_vide"])
        return
    st.caption(c["composeur_aide"])
    ordre = list(choix)
    if sort_items is not None and len(choix) > 1:
        rendu = sort_items(choix)
        if isinstance(rendu, list) and sorted(rendu) == sorted(choix):    # garde-fou : mêmes mots, autre ordre
            ordre = rendu
    elif sort_items is None:
        st.caption(c["composeur_sans_glisser"])
    avant = st.text_input(c["composeur_avant"], key="w_comp_avant", placeholder=c["composeur_placeholder"])
    couples = []
    for mot in ordre:
        gauche, droite = st.columns([1, 3])
        with gauche:
            st.markdown(f"**{mot}**")
        with droite:
            apres = st.text_input(f"{c['composeur_apres']} {mot}", key=f"w_comp_apres_{mot.lower()}",
                                  placeholder=c["composeur_placeholder"], label_visibility="collapsed")
        couples.append((mot, apres))
    phrase = checks.assembler_phrase(avant, couples)
    st.markdown(f"**{c['composeur_apercu']}** {phrase}")
    st.button(c["composeur_inserer"], key="comp_inserer", on_click=inserer_phrase, args=(phrase,))


def ecran_motto_redaction() -> None:
    c = C["motto_redaction"]
    titre("motto_redaction")
    afficher_detresse()
    md("motto_redaction")
    panneaux_motto()
    st.markdown(f"**{c['selection_titre']}**")
    choix = selection_courante()
    st.markdown(" / ".join(choix) if choix else c["selection_vide"])
    composeur_phrase(choix)
    saisie = st.text_area(c["champ"], key="w_motto_saisie", max_chars=300, height=100)
    motto = saisie.strip()

    def verifier() -> None:
        if not motto:
            st.warning(c["erreur_vide"])
            return
        if S.res_verdict is not None and S.motto == motto:      # déjà vérifié tel quel : pas de nouvel appel
            aller("motto_feedback")
            st.rerun()
        res, erreur = appel(G["attente_verification"], activites.verifier_motto, motto=motto)
        if res is None:
            erreur_ia(erreur)
            return
        S.motto, S.res_verdict = motto, res
        S.version_amelio += 1
        aller("motto_feedback")
        st.rerun()
    nav(libelle=c["bouton"], sur_suivant=verifier)


@st.dialog(C["motto_feedback"]["dialogue_titre"], width="medium")
def dialogue_motto_non_conforme() -> None:
    c = C["motto_feedback"]
    st.markdown(c["dialogue_corps"])
    for crit in S.res_verdict.donnees["criteres"]:
        if not crit["respecte"]:
            st.markdown(f"- **{crit['intitule']}** : {crit['explication']}")
    gauche, droite = st.columns(2)
    with gauche:
        if st.button(c["dialogue_ameliorer"], key="alerte_ameliorer", type="primary"):
            st.rerun()
    with droite:
        if st.button(c["dialogue_continuer"], key="alerte_continuer"):
            aller("motto_final")
            st.rerun()


def ecran_motto_feedback() -> None:
    c = C["motto_feedback"]
    v = S.res_verdict.donnees
    titre("motto_feedback")
    afficher_detresse()
    panneaux_motto()
    st.markdown(f"**{c['mon_motto']}**")
    st.info(f"« {S.motto} »")
    if v["conforme"]:
        st.success(textes.MOTTO_CONFORME)
    else:
        st.markdown(f"**{c['points']}**")
        for crit in v["criteres"]:
            if not crit["respecte"]:
                st.markdown(f"- **{crit['intitule']}** : {crit['explication']}")
        if v["suggestion"]:
            st.markdown(f"**{c['exemple']}**")
            st.info(f"« {v['suggestion']} »")
        st.markdown(f"**{c['ameliore']}**")
        st.caption(c["ameliore_aide"])
        st.text_area(c["ameliore"], key=f"w_amelio_{S.version_amelio}", max_chars=300, height=100,
                     label_visibility="collapsed")
    if S.pop("alerte_motto", False):      # consommé tout de suite : une fermeture par la croix ne le rouvre pas
        dialogue_motto_non_conforme()

    def suivant_feedback() -> None:
        nouveau = (S.get(f"w_amelio_{S.version_amelio}") or "").strip()
        if nouveau and nouveau != S.motto:       # motto modifié : nouvelle vérification par l'IA
            res, erreur = appel(G["attente_verification"], activites.verifier_motto, motto=nouveau)
            if res is None:
                erreur_ia(erreur)
                return
            S.motto, S.res_verdict = nouveau, res
            S.version_amelio += 1
        if S.res_verdict.donnees["conforme"]:
            aller("motto_final")
        else:
            S.alerte_motto = True
        st.rerun()
    nav(sur_suivant=suivant_feedback)


def ecran_motto_final() -> None:
    c = C["motto_final"]
    titre("motto_final")
    md("motto_final")
    synthese()
    st.markdown(f"**{c['mon_motto']}**")
    st.success(f"« {S.motto} »")
    nav()


# ----------------------------------------------------------------------------- écrans : 3. ressources
def ecran_ressources_intro() -> None:
    titre("ressources_intro")
    md("ressources_intro")
    nav()


def ecran_ressources_video() -> None:
    c = C["ressources_video"]
    titre("ressources_video")
    md("ressources_video")
    media(c["media"])
    with st.expander(c["resume_titre"]):
        md("ressources_video", "resume")
    nav()


def ecran_aide_theorie() -> None:
    titre("aide_theorie")
    md("aide_theorie")
    md("aide_theorie", "usages")
    nav()


def ecran_aide_panier() -> None:
    c = C["aide_panier"]
    titre("aide_panier")
    md("aide_panier")
    with st.expander(c["revoir_titre"]):
        gauche, droite = st.columns(2)
        with gauche:
            image_choisie(280)
        with droite:
            st.markdown(f"**{C['motto_final']['mon_motto']}**")
            st.info(f"« {S.motto} »")
    st.markdown(c["suite"])
    temoignage(c["temoignage"], "aide_memoire")
    nav()


def _choix_idees(res_cle: str, colonne_gauche: str, colonne_droite: str, prefixe: str,
                 libelle_gauche: str, libelle_droite: str, etiquette) -> tuple[list[str], list[str]]:
    """Deux colonnes de cases à cocher ; renvoie les éléments cochés de chaque colonne."""
    res = S[res_cle]
    cochees = ([], [])
    gauche, droite = st.columns(2)
    for colonne, cle, titre_colonne, sortie, pref in ((gauche, colonne_gauche, libelle_gauche, cochees[0], "g"),
                                                      (droite, colonne_droite, libelle_droite, cochees[1], "d")):
        with colonne:
            st.markdown(f"**{titre_colonne}**")
            for i, element in enumerate(res.donnees[cle]):
                if st.checkbox(etiquette(element), key=f"w_{prefixe}_{pref}_{res.id}_{i}"):
                    sortie.append(element)
    return cochees


def _etiquette_aide(idee: dict) -> str:
    return idee["idee"] if idee["categorie"] == "objet" else f"{idee['idee']} ({idee['categorie']})"


def ecran_aide_ia() -> None:
    c = C["aide_ia"]
    titre("aide_ia")
    st.caption(G["genere_ia"])
    afficher_detresse()
    md("aide_ia")
    res = assurer("res_aide", (S.motto, S.image_id, idees_favorites(), souhait()), G["attente"],
                  activites.proposer_aide_memoire, image_jpeg=image_pour_ia(), motto=S.motto,
                  idees=idees_favorites(), souhait=souhait())
    ok = False
    if res is not None:
        fixes, mobiles = _choix_idees("res_aide", "fixes", "mobiles", "aide", c["colonne_fixes"],
                                      c["colonne_mobiles"], _etiquette_aide)
        ok = bool(fixes and mobiles)
        if not ok:
            st.caption(c["erreur_minimum"])
    nav(suivant=ok)


def _saisie_libre(bloc: str, prefixe: str) -> None:
    c = C[bloc]
    for i in range(NB_LIBRES):
        gauche, droite = st.columns([3, 1])
        with gauche:
            st.text_input(f"Idée {i + 1}", key=f"w_{prefixe}_{i}", max_chars=120,
                          placeholder=C["mots_complementaires"]["placeholder"], label_visibility="collapsed")
        with droite:
            st.selectbox("Type", c["types"], key=f"w_{prefixe}_type_{i}", label_visibility="collapsed")


def ecran_aide_libres() -> None:
    c = C["aide_libres"]
    titre("aide_libres")
    afficher_detresse()
    md("aide_libres")
    _saisie_libre("aide_libres", "libre_aide")
    st.caption(c["note"])
    nav()


def _lister(elements: list[str], vide: str) -> None:
    if elements:
        for e in elements:
            st.markdown(f"- {e}")
    else:
        st.caption(vide)


def ecran_aide_recap() -> None:
    c = C["aide_recap"]
    ia = C["aide_ia"]
    titre("aide_recap")
    md("aide_recap")
    res = S.res_aide
    fixes, mobiles = [], []
    if res is not None:
        fixes = [_etiquette_aide(i) for n, i in enumerate(res.donnees["fixes"])
                 if S.get(f"w_aide_g_{res.id}_{n}")]
        mobiles = [_etiquette_aide(i) for n, i in enumerate(res.donnees["mobiles"])
                   if S.get(f"w_aide_d_{res.id}_{n}")]
    for texte, type_ in libres("libre_aide"):
        (fixes if type_ == C["aide_libres"]["types"][0] else mobiles).append(texte)
    gauche, droite = st.columns(2)
    with gauche:
        st.markdown(f"**{ia['colonne_fixes']}**")
        _lister(fixes, c["aucun"])
    with droite:
        st.markdown(f"**{ia['colonne_mobiles']}**")
        _lister(mobiles, c["aucun"])
    md("aide_recap", "action")
    nav()


def ecran_mouvements_theorie() -> None:
    c = C["mouvements_theorie"]
    titre("mouvements_theorie")
    md("mouvements_theorie")
    st.markdown(c["experiences"])
    media(c["experience_1"])
    media(c["experience_2"])
    nav()


def ecran_mouvements_types() -> None:
    c = C["mouvements_types"]
    titre("mouvements_types")
    md("mouvements_types")
    st.markdown(c["panier"])
    temoignage(c["temoignage"], "mouvements")
    nav()


def ecran_mouvements_ia() -> None:
    c = C["mouvements_ia"]
    titre("mouvements_ia")
    st.caption(G["genere_ia"])
    afficher_detresse()
    md("mouvements_ia")
    st.caption(c["avertissement"])
    res = assurer("res_mouv", (S.motto, S.image_id, idees_favorites(), souhait()), G["attente"],
                  activites.proposer_mouvements, image_jpeg=image_pour_ia(), motto=S.motto,
                  idees=idees_favorites(), souhait=souhait())
    ok = False
    if res is not None:
        macro, micro = _choix_idees("res_mouv", "macro", "micro", "mouv", c["colonne_macro"],
                                    c["colonne_micro"], lambda m: m)
        ok = bool(macro and micro)
        if not ok:
            st.caption(c["erreur_minimum"])
    nav(suivant=ok)


def ecran_mouvements_libres() -> None:
    titre("mouvements_libres")
    afficher_detresse()
    md("mouvements_libres")
    _saisie_libre("mouvements_libres", "libre_mouv")
    nav()


def recap_donnees() -> dict:
    """Tous les choix de l'apprenant et les ressources associées (pour l'écran et le fichier téléchargé)."""
    aide, mouv = S.res_aide, S.res_mouv
    fixes, mobiles, macro, micro = [], [], [], []
    if aide is not None:
        fixes = [_etiquette_aide(i) for n, i in enumerate(aide.donnees["fixes"]) if S.get(f"w_aide_g_{aide.id}_{n}")]
        mobiles = [_etiquette_aide(i) for n, i in enumerate(aide.donnees["mobiles"])
                   if S.get(f"w_aide_d_{aide.id}_{n}")]
    for texte, type_ in libres("libre_aide"):
        (fixes if type_ == C["aide_libres"]["types"][0] else mobiles).append(texte)
    if mouv is not None:
        macro = [m for n, m in enumerate(mouv.donnees["macro"]) if S.get(f"w_mouv_g_{mouv.id}_{n}")]
        micro = [m for n, m in enumerate(mouv.donnees["micro"]) if S.get(f"w_mouv_d_{mouv.id}_{n}")]
    for texte, type_ in libres("libre_mouv"):
        (macro if type_ == C["mouvements_libres"]["types"][0] else micro).append(texte)
    verdict = S.res_verdict.donnees if S.res_verdict is not None else None
    return {"image_id": S.image_id, "raisons": S.w_raisons.strip(), "mots": mots_choisis(),
            "mots_complementaires": mots_complementaires(), "reflexion": S.w_reflexion.strip(),
            "souhait": souhait(), "motto": S.motto,
            "motto_non_conforme": bool(verdict is not None and not verdict["conforme"]),
            "aide_fixes": fixes, "aide_mobiles": mobiles, "mouv_macro": macro, "mouv_micro": micro}


def ecran_recap() -> None:
    c = C["recap"]
    st.header(c["titre"])
    st.markdown(c["corps"])
    donnees = recap_donnees()
    image = images()[S.image_id]["chemin"].read_bytes() if S.image_id else None
    gauche, droite = st.columns(2)
    with gauche:
        st.download_button(c["telecharger"], data=recapitulatif.html(donnees, c, image).encode("utf-8"),
                           file_name=c["fichier"], mime="text/html", type="primary", key="telecharger_recap")
    with droite:
        st.button(G["recommencer"], key="recap_recommencer", on_click=recommencer)
    st.caption(c["aide_telechargement"])
    image_choisie(280)
    for titre_section, lignes, en_liste in recapitulatif.sections(donnees, c):
        st.markdown(f"**{titre_section}**")
        for ligne in lignes:
            st.markdown(f"- {ligne}" if en_liste else ligne)
    st.write("")
    st.markdown(G["fin"])
    nav(dernier=True)


ECRANS = {nom: globals()[f"ecran_{nom}"] for nom in ORDRE}
LARGE = {"choix_image"}      # écrans qui occupent toute la largeur (grille d'images)


# ----------------------------------------------------------------------------- barre latérale et exécution
def barre_laterale() -> None:
    with st.sidebar:
        st.header(G["titre_application"])
        ecran = S.ecran
        etapes = C["menu"]["etapes"]
        numero = 0
        for n, debut in enumerate(DEBUT_ETAPES):
            if ORDRE.index(ecran) >= ORDRE.index(debut):
                numero = n + 1
        st.progress(ORDRE.index(ecran) / (len(ORDRE) - 1),
                    text=G["progression"].format(numero=numero, total=len(DEBUT_ETAPES),
                                                 titre=etapes[numero - 1]["titre"]))
        st.button(G["recommencer"], key="barre_recommencer", on_click=recommencer)
        with st.expander(G["info_technique"]):
            st.caption(f"Fournisseur : {_config.label}  \nModèle : {_config.modele}  \n"
                       f"Prompts : {prompts.VERSION_PROMPTS}  \n"
                       f"Image envoyée au modèle : {'oui' if _config.envoyer_image else 'non'}")


def executer(config: llm.Config) -> None:
    """Point d'entrée appelé par app.py à chaque exécution du script."""
    global _config
    _config = config
    init_etat()
    barre_laterale()
    if S.ecran in LARGE:
        ECRANS[S.ecran]()
    else:
        _, centre, _ = st.columns([1, 4, 1])
        with centre:
            ECRANS[S.ecran]()
