# Runbook Operations -- OmniStudio

## Démarrage

### Démarrage normal
```bash
./start.sh
# Ouvrir http://localhost:7870
```

### Démarrage supervisé (restart automatique)
```bash
SUPERVISED=1 ./start.sh
```

### Démarrage manuel (composant par composant)
```bash
# 1. Keycloak
cd ~/Claude/keycloak && docker compose up -d

# 2. OmniVoice
cd OmniVoice && ./venv/bin/python3 main.py

# 3. OmniStudio
cd omnistudio && ./venv/bin/python3 server.py
```

## Mode Production / Développement

OmniStudio a deux modes de fonctionnement contrôlés par `OMNISTUDIO_MINIFY` :

| Mode | Variable | Assets servis | Cache | Console navigateur |
|------|----------|--------------|-------|-------------------|
| **Développement** | `OMNISTUDIO_MINIFY=false` (défaut) | `frontend/out/` (14 modules JS sources) | no-cache sur JS/CSS/HTML | `DÉVELOPPEMENT (sources)` |
| **Production** | `OMNISTUDIO_MINIFY=true` | `frontend/out-dist/` (1 bundle JS minifié) | 7 jours JS/CSS, 1 an DSFR | `PRODUCTION (minifié)` |

### Passer en production

```bash
# 1. Construire les assets minifiés (esbuild, ~20ms)
./scripts/build-frontend.sh

# 2. Démarrer en mode production
OMNISTUDIO_MINIFY=true ./start.sh
```

Ou pour un serveur déjà en cours :

```bash
./stop.sh
OMNISTUDIO_MINIFY=true ./start.sh
```

### Passer en développement

```bash
./stop.sh
./start.sh    # OMNISTUDIO_MINIFY=false par défaut
```

### Basculement rapide

```bash
./scripts/toggle-minify.sh prod    # Affiche la commande à exécuter
./scripts/toggle-minify.sh dev     # Affiche la commande à exécuter
```

### Vérifier le mode actuel

- **Logs serveur** : `OmniStudio DSFR démarre sur le port 7860 — mode PRODUCTION (minifié)`
- **Console navigateur** (F12) : badge `OmniStudio PRODUCTION` ou `DÉVELOPPEMENT`
- **Modale État des services** (pied de page) : première ligne `Mode → Production` ou `Développement`

### Quand reconstruire les assets

Exécuter `./scripts/build-frontend.sh` après toute modification de :
- `omnistudio/frontend/out/js/*.js` (modules JavaScript)
- `omnistudio/frontend/out/css/app.css` (styles custom)
- `omnistudio/frontend/out/index.html` (structure HTML)

Les fichiers DSFR (`frontend/out/dsfr/`) sont copiés tels quels dans `out-dist/`, pas de rebuild nécessaire.

### Différences techniques entre les modes

| Aspect | Développement | Production |
|--------|--------------|------------|
| JS | 14 fichiers séparés (157 Ko) | 1 bundle `app.min.js` (85 Ko) |
| CSS | `app.css` (14 Ko) | `app.min.css` (8 Ko) |
| Source maps | Non | Oui (debug DevTools sans pénalité) |
| Cache navigateur | Désactivé (no-cache) | 7 jours (hash cache busting `?v=`) |
| Cache DSFR | Désactivé | 1 an immutable |
| GZip | Actif | Actif |
| Headers sécurité | Actifs (CSP, HSTS sur HTTPS, COOP) | Actifs |

---

## Arrêt

### Arrêt normal
```bash
./stop.sh
```

### Arrêt du superviseur
```bash
kill $(cat /tmp/omnistudio-supervisor.pid)
```

## Vérification

### Smoke test rapide
```bash
./test-smoke.sh
```

### Health check
```bash
curl http://localhost:7870/api/health
curl http://localhost:8070/health
```

### Monitoring complet
```bash
./scripts/monitor.sh
```

### Tests E2E (avec serveur actif)
```bash
E2E_PASSWORD=<mot_de_passe> python3 -m pytest tests/e2e/ -v
```

## Backup et restauration

### Backup manuel
```bash
./scripts/backup-db.sh
```

### Voir les backups disponibles
```bash
./scripts/restore-db.sh
```

