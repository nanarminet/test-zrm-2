"""Les 5 activités IA (lecture des textes libres, phrases du motto, vérification, aide-mémoire, mouvements) : appel au modèle + contrôles en code + une relance corrective.

Chaque activité renvoie un `ResultatActivite` :
  - `donnees`  : ce que l'interface affiche ;
  - `detresse` : vrai si le modèle OU le filet de sécurité en code signale une détresse ;
  - `alertes`  : écarts non bloquants (utiles en phase de test) ;
  - `journal`  : une entrée par appel (prompt résumé, réponse brute, tokens, durée).
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from io import BytesIO

from PIL import Image

import checks
import llm
import prompts
import schemas

log = logging.getLogger("zrm.ia")     # journal technique (durées, tokens, problèmes), jamais les saisies

MAX_TENTATIVES = 2        # appel initial + 1 relance corrective
MAX_IMAGE_SIDE = 1024     # px : l'image est réduite avant envoi (comme dans le premier test)

# Nom du contrat JSON (schemas.py) -> fichier de prompt (prompts/*.md)
FICHIER_PROMPT = {"propositions_motto": "motto_propositions", "verification_motto": "motto_verification",
                  "aide_memoire": "aide_memoire", "mouvements": "mouvements", "lecture_saisie": "saisie_lecture"}


@dataclass
class ResultatActivite:
    activite: str
    donnees: dict
    detresse: bool = False
    alertes: list[str] = field(default_factory=list)
    journal: list[dict] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


def preparer_image(image_bytes: bytes) -> bytes:
    """Réduit l'image (côté max MAX_IMAGE_SIDE) et la convertit en JPEG."""
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    tampon = BytesIO()
    image.save(tampon, format="JPEG", quality=90)
    return tampon.getvalue()


def _textes(objet):
    """Tous les textes (valeurs) d'une réponse JSON, à plat."""
    if isinstance(objet, str):
        yield objet
    elif isinstance(objet, dict):
        for v in objet.values():
            yield from _textes(v)
    elif isinstance(objet, list):
        for v in objet:
            yield from _textes(v)


def _sans_emojis(objet):
    """Copie de la réponse sans emojis ni pictogrammes (dernier filet de sécurité)."""
    if isinstance(objet, str):
        return checks.retirer_emojis(objet)
    if isinstance(objet, dict):
        return {k: _sans_emojis(v) for k, v in objet.items()}
    if isinstance(objet, list):
        return [_sans_emojis(v) for v in objet]
    return objet


def _consigne_image(image_jpeg: bytes | None) -> str:
    return "" if image_jpeg else "\nAucune image n'est jointe : appuie-toi sur les mots et le souhait."


def _executer(config: llm.Config, *, activite: str, user_msg: dict, evaluer, temperature: float,
              max_tokens: int, journal: list[dict]):
    """Appelle le modèle, contrôle la réponse, relance une fois avec la liste des défauts.

    `evaluer(donnees) -> (bloquants, alertes)` : les `bloquants` déclenchent la relance ;
    s'ils persistent, la dernière réponse est renvoyée avec ses défauts en alertes.
    Une réponse hors contrat JSON qui persiste lève LLMSortieInvalide.
    """
    schema = schemas.SCHEMAS[activite]
    messages = [{"role": "system", "content": prompts.construire_system(FICHIER_PROMPT[activite])}, user_msg]
    structure: list[str] = []
    bloquants: list[str] = []
    alertes: list[str] = []
    reponse = None
    for tentative in range(1, MAX_TENTATIVES + 1):
        try:
            reponse = llm.appeler(config, nom=activite, messages=messages, schema=schema,
                                  temperature=temperature, max_tokens=max_tokens)
        except llm.LLMSortieInvalide as e:   # JSON illisible ou tronqué : on retente une fois à l'identique
            journal.append({"activite": activite, "tentative": tentative, "fournisseur": config.fournisseur,
                            "modele": config.modele, "problemes": [str(e)], "messages": llm.resumer_messages(messages)})
            if tentative == MAX_TENTATIVES:
                raise
            continue
        avec_emojis = any(checks.contient_emoji(t) for t in _textes(reponse.donnees))
        reponse.donnees = _sans_emojis(reponse.donnees)      # jamais d'emoji affiché, même si la relance échoue
        structure = schemas.valider(activite, reponse.donnees)
        bloquants, alertes = (structure, []) if structure else evaluer(reponse.donnees)
        if avec_emojis:
            bloquants = list(bloquants) + ["la réponse contient des emojis ou des pictogrammes : "
                                           "n'en utilise aucun, seulement des mots et la ponctuation ordinaire"]
        journal.append({
            "activite": activite, "tentative": tentative, "fournisseur": config.fournisseur,
            "modele": config.modele, "format": reponse.format_utilise, "latence_s": reponse.latence_s,
            "usage": reponse.usage, "problemes": list(bloquants), "alertes": list(alertes),
            "messages": llm.resumer_messages(messages), "brut": reponse.brut})
        log.info("activite=%s tentative=%d modele=%s format=%s latence=%ss usage=%s problemes=%d alertes=%d",
                 activite, tentative, config.modele, reponse.format_utilise, reponse.latence_s,
                 reponse.usage, len(bloquants), len(alertes))
        if not bloquants:
            return reponse, alertes
        if tentative < MAX_TENTATIVES:
            liste = "\n".join(f"- {p}" for p in bloquants)
            messages = messages + [
                {"role": "assistant", "content": reponse.brut},
                {"role": "user", "content": "Un contrôle automatique a refusé ta réponse pour ces raisons :\n"
                                            f"{liste}\nCorrige ces points et renvoie l'objet JSON complet, "
                                            "au même format, sans rien d'autre."}]
    if structure:
        raise llm.LLMSortieInvalide("réponse hors contrat après relance : " + " ; ".join(structure))
    return reponse, alertes + [f"non corrigé après relance : {p}" for p in bloquants]


