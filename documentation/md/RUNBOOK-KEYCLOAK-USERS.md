# Gestion des comptes utilisateurs — OmniStudio / Keycloak

## Contexte

Toutes les applications hébergées (OmniStudio, VoxStudio, Harmonia) partagent le même realm Keycloak `harmonia`, accessible sur `http://localhost:8082`. Les comptes sont créés une fois et donnent accès à tous les clients du realm.

---

## Credentials administrateur

Stockés dans `CLAUDE.local.md` (gitignored). Ne pas les mettre dans un fichier versionné.

Connexion admin via le container Docker :

```bash
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8082 \
  --realm master \
  --user admin \
  --password '<voir CLAUDE.local.md>'
```

---

## Créer un nouveau compte

### 1. Obtenir un token admin

```bash
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8082 --realm master \
  --user admin --password '<mot de passe admin>'
```

### 2. Créer l'utilisateur

```bash
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh create users \
  -r harmonia \
  -s username=<nom> \
  -s enabled=true \
  -s emailVerified=true
```

### 3. Définir le mot de passe

La policy du realm exige : **8 caractères minimum, 1 majuscule, 1 chiffre**.

```bash
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh set-password \
  -r harmonia \
  --username <nom> \
  --new-password '<Motdepasse1>'
```

Si le mot de passe souhaité ne respecte pas la policy (ex. : compte de démo avec mdp court), suspendre temporairement la policy, définir le mdp, puis restaurer :

```bash
# Suspendre
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh update realms/harmonia \
  -s 'passwordPolicy=""'

# Définir le mdp
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh set-password \
  -r harmonia --username <nom> --new-password '<mdp>'

# Restaurer
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh update realms/harmonia \
  -s 'passwordPolicy="length(8) and digits(1) and upperCase(1)"'
```

---

## Point critique : mapper d'audience JWT

### Problème

Sans mapper explicite, le token Keycloak peut inclure `aud: ["account"]`. OmniStudio valide le JWT avec `audience="omnistudio"` — si `omnistudio` n'est pas dans `aud`, toutes les requêtes retournent **401 Invalid audience**.

Le comportement dépend du token :
- Token **sans** `aud` (cas de certains utilisateurs anciens) → jose passe sans vérifier
- Token **avec** `aud: ["account"]` (nouveaux utilisateurs) → jose échoue → 401

### Solution permanente (déjà appliquée)

Un Audience mapper est configuré sur les clients `omnistudio` et `voxstudio`. Il ajoute automatiquement le `client_id` dans le claim `aud` de chaque access token, pour tous les utilisateurs sans exception.

Vérification :

```bash
# Décoder le token d'un utilisateur pour confirmer que aud contient "omnistudio"
python3 -c "
import urllib.request, urllib.parse, json, base64
data = urllib.parse.urlencode({
    'grant_type': 'password',
    'client_id': 'omnistudio',
    'username': '<nom>',
    'password': '<mdp>'
}).encode()
req = urllib.request.Request(
    'http://localhost:8082/realms/harmonia/protocol/openid-connect/token', data=data)
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())
at = d['access_token']
payload = at.split('.')[1] + '=='
claims = json.loads(base64.urlsafe_b64decode(payload))
print('aud:', claims.get('aud', 'ABSENT'))
"
```

Résultat attendu : `aud: ['omnistudio', 'account']`

Si le mapper est absent (après une réinstallation Keycloak par exemple), le recréer :

```bash
CLIENT_ID=$(docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh get clients \
  -r harmonia -q clientId=omnistudio \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh create \
  clients/$CLIENT_ID/protocol-mappers/models \
  -r harmonia \
  -s name="omnistudio-audience" \
  -s protocolMapper="oidc-audience-mapper" \
  -s protocol="openid-connect" \
  -s 'config={"included.client.audience":"omnistudio","id.token.claim":"false","access.token.claim":"true"}'
```

Répéter avec `clientId=voxstudio` pour VoxStudio.

---

## Rate limiting

Le endpoint `/api/auth/login` est limité à **5 requêtes/minute** par IP. Si un utilisateur est bloqué en 429 après des tentatives répétées (boucle de retry due à un 401), le compteur se réinitialise après 1 minute ou au redémarrage du serveur OmniStudio.

---

## Comptes existants

| Username | Accès | Notes |
|----------|-------|-------|
| alex     | Admin OmniStudio + VoxStudio | Mot de passe dans `CLAUDE.local.md` |
| miweb    | Utilisateur standard | Mdp court (policy suspendue lors de la création) |
| vlad, agnes, loic | Utilisateurs standard | Voir realm-export.json |

---

## Vérifications utiles

```bash
# Lister tous les utilisateurs du realm harmonia
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh get users -r harmonia \
  | python3 -c "import sys,json; [print(u['username'], '|', u['id']) for u in json.load(sys.stdin)]"

# Vérifier qu'un utilisateur est activé
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh get users \
  -r harmonia -q username=<nom>

# Réinitialiser un mot de passe oublié
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh set-password \
  -r harmonia --username <nom> --new-password '<NouveauMdp1>'
```
