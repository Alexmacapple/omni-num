#!/usr/bin/env bash
# setup-e2e-user.sh — prépare le compte Keycloak E2E sans secret en dur.

set -euo pipefail

KC_CONTAINER="${KC_CONTAINER:-keycloak-keycloak-1}"
KC_REALM="${KC_REALM:-harmonia}"
KC_CLIENT_ID="${KC_CLIENT_ID:-omnistudio}"
KC_SERVER="${KC_SERVER:-http://localhost:8082}"
KC_ENV_FILE="${KC_ENV_FILE:-${HOME}/Claude/keycloak/.env}"
E2E_USERNAME="${E2E_USERNAME:-omni-e2e}"

fail() { echo "ERROR: $*" >&2; exit 1; }
ok() { echo "  [OK] $*"; }

if [ -z "${E2E_PASSWORD:-}" ]; then
    fail "E2E_PASSWORD doit être défini dans l'environnement (aucun secret en dur)."
fi

if [ "${#E2E_PASSWORD}" -lt 8 ] || ! [[ "$E2E_PASSWORD" =~ [A-Z] ]] || ! [[ "$E2E_PASSWORD" =~ [0-9] ]]; then
    fail "E2E_PASSWORD doit respecter la policy Keycloak: 8 caractères minimum, 1 majuscule, 1 chiffre."
fi

if [ -z "${KEYCLOAK_ADMIN_PASSWORD:-}" ]; then
    [ -f "$KC_ENV_FILE" ] || fail "$KC_ENV_FILE introuvable et KEYCLOAK_ADMIN_PASSWORD non défini"
    KEYCLOAK_ADMIN_PASSWORD=$(grep "^KEYCLOAK_ADMIN_PASSWORD=" "$KC_ENV_FILE" | cut -d= -f2-)
fi
[ -n "$KEYCLOAK_ADMIN_PASSWORD" ] || fail "KEYCLOAK_ADMIN_PASSWORD absent"

command -v docker >/dev/null 2>&1 || fail "docker manquant"
command -v python3 >/dev/null 2>&1 || fail "python3 manquant"
docker ps --format '{{.Names}}' | grep -qx "$KC_CONTAINER" || fail "container Keycloak non actif: $KC_CONTAINER"

echo "=== Préparation compte E2E Keycloak ==="
echo "Realm : $KC_REALM"
echo "Client: $KC_CLIENT_ID"
echo "User  : $E2E_USERNAME"

docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh config credentials \
    --server "$KC_SERVER" \
    --realm master \
    --user admin \
    --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null
ok "login admin kcadm"

docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh get "realms/$KC_REALM" --fields realm,enabled >/dev/null
ok "realm $KC_REALM accessible"

CLIENT_JSON=$(docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh get clients \
    -r "$KC_REALM" \
    -q "clientId=$KC_CLIENT_ID" \
    --fields id,clientId,directAccessGrantsEnabled 2>/dev/null || echo "[]")

CLIENT_UUID=$(CLIENT_JSON="$CLIENT_JSON" python3 - <<'PY'
import json
import os
data = json.loads(os.environ["CLIENT_JSON"])
if not data:
    raise SystemExit(1)
print(data[0]["id"])
PY
) || fail "client $KC_CLIENT_ID introuvable dans realm $KC_REALM"
ok "client $KC_CLIENT_ID trouvé"

docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh update "clients/$CLIENT_UUID" \
    -r "$KC_REALM" \
    -s 'publicClient=true' \
    -s 'standardFlowEnabled=false' \
    -s 'directAccessGrantsEnabled=true' \
    -s 'enabled=true' >/dev/null
ok "client compatible ROPC"

USER_JSON=$(docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh get users \
    -r "$KC_REALM" \
    -q "username=$E2E_USERNAME" \
    --fields id,username 2>/dev/null || echo "[]")

