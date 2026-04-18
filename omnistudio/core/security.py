"""Gestion cle API — version simplifiee (PRD-005).

La cle API est unique, cote serveur, via variable d'environnement.
Le parametre thread_id est conserve pour compatibilite de signature
avec les subgraphs (clean_loop, design_loop) qui appellent get_api_key(thread_id).
"""
import os


def get_api_key(thread_id: str = "") -> str:
    """Retourne la cle API serveur (variable d'environnement)."""
    return os.getenv("OPENAI_API_KEY", "sk-no-key-needed")


def set_api_key(thread_id: str, api_key: str):
    """No-op. Conserve pour compatibilite import."""
    pass


def clear_api_keys():
    """No-op. Conserve pour compatibilite import."""
    pass