### Restaurer un backup
```bash
./stop.sh
./scripts/restore-db.sh 20260320-0300
./start.sh
```

### Installer le cron backup quotidien
```bash
./scripts/install-cron.sh
```

## Protections sécurité (PRD-029)

### Validation des entrées

Toutes les entrées utilisateur sont validées avant traitement :

- **thread_id** : regex `^[a-zA-Z0-9\-_]{1,64}$` appliquée sur les 3 points d'entrée (`get_thread_id()` + endpoints hybrides `export.py`, `audio.py`). Bloque les path traversal (`../`), les caractères shell (`;`, `|`, `$`), les espaces et l'unicode
- **Noms de fichiers upload** : `os.path.basename()` + `slugify()` — neutralise tout path traversal dans les noms de fichiers uploadés
- **Import ZIP voix** : double protection — filtre `..` dans les noms de dossiers + `resolve().is_relative_to()` pour vérifier que le chemin résolu reste dans `voices_dir`

### Headers sécurité

| Header | Valeur | Protection |
|--------|--------|------------|
| CSP | `default-src 'self'; script-src 'self'; ...` | Anti-XSS, anti-injection |
| HSTS | Conditionnel HTTPS | Force HTTPS |
| COOP | `same-origin` | Anti-clickjacking |
| X-Frame-Options | `DENY` | Anti-iframe |
| Rate limiting | slowapi, 14 endpoints protégés (PRD-031 : +clean, +import) | Anti-brute force, anti-abus GPU |

### Vérifier les protections

```bash
# Thread_id malveillant (doit retourner 400)
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer TOKEN" -H "X-Thread-Id: ../../../etc" http://localhost:7870/api/steps

# Health check (sans auth)
curl http://localhost:7870/api/health
```

---

## Troubleshooting

### OmniStudio ne répond pas (port 7860)
1. Vérifier le processus : `lsof -i :7870`
2. Si absent, relancer : `cd omnistudio && ./venv/bin/python3 server.py`
3. Si présent mais ne répond pas, tuer et relancer :
   `kill $(lsof -t -i :7870); cd omnistudio && ./venv/bin/python3 server.py`
4. Vérifier les logs : `tail -50 omnistudio/logs/omnistudio.log`

### OmniVoice ne répond pas (port 8060)
1. Vérifier le processus : `lsof -i :8070`
2. Si absent, relancer : `cd OmniVoice && ./venv/bin/python3 main.py`
3. Vérifier les logs : `tail -50 OmniVoice/logs/omnivoice.log`
4. Si GPU bloqué, vérifier VRAM :
   `curl http://localhost:8070/generation/status`

### Keycloak ne répond pas (port 8082)
1. Vérifier Docker : `docker ps | grep keycloak`
2. Si absent, relancer : `cd ~/Claude/keycloak && docker compose up -d`
3. Attendre 30s pour le démarrage
4. Vérifier : `curl http://localhost:8082/`

### Génération TTS bloquée
1. Vérifier le statut : `curl http://localhost:8070/generation/status`
2. Si busy depuis > 5 min, possible timeout orphelin
3. Redémarrer OmniVoice : `kill $(lsof -t -i :8070); cd OmniVoice && ./venv/bin/python3 main.py`

Note (PRD-UX-030) : les batches sont découpés en chunks de 20 textes max pour éviter les timeouts sur voix clonées (~15s/texte). Le timeout preview est de 90s (voix clonées avec chargement lazy du modèle).

### Base de données corrompue
1. Arrêter OmniStudio : `./stop.sh`
2. Tester la DB : `sqlite3 omnistudio/data/omnistudio_checkpoint.db "PRAGMA integrity_check;"`
3. Si "ok", problème ailleurs
4. Si erreur, restaurer depuis backup :
   `./scripts/restore-db.sh <date>`
5. Relancer : `./start.sh`

### Disque plein
1. Vérifier : `df -h /`
2. Purge manuelle des exports : `rm -f omnistudio/export/*.zip`
3. Purge manuelle des voix : `rm -rf omnistudio/data/voices/*/`
4. Purge des logs : `rm -f omnistudio/logs/omnistudio.log.* OmniVoice/logs/omnivoice.log.*`