USER_COUNT=$(USER_JSON="$USER_JSON" python3 - <<'PY'
import json
import os
print(len(json.loads(os.environ["USER_JSON"])))
PY
)

if [ "$USER_COUNT" -gt 0 ]; then
    USER_ID=$(USER_JSON="$USER_JSON" python3 - <<'PY'
import json
import os
print(json.loads(os.environ["USER_JSON"])[0]["id"])
PY
)
    docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh update "users/$USER_ID" \
        -r "$KC_REALM" \
        -s enabled=true \
        -s emailVerified=true >/dev/null
    ok "utilisateur existant réactivé"
else
    docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh create users \
        -r "$KC_REALM" \
        -s "username=$E2E_USERNAME" \
        -s enabled=true \
        -s emailVerified=true >/dev/null
    ok "utilisateur créé"
fi

docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh set-password \
    -r "$KC_REALM" \
    --username "$E2E_USERNAME" \
    --new-password "$E2E_PASSWORD" >/dev/null
ok "mot de passe E2E défini"

MAPPERS_JSON=$(docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh get "clients/$CLIENT_UUID/protocol-mappers/models" \
    -r "$KC_REALM" 2>/dev/null || echo "[]")
HAS_MAPPER=$(MAPPERS_JSON="$MAPPERS_JSON" KC_CLIENT_ID="$KC_CLIENT_ID" python3 - <<'PY'
import json
import os
data = json.loads(os.environ["MAPPERS_JSON"])
client_id = os.environ["KC_CLIENT_ID"]
for mapper in data:
    cfg = mapper.get("config") or {}
    if (
        mapper.get("protocolMapper") == "oidc-audience-mapper"
        and cfg.get("included.client.audience") == client_id
        and cfg.get("access.token.claim") == "true"
    ):
        print("1")
        break
else:
    print("0")
PY
)

if [ "$HAS_MAPPER" = "0" ]; then
    docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh create "clients/$CLIENT_UUID/protocol-mappers/models" \
        -r "$KC_REALM" \
        -s "name=$KC_CLIENT_ID-audience" \
        -s protocolMapper="oidc-audience-mapper" \
        -s protocol="openid-connect" \
        -s "config={\"included.client.audience\":\"$KC_CLIENT_ID\",\"id.token.claim\":\"false\",\"access.token.claim\":\"true\"}" >/dev/null
    ok "mapper audience $KC_CLIENT_ID créé"
else
    ok "mapper audience $KC_CLIENT_ID présent"
fi

KC_SERVER="$KC_SERVER" KC_REALM="$KC_REALM" KC_CLIENT_ID="$KC_CLIENT_ID" E2E_USERNAME="$E2E_USERNAME" E2E_PASSWORD="$E2E_PASSWORD" python3 - <<'PY'
import base64
import json
import os
import urllib.parse
import urllib.request

data = urllib.parse.urlencode({
    "grant_type": "password",
    "client_id": os.environ["KC_CLIENT_ID"],
    "username": os.environ["E2E_USERNAME"],
    "password": os.environ["E2E_PASSWORD"],
}).encode()
url = f"{os.environ['KC_SERVER']}/realms/{os.environ['KC_REALM']}/protocol/openid-connect/token"
req = urllib.request.Request(url, data=data)
with urllib.request.urlopen(req, timeout=10) as response:
    token = json.loads(response.read())["access_token"]
payload = token.split(".")[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
aud = claims.get("aud", [])
if isinstance(aud, str):
    aud = [aud]
if os.environ["KC_CLIENT_ID"] not in aud:
    raise SystemExit(f"audience JWT invalide: {aud!r}")
print("  [OK] token E2E obtenu avec audience", aud)
PY

echo ""
echo "Compte E2E prêt."
echo "Commande de test :"
echo "  E2E_USERNAME=$E2E_USERNAME E2E_PASSWORD=<secret> python3 -m pytest tests/e2e/ -v --timeout=120"
