"""POC « Parcours ZRM » (Le Vinatier) : simulation du parcours aidant·e avec les activités IA.

Lancement :  cd poc_activites_ia  puis  streamlit run app.py
Clé API    :  variable d'environnement OLLAMA_API_KEY (test) ou MISTRAL_API_KEY (production),
              ou .streamlit/secrets.toml / « Secrets » de Streamlit Cloud (voir le README).

Ce fichier ne fait que la configuration ; le parcours est dans parcours.py, les textes fixes dans
contenus/textes.toml, les appels à l'IA dans activites.py.
"""
from __future__ import annotations

import os

import streamlit as st

st.set_page_config(page_title="Parcours ZRM - POC activités IA", layout="wide")

import llm  # noqa: E402  (après set_page_config, qui doit être la première commande Streamlit)
import parcours  # noqa: E402


def lire(nom: str) -> str:
    """Variable d'environnement d'abord, puis secrets Streamlit (s'il y en a)."""
    if os.environ.get(nom):
        return os.environ[nom]
    try:
        return str(st.secrets.get(nom, "") or "")
    except Exception:   # pas de fichier secrets.toml : normal
        return ""


try:
    CONFIG = llm.resoudre_config(lire)
except llm.ConfigurationError as e:
    st.title("Parcours ZRM - POC activités IA")
    st.error(str(e))
    st.markdown(
        "Lancez l'application avec la clé dans l'environnement, par exemple (PowerShell) :\n\n"
        "```\n$env:OLLAMA_API_KEY = \"votre_clé\"\nstreamlit run app.py\n```\n"
        "ou sans IA, pour essayer l'interface : `$env:LLM_PROVIDER = \"mock\"`.")
    st.stop()

parcours.executer(CONFIG)