### Mise à jour des dépendances
1. Toujours tester sur un venv temporaire d'abord :
   ```bash
   python3 -m venv /tmp/test-venv
   source /tmp/test-venv/bin/activate
   pip install -r requirements.txt
   # Tester
   ```
2. Si OK, mettre à jour le lock file :
   `cd omnistudio && ./venv/bin/pip freeze > requirements-lock.txt`
3. Commiter et tester les 349 tests

## Keycloak (authentification)

### Pourquoi Docker

Keycloak est un serveur Java (Quarkus) qui nécessite un JDK et de nombreuses dépendances. Docker isole tout ça — pas besoin d'installer Java sur la machine. Le même Keycloak (realm `harmonia`, port 8082) est partagé entre OmniStudio et Harmonia.

### Configuration

- **Emplacement** : `~/Claude/keycloak/` (docker-compose.yml)
- **Port** : 8082
- **Realm** : `harmonia`
- **Client** : `omnistudio`
- **Console admin** : http://localhost:8082/admin

### Créer un utilisateur

Via l'interface admin :
1. Ouvrir http://localhost:8082/admin
2. Se connecter avec les credentials admin
3. Sélectionner le realm **harmonia** (menu déroulant en haut à gauche)
4. Menu **Users** → **Add user**
5. Remplir **Username**, **Enabled** = ON → **Save**
6. Onglet **Credentials** → **Set password** → saisir le mot de passe, **Temporary** = OFF → **Save**

Via la ligne de commande :
```bash
# Se connecter à l'admin CLI (mot de passe dans ~/Claude/keycloak/.env)
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8082 --realm master --user admin --password "$(grep KEYCLOAK_ADMIN_PASSWORD ~/Claude/keycloak/.env | cut -d= -f2)"

# Créer l'utilisateur
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh create users \
  -r harmonia -s username=miweb -s enabled=true -s emailVerified=true

# Définir le mot de passe
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh set-password \
  -r harmonia --username miweb --new-password Miweb1234
```

### Lister les utilisateurs

```bash
docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8082 --realm master --user admin --password "$(grep KEYCLOAK_ADMIN_PASSWORD ~/Claude/keycloak/.env | cut -d= -f2)"

docker exec keycloak-keycloak-1 /opt/keycloak/bin/kcadm.sh get users -r harmonia --fields username,enabled
```

---

## Tailscale Funnel

### Activer
```bash
tailscale funnel --bg --https=7443 http://localhost:7870
```

### Désactiver
```bash
tailscale funnel --https=7443 off
```

### Vérifier
```bash
tailscale funnel status
```

## Architecture rappel

3 processus indépendants :
- Keycloak (Docker, :8082) -- auth JWT
- OmniStudio (Python, :7870) -- front + API + workflow
- OmniVoice (Python, :8070) -- TTS GPU

Base de données :
- `omnistudio/data/omnistudio_checkpoint.db` -- workflows LangGraph (LA base à backuper)
- `omnistudio/data/omnistudio_dsfr_sessions.db` -- sessions utilisateurs

## Décision : Single worker uvicorn

OmniStudio tourne avec 1 worker uvicorn. C'est suffisant car :

1. Toutes les opérations bloquantes (LangGraph, OmniVoice) sont encapsulées dans
   `asyncio.to_thread()` (83 occurrences). Le worker async reste libre.

2. Le goulot d'étranglement est OmniVoice (1 génération GPU à la fois).
   Ajouter des workers OmniStudio ne change rien -- les users attendent le GPU.

3. Les verrous SSE (`_cleaning_locks`, `_generating_locks`, `_exporting_locks`)
   sont des dicts en mémoire process. Avec multi-workers, chaque worker
   a sa copie -- les verrous ne fonctionnent plus.

4. Pour passer en multi-workers, il faudrait migrer les verrous SSE vers
   un backend partagé (SQLite table, Redis, ou file locks). C'est un
   refactoring significatif pour un gain marginal.

Seuil de reconsidération : si > 20 utilisateurs simultanés constatent
des latences > 2s sur les requêtes non-GPU (import, assign, voices).
Mesurer avec : `time curl http://localhost:7870/api/status`