def _detresse(reponse: llm.Reponse, *saisies: str) -> bool:
    return bool(reponse.donnees.get("detresse")) or checks.detecter_detresse(*saisies)


# --------------------------------------------------------------------------------------
# 0. Lecture d'un texte libre (souhait, raisons du choix d'image) : repérer une détresse
# --------------------------------------------------------------------------------------
CHAMPS_LUS = ("raisons_image", "mots_complementaires", "reflexion", "souhait", "idees_aide_memoire",
              "idees_mouvements")


def lire_saisie(config: llm.Config, *, textes: dict[str, str]) -> ResultatActivite:
    """Le modèle lit les textes libres d'un écran et ne renvoie que le drapeau de détresse.

    `textes` : {nom du champ (CHAMPS_LUS): texte}. Le code ajoute son filet de mots-clés.
    """
    inconnus = [c for c in textes if c not in CHAMPS_LUS]
    if inconnus or not any(t.strip() for t in textes.values()):
        raise ValueError(f"champs inconnus ou textes vides : {inconnus or list(textes)}")
    journal: list[dict] = []
    user = llm.message_utilisateur(prompts.formater_saisies(**textes)
                                   + "\nLis ces textes et renseigne uniquement `detresse` (JSON uniquement).")
    rep, alertes = _executer(config, activite="lecture_saisie", user_msg=user, evaluer=lambda d: ([], []),
                             temperature=0.0, max_tokens=300, journal=journal)
    return ResultatActivite("lecture_saisie", {}, _detresse(rep, *textes.values()), alertes, journal)


# --------------------------------------------------------------------------------------
# 1. Panier à idées du motto : 5 phrases
# --------------------------------------------------------------------------------------
def _phrase_affichable(ph: dict) -> dict:
    """Phrase prête pour l'interface : texte, rendu Markdown (mots cliquables en gras) et mots cliquables."""
    mots = [{"texte": m["texte"].strip(), "nature": m["nature"]} for m in ph["mots"]]
    morceaux_par_mot = [checks.decouper_mot(m["texte"], m["nature"], debut_de_phrase=(n == 0))
                        for n, m in enumerate(mots)]
    rendu, cliquables, vus = [], [], set()
    for morceaux in morceaux_par_mot:
        rendu.append("".join(f"**{checks.echapper_markdown(x['texte'])}**" if x["cliquable"]
                             else checks.echapper_markdown(x["texte"]) for x in morceaux))
        for x in morceaux:
            if x["cliquable"] and x["mot"].lower() not in vus:
                vus.add(x["mot"].lower())
                cliquables.append(x["mot"])
    return {"texte": " ".join(m["texte"] for m in mots), "rendu": " ".join(rendu), "cliquables": cliquables,
            "mots": mots}


