#!/usr/bin/env bash
# setup-keycloak.sh — Crée le client omnistudio dans Keycloak (realm harmonia).
#
# Phase 0bis étape 4 : client idempotent (vérifie avant créer, update si existe).
# Calque la config de voxstudio (ROPC : publicClient + directAccessGrants).
#
# Prérequis :
# - Container Keycloak (keycloak-keycloak-1) en cours d'exécution
# - ~/Claude/keycloak/.env contient KEYCLOAK_ADMIN_PASSWORD
#
# Usage :
#   ./scripts/setup-keycloak.sh

set -e

KC_CONTAINER="keycloak-keycloak-1"
KC_REALM="harmonia"
KC_CLIENT_ID="omnistudio"
KC_SERVER="http://localhost:8082"

#!/usr/bin/env bash
# setup-keycloak.sh — Crée le client omnistudio dans Keycloak (realm harmonia).
#
# Phase 0bis étape 4 : client idempotent (vérifie avant créer, update si existe).
# Calque la config de voxstudio (ROPC : publicClient + directAccessGrants).
#
# Prérequis :
# - Container Keycloak (keycloak-keycloak-1) en cours d'exécution
# - ~/Claude/keycloak/.env contient KEYCLOAK_ADMIN_PASSWORD
#
# Usage :
#   ./scripts/setup-keycloak.sh

set -euo pipefail

# Charger le password admin depuis le .env de Keycloak
KC_ENV_FILE="${HOME}/Claude/keycloak/.env"
if [ ! -f "$KC_ENV_FILE" ]; then
    echo "ERROR: $KC_ENV_FILE introuvable"
    exit 1
fi
KC_ADMIN_PASSWORD=$(grep "^KEYCLOAK_ADMIN_PASSWORD=" "$KC_ENV_FILE" | cut -d= -f2-)
if [ -z "$KC_ADMIN_PASSWORD" ]; then
    echo "ERROR: KEYCLOAK_ADMIN_PASSWORD absent de $KC_ENV_FILE"
    exit 1
fi

echo "=== Login kcadm ==="
docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh config credentials \
    --server "$KC_SERVER" \
    --realm master \
    --user admin \
    --password "$KC_ADMIN_PASSWORD" > /dev/null
echo "OK"

echo ""
echo "=== Vérification realm $KC_REALM ==="
docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh get "realms/$KC_REALM" --fields realm,enabled > /dev/null
echo "OK (realm existe)"

echo ""
echo "=== Vérification client $KC_CLIENT_ID ==="
EXISTING=$(docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh get clients \
    -r "$KC_REALM" \
    -q "clientId=$KC_CLIENT_ID" \
    --fields id,clientId 2>/dev/null || echo "[]")

CLIENT_EXISTS=$(echo "$EXISTING" | python3 -c "import sys, json; d = json.load(sys.stdin); print(len(d))" 2>/dev/null || echo 0)

if [ "$CLIENT_EXISTS" -gt 0 ]; then
    CLIENT_UUID=$(echo "$EXISTING" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")
    echo "Client déjà présent (UUID=$CLIENT_UUID) — mise à jour de la config"

    # Update redirectUris et webOrigins (idempotent)
    docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh update "clients/$CLIENT_UUID" \
        -r "$KC_REALM" \
        -s 'redirectUris=["http://localhost:7870/*","https://mac-studio-alex.tail0fc408.ts.net/omni/*"]' \
        -s 'webOrigins=["http://localhost:7870","https://mac-studio-alex.tail0fc408.ts.net"]' \
        -s 'publicClient=true' \
        -s 'standardFlowEnabled=false' \
        -s 'directAccessGrantsEnabled=true' \
        -s 'protocol=openid-connect' \
        -s 'enabled=true'
    echo "Client $KC_CLIENT_ID mis à jour"
else
    echo "Client absent — création"
    docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh create clients \
        -r "$KC_REALM" \
        -s "clientId=$KC_CLIENT_ID" \
        -s 'publicClient=true' \
        -s 'standardFlowEnabled=false' \
        -s 'directAccessGrantsEnabled=true' \
        -s 'protocol=openid-connect' \
        -s 'enabled=true' \
        -s 'redirectUris=["http://localhost:7870/*","https://mac-studio-alex.tail0fc408.ts.net/omni/*"]' \
        -s 'webOrigins=["http://localhost:7870","https://mac-studio-alex.tail0fc408.ts.net"]'
    echo "Client $KC_CLIENT_ID créé"
fi

echo ""
echo "=== Vérification finale ==="
docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh get clients \
    -r "$KC_REALM" \
    -q "clientId=$KC_CLIENT_ID" 2>/dev/null | python3 -c "
import sys, json
c = json.load(sys.stdin)[0]
for k in ['clientId', 'enabled', 'publicClient', 'standardFlowEnabled', 'directAccessGrantsEnabled', 'redirectUris', 'webOrigins']:
    print(f'  {k}: {c.get(k)}')
"

echo ""
echo "Setup Keycloak terminé."
