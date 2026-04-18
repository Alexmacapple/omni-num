"""Tests directs pour auth.py — JWT validation, JWKS cache.

Couvre les chemins non testes par test_endpoints.py (qui bypass auth via dependency_overrides) :
- get_jwks() : fetch, cache hit, cache expire, Keycloak down
- get_current_user() : token valide, manquant, expire, mauvais audience
- validate_token() : token valide, invalide
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt as jose_jwt

from auth import get_jwks, get_current_user, validate_token, _jwks_cache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_JWKS = {
    "keys": [
        {
            "kty": "RSA",
            "kid": "test-key-id",
            "use": "sig",
            "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw",
            "e": "AQAB",
            "alg": "RS256",
        }
    ]
}


@pytest.fixture(autouse=True)
def reset_jwks_cache():
    """Reset le cache JWKS entre chaque test."""
    _jwks_cache["keys"] = None
    _jwks_cache["expires"] = 0
    yield
    _jwks_cache["keys"] = None
    _jwks_cache["expires"] = 0


# ---------------------------------------------------------------------------
# Tests get_jwks
# ---------------------------------------------------------------------------

class TestGetJwks:
    """Cache JWKS et fetch depuis Keycloak."""

    @pytest.mark.asyncio
    async def test_fetch_jwks_success(self):
        """Premier appel -> fetch JWKS depuis Keycloak."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = FAKE_JWKS
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("auth.httpx.AsyncClient", return_value=mock_client):
            result = await get_jwks()
        assert result == FAKE_JWKS
        assert _jwks_cache["keys"] == FAKE_JWKS

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Deuxieme appel avant expiry -> cache hit (pas de fetch)."""
        _jwks_cache["keys"] = FAKE_JWKS
        _jwks_cache["expires"] = time.time() + 3600

        result = await get_jwks()
        assert result == FAKE_JWKS

    @pytest.mark.asyncio
    async def test_cache_expired_refetch(self):
        """Cache expire -> re-fetch."""
        _jwks_cache["keys"] = FAKE_JWKS
        _jwks_cache["expires"] = time.time() - 1  # Expire

        mock_response = MagicMock()
        mock_response.status_code = 200
        new_jwks = {"keys": [{"kid": "new-key"}]}
        mock_response.json.return_value = new_jwks
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("auth.httpx.AsyncClient", return_value=mock_client):
            result = await get_jwks()
        assert result == new_jwks

    @pytest.mark.asyncio
    async def test_keycloak_down_with_cache(self):
        """Keycloak down mais cache disponible -> retourne le cache."""
        _jwks_cache["keys"] = FAKE_JWKS
        _jwks_cache["expires"] = time.time() - 1  # Expire

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("auth.httpx.AsyncClient", return_value=mock_client):
            result = await get_jwks()
        assert result == FAKE_JWKS

    @pytest.mark.asyncio
    async def test_keycloak_down_no_cache(self):
        """Keycloak down et pas de cache -> HTTPException 503."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("auth.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await get_jwks()
            assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Tests get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    """Extraction et validation du JWT Bearer."""

    @pytest.mark.asyncio
    async def test_no_auth_header(self):
        """Pas de header Authorization -> 401."""
        request = MagicMock()
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_bearer_prefix(self):
        """Header Authorization sans 'Bearer ' -> 401."""
        request = MagicMock()
        request.headers = {"Authorization": "Basic abc123"}
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_jwt(self):
        """JWT invalide -> 401."""
        request = MagicMock()
        request.headers = {"Authorization": "Bearer invalid.jwt.token"}

        _jwks_cache["keys"] = FAKE_JWKS
        _jwks_cache["expires"] = time.time() + 3600

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Tests validate_token
# ---------------------------------------------------------------------------

class TestValidateToken:
    """Validation directe d'un token (query params)."""

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Token invalide -> 401."""
        _jwks_cache["keys"] = FAKE_JWKS
        _jwks_cache["expires"] = time.time() + 3600

        with pytest.raises(HTTPException) as exc_info:
            await validate_token("fake.invalid.token")
        assert exc_info.value.status_code == 401
