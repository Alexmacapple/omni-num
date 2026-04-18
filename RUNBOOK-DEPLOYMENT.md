# RUNBOOK-DEPLOYMENT — omni-num

Procédures de déploiement et décisions d'architecture validées en **Phase 0bis** (architecture check).

---

## Architecture réseau

| Composant | Port local | URL publique | Notes |
|-----------|-----------|--------------|-------|
| Keycloak | 8082 | interne | Auth JWT, realm `harmonia`, client `omnistudio` |
| OmniVoice | 8070 | interne | API TTS k2-fsa, chargé au premier boot |
| omnistudio | 7870 | `https://mac-studio-alex.tail0fc408.ts.net/omni/` | Front DSFR + API FastAPI |

---

## Décision assets — Option A (`<base href="/omni/">`)

Stratégie validée empiriquement en Phase 0bis. **Règles absolues** :

1. **PAS de `root_path="/omni"` dans FastAPI**
   Tailscale Funnel strippe le préfixe `/omni/` avant de forwarder au backend. Si FastAPI est configuré avec `root_path`, les mounts `StaticFiles` ne répondent QUE sous le prefix, donc 404 via Funnel. Confirmé empiriquement.

2. **`<base href="/omni/">` dans `<head>` de `index.html`**
   Résout tous les chemins relatifs (`css/app.css`, `js/app.js`, `dsfr/dsfr.min.css`) vers `/omni/...`, que l'URL d'entrée soit `http://localhost:7870/` ou `https://mac-studio-alex.tail0fc408.ts.net/omni/`.

3. **Chemins HTML : relatifs, jamais absolus**
   Retirer le `/` initial des 9 `href="/...` et `src="/...` identifiés par `scripts/verify-assets-prefix.sh`.

4. **Chemins JS `fetch()` : relatifs**
   `<base href>` ne s'applique pas aux `fetch()`. Les 5 `fetch('/api/...')` identifiés (auth.js × 3, app.js × 2) doivent devenir `fetch('api/...')`.

5. **Audit avant build**
   `./scripts/verify-assets-prefix.sh` audite `frontend/out/` et `frontend/out-dist/` avant chaque build prod. Zéro `/` initial dans les chemins d'assets.

---

## Démarrage

### Démarrage complet

```bash
./start.sh
```

Lance Keycloak (Docker, partagé avec voice-num), OmniVoice (port 8070), seed des voix système si nécessaire, puis omnistudio (port 7870).

### Démarrage individuel (dev)

```bash
# Keycloak (partagé)
cd ~/Claude/keycloak && docker compose up -d

# OmniVoice
cd omni-num/OmniVoice && ./venv/bin/python3 main.py

# omnistudio
cd omni-num/omnistudio && ./venv/bin/python3 server.py
```

### Stub Phase 0bis (debug architecture)

```bash
cd omni-num/omnistudio && python3 stub_server.py
```

Minimal, sans OmniVoice ni Keycloak. Utile pour re-valider l'architecture si changements infra.

---

## Tailscale Funnel

### Activer `/omni` sur port 443

```bash
tailscale funnel --bg --set-path=/omni http://localhost:7870
```

**Ne PAS utiliser `--https=443`** : le Funnel 443 est déjà actif pour voxstudio et autres services. `--bg` ajoute un path à la config existante.

### État actuel des paths sur 443

```bash
tailscale funnel status
```

Paths actifs sur `https://mac-studio-alex.tail0fc408.ts.net` (443) :

```
/              → voxstudio (localhost:7860)
/omni          → omnistudio (localhost:7870)
/harmonia      → localhost:8081
/anon          → localhost:8091
/projets       → localhost:8093
/pseudonymus   → localhost:8090
/swing-digital → localhost:8092
```

### Retirer `/omni` si besoin

