"""Validation JWT Keycloak pour OmniStudio DSFR."""
import time
import logging
import httpx
from jose import jwt, JWTError
from fastapi import Request, HTTPException

from config import KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID

logger = logging.getLogger("omnistudio")

# Cache JWKS (TTL 1h)
_jwks_cache = {"keys": None, "expires": 0}


async def get_jwks() -> dict:
    """Recupere les cles publiques Keycloak (cache 1h)."""
    now = time.time()
    if _jwks_cache["keys"] and now < _jwks_cache["expires"]:
        return _jwks_cache["keys"]

    jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            jwks = response.json()
            _jwks_cache["keys"] = jwks
            _jwks_cache["expires"] = now + 3600
            return jwks
    except Exception as e:
        logger.error("Erreur recuperation JWKS : %s", e)
        if _jwks_cache["keys"]:
            return _jwks_cache["keys"]
        raise HTTPException(status_code=503, detail="Keycloak indisponible")


async def get_current_user(request: Request) -> dict:
    """Dependance FastAPI : extrait et valide le JWT Bearer."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Token manquant ou invalide"},
        )

    token = auth_header[7:]
    jwks = await get_jwks()

    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=KEYCLOAK_CLIENT_ID,
            issuer=f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}",
            options={"verify_exp": True},
        )
        return {
            "user_id": payload["sub"],
            "username": payload.get("preferred_username", ""),
        }
    except JWTError as e:
        logger.warning("JWT invalide : %s", e)
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Token invalide ou expire"},
        )


async def validate_token(token: str) -> dict:
    """Valide un JWT brut (sans passer par Request). Pour les query params."""
    jwks = await get_jwks()
    try:
        payload = jwt.decode(
            token, jwks, algorithms=["RS256"],
            audience=KEYCLOAK_CLIENT_ID,
            issuer=f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}",
            options={"verify_exp": True},
        )
        return {
            "user_id": payload["sub"],
            "username": payload.get("preferred_username", ""),
        }
    except JWTError as e:
        logger.warning("JWT invalide: %s", e)
        raise HTTPException(status_code=401, detail="Token invalide")