def proposer_mottos(config: llm.Config, *, image_jpeg: bytes | None, idees: str, souhait: str) -> ResultatActivite:
    """5 phrases dont les verbes, noms communs, noms propres et adjectifs sont cliquables.

    `donnees` = {"phrases": [{"texte", "rendu", "cliquables", "mots"}]}.
    """
    journal: list[dict] = []
    user = llm.message_utilisateur(
        prompts.formater_saisies(idees_favorites=idees, souhait=souhait)
        + _consigne_image(image_jpeg) + "\nPropose les 5 phrases (JSON uniquement).", image_jpeg)

    def evaluer(d):
        bloquants, alertes, textes = [], [], []
        for i, brut in enumerate(d["phrases"], 1):
            ph = _phrase_affichable(brut)
            textes.append(ph["texte"])
            bloquants += [f"phrase {i} : {p}" for p in checks.verifier_phrase_motto(ph["texte"])]
            if any(len(m["texte"].split()) != 1 for m in ph["mots"]):
                bloquants.append(f"phrase {i} : chaque élément de « mots » doit être un seul mot")
            if len(ph["cliquables"]) < checks.MOTS_CLIQUABLES_MIN:
                bloquants.append(f"phrase {i} : seulement {len(ph['cliquables'])} mots cliquables (verbes, noms "
                                 f"communs, noms propres, adjectifs) ; il en faut au moins {checks.MOTS_CLIQUABLES_MIN}")
            for m in ph["mots"]:       # mot-outil étiqueté verbe/nom : corrigé par le code, signalé dans les journaux
                if m["nature"] in checks.NATURES_CLIQUABLES and not any(
                        x["cliquable"] for x in checks.decouper_mot(m["texte"], m["nature"])):
                    alertes.append(f"phrase {i} : « {m['texte']} » étiqueté {m['nature']} mais c'est un mot-outil "
                                   "ou une ponctuation (rendu non cliquable)")
        for i, j, communs in checks.chevauchements(textes):
            bloquants.append(f"phrases {i} et {j} : mots communs ({', '.join(communs)}) ; les 5 phrases doivent "
                             "utiliser des mots différents")
        return bloquants, alertes

    rep, alertes = _executer(config, activite="propositions_motto", user_msg=user, evaluer=evaluer,
                             temperature=0.9, max_tokens=3500, journal=journal)
    phrases = [_phrase_affichable(ph) for ph in rep.donnees["phrases"]]
    return ResultatActivite("propositions_motto", {"phrases": phrases}, _detresse(rep, idees, souhait),
                            alertes, journal)


# --------------------------------------------------------------------------------------
# 2. Vérification du motto : 10 critères, feedback, une suggestion
# --------------------------------------------------------------------------------------
def _forcer_ko(criteres: list[dict], id_critere: str, explication: str) -> None:
    for c in criteres:
        if c["id"] == id_critere and c["respecte"]:
            c.update(respecte=False, explication=explication, source="code")


def construire_verdict(donnees: dict, motto: str) -> dict:
    """Verdict affichable : réponse du modèle + corrections des critères purement mécaniques."""
    criteres = []
    for meta in schemas.CRITERES:
        brut = donnees["criteres"][meta["id"]]
        criteres.append({"id": meta["id"], "intitule": meta["intitule"], "priorite": meta["priorite"],
                         "respecte": brut["respecte"], "explication": brut["explication"].strip(), "source": "ia"})
    if checks.a_invitation_explicite(motto):       # tournures admises d'office : le modèle ne peut pas les refuser
        for c in criteres:
            if c["id"] == "invitation" and not c["respecte"]:
                c.update(respecte=True, explication="", source="code")
    if (neg := checks.trouver_negation(motto)):
        _forcer_ko(criteres, "emotions",
                   f"Votre motto contient une négation (« {neg} »). Pour garder un bilan émotionnel positif, "
                   "formulez ce que vous voulez vivre plutôt que ce que vous écartez.")
    if (contr := checks.trouver_contrainte(motto)):
        _forcer_ko(criteres, "contrainte",
                   f"« {contr} » exprime une obligation. Remplacez-la par une invitation ou une autorisation, "
                   "par exemple « Je m'autorise à… » ou « Je savoure… ».")
    if not checks.a_premiere_personne(motto):
        _forcer_ko(criteres, "premiere_personne",
                   "Votre motto n'est pas écrit à la première personne. Reformulez-le avec « je », "
                   "par exemple « Je m'autorise… » ou « Je savoure… ».")
    return {"criteres": criteres, "conforme": all(c["respecte"] for c in criteres),
            "suggestion": donnees["suggestion"].strip()}


def verifier_motto(config: llm.Config, *, motto: str) -> ResultatActivite:
    journal: list[dict] = []
    user = llm.message_utilisateur(prompts.formater_saisies(motto=motto) + "\nVérifie ce motto (JSON uniquement).")
    verdict_final: dict = {}

    def evaluer(d):
        verdict = construire_verdict(d, motto)
        verdict_final.clear()
        verdict_final.update(verdict)
        bloquants = [f"critère « {c['id']} » non respecté sans explication" for c in verdict["criteres"]
                     if not c["respecte"] and not c["explication"]]
        if not verdict["conforme"]:
            if not verdict["suggestion"]:
                bloquants.append("au moins un critère n'est pas respecté (contrôle automatique inclus) : "
                                 "fournis une suggestion de motto qui les corrige tous")
            else:
                bloquants += [f"suggestion : {p}" for p in
                              checks.verifier_phrase_motto(verdict["suggestion"], bornes=False)]
        return bloquants, []

    rep, alertes = _executer(config, activite="verification_motto", user_msg=user, evaluer=evaluer,
                             temperature=0.2, max_tokens=2500, journal=journal)
    if verdict_final["conforme"]:
        verdict_final["suggestion"] = ""
    return ResultatActivite("verification_motto", dict(verdict_final), _detresse(rep, motto), alertes, journal)


