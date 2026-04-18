"""Registre central des routeurs FastAPI (PRD-010, decision D3).

Chaque routeur est importe et enregistre ici. Si un import echoue,
l'application crashe au demarrage (pas de 404 silencieux).
"""
from fastapi import FastAPI


def register_all(app: FastAPI):
    """Enregistre tous les routeurs API dans l'application.

    Appele une seule fois dans server.py, AVANT le montage des fichiers statiques.
    Les routeurs seront ajoutes au fur et a mesure des phases (1-10).
    """
    from .auth_routes import router as auth_routes_router
    from .sessions import router as sessions_router
    from .status import router as status_router
    from .audio import router as audio_router
    from .import_steps import router as import_steps_router
    from .clean import router as clean_router
    from .voices import router as voices_router
    from .assign import router as assign_router
    from .generate import router as generate_router
    from .export import router as export_router

    _routers = [
        (auth_routes_router, ["Authentification"]),
        (sessions_router, ["Sessions"]),
        (status_router, ["Statut"]),
        (audio_router, ["Audio"]),
        (import_steps_router, ["Import"]),
        (clean_router, ["Préparation"]),
        (voices_router, ["Voix"]),
        (assign_router, ["Assignation"]),
        (generate_router, ["Génération"]),
        (export_router, ["Export"]),
    ]

    for router, tags in _routers:
        app.include_router(router, tags=tags)
