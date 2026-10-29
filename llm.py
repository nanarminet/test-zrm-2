"""Appel d'un LLM via l'API « chat completions » compatible OpenAI.

Ollama Cloud et Mistral exposent le même format de requête ; seuls l'URL de base,
le nom du modèle et la clé changent. Ces trois valeurs sont regroupées dans PRESETS :
passer d'un fournisseur à l'autre = changer la clé (et, si les deux clés sont
présentes, LLM_PROVIDER). Aucun import de Streamlit ici, pour rester testable.

Le payload envoyé est volontairement du JSON brut (requests) : les développeurs
peuvent le reprendre tel quel en JS (fetch).
"""
from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass

import requests

REQUEST_TIMEOUT = 120      # secondes
MAX_ESSAIS_RESEAU = 3      # essais pour une même requête (timeout, 429, 5xx)

# Noms vérifiés dans la documentation des fournisseurs (oct. 2026) :
#  - Ollama Cloud : https://ollama.com/v1 (OpenAI-compatible), modèle « gemma4:31b » (vision).
#  - Mistral : https://api.mistral.ai/v1, modèle « mistral-medium-3-5 » (multimodal).
# Changer de modèle : variable LLM_MODEL (ex. « mistral-small-2603 »).
PRESETS = {
    "ollama": {"label": "Ollama Cloud", "base_url": "https://ollama.com/v1",
               "modele": "gemma4:31b", "cle": "OLLAMA_API_KEY"},
    "mistral": {"label": "Mistral", "base_url": "https://api.mistral.ai/v1",
                "modele": "mistral-medium-3-5", "cle": "MISTRAL_API_KEY"},
    "mock": {"label": "Simulation (aucune IA appelée)", "base_url": "", "modele": "mock", "cle": ""},
}


class LLMError(Exception):
    """Erreur de l'appel au modèle."""


class ConfigurationError(LLMError):
    """Clé ou fournisseur mal configuré."""


class LLMIndisponible(LLMError):
    """Service injoignable, clé refusée ou quota dépassé : l'étape doit être suspendue."""


class RequeteRefusee(LLMError):
    """HTTP 400 / 422 : la requête (souvent le format de réponse) a été refusée."""


class LLMSortieInvalide(LLMError):
    """La réponse n'est pas exploitable (JSON illisible, tronquée, hors contrat)."""


@dataclass(frozen=True)
class Config:
    fournisseur: str
    label: str
    base_url: str
    modele: str
    cle: str
    effort_raisonnement: str = ""   # facultatif (LLM_REASONING_EFFORT), non envoyé si vide
    envoyer_image: bool = True      # LLM_ENVOYER_IMAGE=non : le modèle ne reçoit pas l'image (mots et souhait seuls)


@dataclass
class Reponse:
    donnees: dict
    brut: str
    usage: dict
    latence_s: float
    format_utilise: str


def resoudre_config(lire) -> Config:
    """Construit la configuration. `lire(nom)` renvoie la valeur (variable d'environnement ou secret)."""
    def val(nom: str) -> str:
        return (lire(nom) or "").strip()

    fournisseur = val("LLM_PROVIDER").lower()
    if not fournisseur:
        presents = [n for n, p in PRESETS.items() if p["cle"] and val(p["cle"])]
        if len(presents) == 1:
            fournisseur = presents[0]
        elif not presents and not val("LLM_API_KEY"):
            raise ConfigurationError(
                "Aucune clé API trouvée. Définissez OLLAMA_API_KEY (test) ou MISTRAL_API_KEY (production), "
                "ou LLM_PROVIDER=mock pour essayer l'interface sans IA.")
        else:
            raise ConfigurationError(
                "Plusieurs clés (ou LLM_API_KEY seule) : indiquez le fournisseur avec LLM_PROVIDER "
                "(ollama, mistral ou mock).")
    if fournisseur not in PRESETS:
        raise ConfigurationError(f"LLM_PROVIDER « {fournisseur} » inconnu (choix : {', '.join(PRESETS)}).")

    preset = PRESETS[fournisseur]
    cle = val("LLM_API_KEY") or (val(preset["cle"]) if preset["cle"] else "")
    if fournisseur != "mock" and not cle:
        raise ConfigurationError(f"Clé manquante pour {preset['label']} : définissez {preset['cle']}.")
    return Config(
        fournisseur=fournisseur, label=preset["label"],
        base_url=val("LLM_BASE_URL") or preset["base_url"],
        modele=val("LLM_MODEL") or preset["modele"],
        cle=cle, effort_raisonnement=val("LLM_REASONING_EFFORT"),
        envoyer_image=val("LLM_ENVOYER_IMAGE").lower() not in ("0", "non", "no", "false", "faux"))