```bash
# Impossible de retirer un seul path sans toucher les autres.
# Solution : reset complet puis re-déclarer tous les paths via script.
tailscale funnel reset
# Puis re-lancer le start.sh de voxstudio qui re-déclare ses paths
# + tailscale funnel --bg --set-path=/omni http://localhost:7870
```

---

## Keycloak

### Credentials admin

Mot de passe admin dans `~/Claude/keycloak/.env` (variable `KEYCLOAK_ADMIN_PASSWORD`). Username : `admin`.

### Console admin

```
http://localhost:8082/admin/
```

### Créer/mettre à jour le client omnistudio

```bash
./scripts/setup-keycloak.sh
```

Script idempotent. Crée ou met à jour le client `omnistudio` dans le realm `harmonia` avec :

- `publicClient: true`
- `directAccessGrantsEnabled: true` (ROPC — même flow que voxstudio)
- `standardFlowEnabled: false`
- `redirectUris`: `http://localhost:7870/*`, `https://mac-studio-alex.tail0fc408.ts.net/omni/*`
- `webOrigins`: `http://localhost:7870`, `https://mac-studio-alex.tail0fc408.ts.net`

### Tester le flow ROPC

```bash
curl -X POST http://localhost:8082/realms/harmonia/protocol/openid-connect/token \
  -d "client_id=omnistudio" \
  -d "username=alex" \
  -d "password=<mot_de_passe_alex>" \
  -d "grant_type=password"
```

Retourne un JSON avec `access_token` et `refresh_token` si credentials valides.

---

## Piège Docker exec resource unavailable

Si `docker exec keycloak-keycloak-1 ...` échoue avec `resource temporarily unavailable` :

- Symptôme : container marqué `unhealthy` depuis plusieurs jours, limite PIDs atteinte
- Fix : `cd ~/Claude/keycloak && docker compose restart` (30 s de downtime)
- Ne pas utiliser `docker compose down && up` sans raison (efface potentiellement des sessions actives)

---

## Troubleshooting

### 404 sur les assets via Funnel

1. Vérifier que le stub / serveur n'a PAS `root_path="/omni"` dans FastAPI
2. Vérifier que `<base href="/omni/">` est dans `<head>` de `index.html`
3. Lancer `./scripts/verify-assets-prefix.sh` pour détecter des chemins absolus oubliés

### Login Keycloak en boucle

1. Vérifier que le client `omnistudio` existe : console admin Keycloak → realm harmonia → Clients
2. Vérifier les `redirectUris` : doivent contenir exactement `http://localhost:7870/*` ET `https://mac-studio-alex.tail0fc408.ts.net/omni/*`
3. Vérifier JWT `aud=omnistudio` côté back via `auth.py`

### Port 7870 occupé

```bash
lsof -ti :7870   # identifier le PID
kill <PID>       # arrêt propre
```

Si `stop.sh` existe :

```bash
./stop.sh
```

### Mémoire cumulée élevée (critère de validation #29)

```bash
./scripts/monitor.sh   # affiche memory_pressure macOS
```

Seuil critique : `memory_pressure < 0.5`. Si dépassé, arrêter voxstudio (si actif en parallèle) avant de relancer omnistudio.

---

## Validation Phase 0bis (5 critères de sortie)

- [x] Stub FastAPI répond sur `http://localhost:7870/` ET `https://mac-studio-alex.tail0fc408.ts.net/omni/`
- [x] Assets statiques (CSS, JS) servis correctement sous `/omni/` via Funnel
- [x] `scripts/verify-assets-prefix.sh` produit un inventaire des chemins à corriger (14 trouvés dans voxstudio/)
- [x] Décision assets documentée ici (Option A : `<base href="/omni/">` + pas de `root_path`)
- [x] Client Keycloak `omnistudio` créé (UUID `7c0cfb9b-3c88-4ec0-839f-7e76bac27ad7`) via `scripts/setup-keycloak.sh`

**Phase 0bis validée.** Passage à Phase 1 (documentation) autorisé.