# --------------------------------------------------------------------------------------
# 3. Aide-mémoire : 4 fixes + 4 mobiles
# --------------------------------------------------------------------------------------
_SUPPORT_ECRAN = re.compile(r"t[ée]l[ée]phone|smartphone|portable|mobile|tablette|ordinateur|\bpc\b|bureau", re.I)
_SEMBLE_MOBILE = re.compile(r"porte-cl[ée]s|bracelet|collier|marque-page|sonnerie|portefeuille|\bsac\b|poche|montre", re.I)
_SEMBLE_FIXE = re.compile(r"frigo|r[ée]frig[ée]rateur|\bmur\b|mural|tableau|salon|cuisine|chambre|fen[êe]tre|canap[ée]", re.I)
MIN_OBJETS = 5  # « une majorité d'objets » sur 8 idées


def proposer_aide_memoire(config: llm.Config, *, image_jpeg: bytes | None, motto: str,
                          idees: str = "", souhait: str = "") -> ResultatActivite:
    journal: list[dict] = []
    user = llm.message_utilisateur(
        prompts.formater_saisies(motto=motto, idees_favorites=idees, souhait=souhait)
        + _consigne_image(image_jpeg) + "\nPropose les 4 aide-mémoire fixes et les 4 aide-mémoire mobiles (JSON uniquement).",
        image_jpeg)

    def evaluer(d):
        toutes = d["fixes"] + d["mobiles"]
        bloquants, alertes = [], []
        textes = [i["idee"].strip().lower() for i in toutes]
        if len(set(textes)) < len(textes):
            bloquants.append("des idées sont en double : les 8 idées doivent être différentes")
        nb_objets = sum(1 for i in toutes if i["categorie"] == "objet")
        if nb_objets < MIN_OBJETS:
            bloquants.append(f"seulement {nb_objets} idées de catégorie « objet » sur 8 ; il en faut au moins {MIN_OBJETS}")
        for colonne, classe, motif, semble in (("fixes", "fixe", _SEMBLE_MOBILE, "mobile"),
                                               ("mobiles", "mobile", _SEMBLE_FIXE, "fixe")):
            for i in d[colonne]:
                if motif.search(i["idee"]):
                    alertes.append(f"« {i['idee']} » est classé « {classe} » mais semble {semble} : à vérifier")
        for i in toutes:
            if re.search(r"fond d'[ée]cran", i["idee"], re.I) and not _SUPPORT_ECRAN.search(i["idee"]):
                alertes.append(f"« {i['idee']} » : support du fond d'écran non précisé (fixe ou mobile ?)")
        return bloquants, alertes

    rep, alertes = _executer(config, activite="aide_memoire", user_msg=user, evaluer=evaluer,
                             temperature=0.8, max_tokens=1500, journal=journal)
    donnees = {"fixes": rep.donnees["fixes"], "mobiles": rep.donnees["mobiles"]}
    return ResultatActivite("aide_memoire", donnees, _detresse(rep, motto, idees, souhait), alertes, journal)


# --------------------------------------------------------------------------------------
# 4. Mouvements : 3 macro + 3 micro
# --------------------------------------------------------------------------------------
def proposer_mouvements(config: llm.Config, *, image_jpeg: bytes | None, motto: str,
                        idees: str = "", souhait: str = "") -> ResultatActivite:
    journal: list[dict] = []
    user = llm.message_utilisateur(
        prompts.formater_saisies(motto=motto, idees_favorites=idees, souhait=souhait)
        + _consigne_image(image_jpeg) + "\nPropose les 3 macro-mouvements et les 3 micro-mouvements (JSON uniquement).",
        image_jpeg)

    def evaluer(d):
        tous = [m.strip().lower() for m in d["macro"] + d["micro"]]
        bloquants = ["des mouvements sont en double : les 6 mouvements doivent être différents"] \
            if len(set(tous)) < len(tous) else []
        return bloquants, []

    rep, alertes = _executer(config, activite="mouvements", user_msg=user, evaluer=evaluer,
                             temperature=0.8, max_tokens=1000, journal=journal)
    donnees = {"macro": [m.strip() for m in rep.donnees["macro"]], "micro": [m.strip() for m in rep.donnees["micro"]]}
    return ResultatActivite("mouvements", donnees, _detresse(rep, motto, idees, souhait), alertes, journal)