def message_utilisateur(texte: str, image_jpeg: bytes | None = None) -> dict:
    """Message « user », avec une image éventuelle en data URI (format documenté par Ollama et Mistral)."""
    if not image_jpeg:
        return {"role": "user", "content": texte}
    b64 = base64.b64encode(image_jpeg).decode("ascii")
    return {"role": "user", "content": [
        {"type": "text", "text": texte},
        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{b64}"}]}


def resumer_messages(messages: list[dict]) -> list[dict]:
    """Copie lisible des messages (l'image est remplacée par sa taille) pour le journal."""
    resume = []
    for m in messages:
        contenu = m["content"]
        if isinstance(contenu, list):
            parts = []
            for c in contenu:
                if c.get("type") == "image_url":
                    url = c["image_url"] if isinstance(c["image_url"], str) else c["image_url"].get("url", "")
                    parts.append(f"[image jointe, {len(url) * 3 // 4 // 1024} Ko]")
                else:
                    parts.append(c.get("text", ""))
            contenu = "\n".join(parts)
        resume.append({"role": m["role"], "content": contenu})
    return resume


def extraire_json(texte: str) -> dict:
    """JSON de la réponse, même entouré de ```json … ``` ou de quelques mots."""
    t = (texte or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE).strip()
    candidats = [t]
    debut, fin = t.find("{"), t.rfind("}")
    if debut != -1 and fin > debut:
        candidats.append(t[debut:fin + 1])
    for c in candidats:
        try:
            obj = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise LLMSortieInvalide("la réponse du modèle n'est pas un objet JSON lisible.")


def _contenu_texte(message: dict) -> str:
    """Texte de la réponse ; certains modèles renvoient une liste de blocs (texte, raisonnement…)."""
    contenu = message.get("content")
    if isinstance(contenu, list):
        return "".join(b.get("text", "") for b in contenu if isinstance(b, dict) and b.get("type") == "text")
    return contenu or ""


def _post(config: Config, payload: dict, timeout: int) -> dict:
    url = config.base_url.rstrip("/") + "/chat/completions"
    entetes = {"Authorization": f"Bearer {config.cle}", "Content-Type": "application/json"}
    cause = ""
    for essai in range(1, MAX_ESSAIS_RESEAU + 1):
        attente = min(2 ** (essai - 1), 8)
        try:
            r = requests.post(url, headers=entetes, json=payload, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as e:
            cause = f"réseau ({e.__class__.__name__})"
        else:
            if r.status_code == 200:
                return r.json()
            if r.status_code in (401, 403):
                raise LLMIndisponible(f"clé API refusée par {config.label} (HTTP {r.status_code}).")
            if r.status_code in (400, 422):
                raise RequeteRefusee(f"HTTP {r.status_code} : {r.text[:400]}")
            if r.status_code == 404:
                raise LLMIndisponible(f"modèle ou adresse introuvable chez {config.label} "
                                      f"(HTTP 404, modèle « {config.modele} »).")
            if r.status_code in (408, 409, 429) or r.status_code >= 500:
                cause = f"HTTP {r.status_code}"
                if r.headers.get("Retry-After", "").isdigit():
                    attente = min(int(r.headers["Retry-After"]), 20)
            else:
                raise LLMIndisponible(f"HTTP {r.status_code} : {r.text[:300]}")
        if essai < MAX_ESSAIS_RESEAU:
            time.sleep(attente)
    raise LLMIndisponible(f"{config.label} injoignable après {MAX_ESSAIS_RESEAU} essais ({cause}).")


def appeler(config: Config, *, nom: str, messages: list[dict], schema: dict,
            temperature: float = 0.7, max_tokens: int = 2000, timeout: int = REQUEST_TIMEOUT) -> Reponse:
    """Appelle le modèle et renvoie le JSON de la réponse.

    Format de réponse : `json_schema` d'abord ; si le fournisseur refuse (HTTP 400/422),
    repli sur `json_object` (le prompt décrit alors lui-même le JSON attendu).
    """
    if config.fournisseur == "mock":
        from simulation import reponse_simulee
        return reponse_simulee(nom, messages)

    refus = ""
    for fmt in ("json_schema", "json_object"):
        payload = {"model": config.modele, "messages": messages, "temperature": temperature,
                   "max_tokens": max_tokens, "stream": False}
        if config.effort_raisonnement:
            payload["reasoning_effort"] = config.effort_raisonnement
        payload["response_format"] = (
            {"type": "json_schema", "json_schema": {"name": nom, "schema": schema, "strict": True}}
            if fmt == "json_schema" else {"type": "json_object"})
        debut = time.monotonic()
        try:
            data = _post(config, payload, timeout)
        except RequeteRefusee as e:
            refus = str(e)
            continue
        latence = time.monotonic() - debut
        try:
            choix = data["choices"][0]
            brut = _contenu_texte(choix["message"])
        except (KeyError, IndexError, TypeError):
            raise LLMSortieInvalide("réponse du fournisseur inattendue (pas de « choices »).")
        if choix.get("finish_reason") == "length":
            raise LLMSortieInvalide("réponse tronquée (limite max_tokens atteinte).")
        return Reponse(donnees=extraire_json(brut), brut=brut, usage=data.get("usage") or {},
                       latence_s=round(latence, 2), format_utilise=fmt)
    raise LLMSortieInvalide(f"requête refusée par {config.label} : {refus}")
