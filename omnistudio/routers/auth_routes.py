"""Routeur Auth — proxy vers Keycloak (PRD-010, Phase 1).

Endpoints :
- POST /api/auth/login
- POST /api/auth/token/refresh
- POST /api/auth/logout
"""
import httpx
from fastapi import APIRouter, Request

from config import KEYCLOAK_CLIENT_ID, KEYCLOAK_REALM, KEYCLOAK_URL
from dependencies import api_error, api_response, limiter, logger

router = APIRouter()


@router.post("/api/auth/login")
@limiter.limit("5/minute")
async def auth_login(request: Request):
    """Login via Keycloak (Resource Owner Password)."""
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")

    token_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "password",
                    "client_id": KEYCLOAK_CLIENT_ID,
                    "username": username,
                    "password": password,
                },
                timeout=10.0,
            )
        except httpx.ConnectError:
            return api_error("AUTH_REQUIRED", "Keycloak indisponible", 503)

    if response.status_code != 200:
        return api_error("AUTH_REQUIRED", "Identifiants invalides", 401)

    try:
        tokens = response.json()
    except (ValueError, KeyError):
        return api_error("AUTH_REQUIRED", "Reponse Keycloak invalide (non-JSON)", 502)
    return api_response({
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_in": tokens.get("expires_in", 300),
    })


@router.post("/api/auth/token/refresh")
@limiter.limit("10/minute")
async def auth_refresh(request: Request):
    """Rafraichir le token d'acces."""
    body = await request.json()
    refresh_token = body.get("refresh_token", "")

    token_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": KEYCLOAK_CLIENT_ID,
                    "refresh_token": refresh_token,
                },
                timeout=10.0,
            )
        except httpx.ConnectError:
            return api_error("AUTH_REQUIRED", "Keycloak indisponible", 503)

    if response.status_code != 200:
        return api_error("AUTH_REQUIRED", "Refresh token invalide", 401)

    try:
        tokens = response.json()
    except (ValueError, KeyError):
        return api_error("AUTH_REQUIRED", "Reponse Keycloak invalide (non-JSON)", 502)
    return api_response({
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", refresh_token),
        "expires_in": tokens.get("expires_in", 300),
    })


@router.post("/api/auth/logout")
async def auth_logout(request: Request):
    """Deconnexion (revocation du refresh token)."""
    body = await request.json()
    refresh_token = body.get("refresh_token", "")

    logout_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                logout_url,
                data={
                    "client_id": KEYCLOAK_CLIENT_ID,
                    "refresh_token": refresh_token,
                },
                timeout=10.0,
            )
        except httpx.ConnectError:
            logger.warning("Keycloak indisponible pour logout, best-effort OK")

    return api_response({"message": "Deconnecte"})
