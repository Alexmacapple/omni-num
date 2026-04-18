# Architecture OmniStudio

Guide pédagogique de l'architecture technique de OmniStudio. Ce document explique comment l'application fonctionne, couche par couche, avec des exemples concrets.

**Public** : développeur qui rejoint le projet ou qui veut comprendre les choix techniques.
**Prérequis** : notions de base en Python, JavaScript, HTTP, SQL.

> **Origine** : ce document est adapté de `voice-num/documentation/md/ARCHITECTURE.md` (voxstudio) le 2026-04-18 dans le cadre du fork omnistudio. Pour les écarts spécifiques à OmniVoice (tags émotionnels, multi-voix par étape, sous-titres SRT, accents/dialectes, paramètres avancés), voir :
>
> - [TAGS-SRT-SUBTITLES.md](./TAGS-SRT-SUBTITLES.md) — enrichissements OmniVoice
> - [ARCHITECTURE-LANGGRAPH-OMNI.md](./ARCHITECTURE-LANGGRAPH-OMNI.md) — extension du graphe pour multi-voix
> - [`PRD-MIGRATION-001-FORK-OMNISTUDIO.md`](../../PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md) — décisions v1.5
> - [`RUNBOOK-DEPLOYMENT.md`](../../RUNBOOK-DEPLOYMENT.md) — stratégie `<base href>` et Funnel path-based

---

## Vue d'ensemble

OmniStudio est un studio de production vocale composé de 3 processus indépendants :

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│  Keycloak   │     │   OmniStudio     │     │   OmniVoice   │
│  (Docker)   │     │   (FastAPI)     │     │  (Python)   │
│  :8082      │◄────│   :7870         │────►│  :8070      │
│             │     │                 │     │             │
│  Auth JWT   │     │  Front + API    │     │  TTS GPU    │
└─────────────┘     └─────────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │   SQLite    │
                    │ checkpoint  │
                    └─────────────┘
```

**Keycloak** gère l'authentification. L'utilisateur se connecte, Keycloak délivre un jeton JWT. Tous les appels API vérifient ce jeton.

**OmniStudio** est le cœur : il sert le front HTML, expose l'API REST, orchestre le workflow LangGraph et stocke l'état dans SQLite.

**OmniVoice** est le moteur de synthèse vocale (TTS). Il reçoit du texte, il renvoie du WAV. C'est lui qui utilise le GPU (Apple Silicon MPS, modèle k2-fsa OmniVoice).

---

## Le front (ce que l'utilisateur voit)

### Fichiers

```
omnistudio/frontend/out/
├── index.html          ← SPA, une seule page HTML
├── css/app.css          ← Styles custom (préfixe vx-*)
├── dsfr/                ← Design System de l'État (CSS + JS auto-hébergé)
└── js/
    ├── app.js           ← Chef d'orchestre (event bus, onglets, init)
    ├── auth.js          ← Gestion du jeton JWT (login, refresh, logout)
    ├── api-client.js    ← Communication avec le backend
    ├── dom-utils.js     ← Utilitaires (escapeHtml, escapeAttr, sanitizeHtml)
    ├── toast.js         ← Notifications DSFR (succès, erreur, warning)
    ├── audio-player.js  ← Player audio accessible
    ├── theme-init.js    ← Prevention flash theme (sombre/clair)
    ├── url-state.js     ← Routage hash (#import, #voices/design)
    ├── tab-import.js    ← Onglet 1 : Import
    ├── tab-clean.js     ← Onglet 2 : Préparation
    ├── tab-voices.js    ← Onglet 3 : Voix
    ├── tab-assign.js    ← Onglet 4 : Assignation
    ├── tab-generate.js  ← Onglet 5 : Génération
    └── tab-export.js    ← Onglet 6 : Export
```

**Pas de React, pas de Node, pas de build.** C'est du HTML/CSS/JS pur avec des modules ES natifs (`import`/`export`). Le navigateur charge `app.js` qui initialise tous les modules.

**Fonts preload** : le `<head>` de `index.html` précharge 3 variantes de la police Marianne (Regular, Bold, Medium) via des balises `<link rel="preload">`. Cela évite le flash de texte non stylé (FOUT) au chargement initial.

### L'event bus (comment les modules communiquent)

`app.js` contient un système de messages internes (publish/subscribe). Les modules ne se connaissent pas entre eux — ils communiquent via des événements :

```
Utilisateur clique sur l'onglet "Préparation"
    → app.js émet "tab-deactivated:tab-import"
        → tab-import.js reçoit le signal et sauvegarde ses edits
    → app.js émet "tab-activated:tab-clean"
        → tab-clean.js reçoit le signal et charge les données depuis l'API
```

Les 5 événements principaux :

| Événement | Émetteur | Effet |
|-----------|----------|-------|
| `tab-activated:<tabId>` | app.js | Le module charge ses données |
| `tab-deactivated:<tabId>` | app.js | Le module sauvegardé ses edits |
| `navigate` | boutons "Suivant", url-state | app.js switch l'onglet |
| `session-reset` | app.js (nouvelle session) | Tous les modules nettoient leur état |
| `generation-complete` | tab-generate | tab-export active son bouton |

### Cycle de vie d'un module onglet

Chaque module suit le même pattern :

```javascript
// tab-clean.js (simplifié)
export function init() {
    // 1. Poser les écouteurs d'événements (une seule fois)
    eventBus.on('tab-activated:tab-clean', loadSteps);
    eventBus.on('tab-deactivated:tab-clean', autoSave);
    eventBus.on('session-reset', reset);

    // 2. Event delegation sur le tableau (un seul listener pour tous les boutons)
    DOM.tableBody().addEventListener('click', onTableAction);
}
```

**Règle importante** : les écouteurs sont posés dans `init()`, jamais dans `render()`. Sinon les handlers se dupliquent à chaque re-rendu du tableau.

### Comment le front parle au backend

`api-client.js` est le point unique de communication. Trois patterns couvrent tous les cas :

**1. Requête simple** (charger ou sauvegarder des données) :

```javascript
// Charger les étapes
const result = await apiGet('/api/steps');
// → fetch GET avec headers Authorization + X-Thread-Id

// Sauvegarder les assignations
await apiPost('/api/assign', { assignments: [...] });
// → fetch POST avec body JSON
```

**2. Upload de fichier** (import) :

```javascript
// Upload avec barre de progression
await uploadFile('/api/import', formData, (percent) => {
    progressBar.value = percent;
});
// → XMLHttpRequest (pas fetch, car fetch ne supporte pas onProgress)
```

**3. Streaming SSE** (nettoyage, génération, export) :

```javascript
// Le serveur envoie des événements au fil de l'eau
fetchSSE('/api/clean', body, {
    onProgress: (data) => updateTable(data),    // Chaque étape nettoyée
    onDone: (data) => showResults(data),         // Tout est fini
    onError: (err) => showError(err.message),    // Erreur
});
// → POST puis lecture du flux via ReadableStream, ligne par ligne
```

Le SSE (Server-Sent Events) permet au serveur d'envoyer des événements en temps réel. Quand le LLM nettoie 50 étapes, chaque étape terminée arrive dans le navigateur sans attendre la fin du lot.

### L'intercepteur 401

Si un appel échoue parce que le jeton JWT a expiré, `api-client.js` intercepte l'erreur, appelle `refreshAccessToken()` pour obtenir un nouveau jeton auprès de Keycloak, et rejoue la requête originale. L'utilisateur ne voit rien — c'est transparent.

```
Requête GET /api/steps
    → 401 Unauthorized (jeton expiré)
    → api-client.js appelle POST /api/auth/token/refresh
    → Keycloak renvoie un nouveau jeton
    → api-client.js rejoue GET /api/steps avec le nouveau jeton
    → 200 OK
```

### Le responsive (desktop et mobile)

Breakpoint principal : **48em (768px)**.

Sur desktop, les 6 onglets sont affichés en `fr-tabs` DSFR classiques. Sur mobile, les onglets sont remplacés par un stepper (étape 1/6, 2/6...) avec des boutons précédent/suivant. Les tableaux se transforment en cartes empilées : chaque ligne devient une fiche verticale avec des labels via l'attribut `data-label` et le pseudo-élément `::before`.

---

## L'API REST (le contrat entre front et back)

### Organisation

44 endpoints répartis dans 10 routeurs. Chaque routeur = un fichier Python autonome dans `routers/` :

```
routers/
├── auth_routes.py    →  /api/auth/login, refresh, logout       (3 endpoints)
├── sessions.py       →  /api/session (créer, reprendre, lister) (4 endpoints)
├── status.py         →  /api/status (health check public)       (3 endpoints)
├── import_steps.py   →  /api/import, /api/steps                 (4 endpoints)
├── clean.py          →  /api/clean (SSE nettoyage LLM)          (8 endpoints)
├── voices.py         →  /api/voices (design, clone, preview)    (11 endpoints)
├── assign.py         →  /api/assign (voix par étape)            (4 endpoints)
├── generate.py       →  /api/generate (SSE batch TTS)           (3 endpoints)
├── export.py         →  /api/export (SSE post-traitement + ZIP) (2 endpoints)
└── audio.py          →  /api/audio/{filename} (servir les WAV)  (1 endpoint)
```

Ils sont tous enregistrés dans `routers/__init__.py` via `register_all(app)`, appelé une seule fois par `server.py`.

### Format de réponse uniforme

Toutes les réponses suivent la même structure :

```json
// Succès
{"data": {"steps": [...]}, "error": null}

// Erreur
{"data": null, "error": {"code": "TTS_BUSY", "message": "Génération en cours"}}
```

Le front n'a qu'un seul format à parser, quel que soit l'endpoint.

### Headers obligatoires

Chaque requête authentifiée porte deux headers :

- `Authorization: Bearer <jeton_jwt>` — identité de l'utilisateur
- `X-Thread-Id: <uuid_session>` — dans quel workflow il travaille

Le `thread_id` est un UUID généré à la création de la session. Il isole complètement les données d'un utilisateur (ses étapes, ses voix, ses fichiers audio).

### Flux par onglet

```
Onglet 1 — IMPORT
  POST /api/import              Upload fichier (xlsx, csv, md, txt, docx, pdf)
  POST /api/import/select       Filtrer les étapes sélectionnées
  GET  /api/steps               Lister les étapes de la session

Onglet 2 — PREPARATION
  POST /api/clean               SSE nettoyage LLM (Layer B + LLM batch)
  GET  /api/clean/diff/{id}     Diff HTML original vs nettoyé (word-level)
  POST /api/clean/accept/{id}   Accepter le texte nettoyé d'une étape
  POST /api/clean/single/{id}   Re-nettoyér une seule étape
  POST /api/clean/validate      Valider toutes les étapes d'un coup
  POST /api/clean/delete/{id}   Supprimer une étape

Onglet 3 — VOIX
  GET  /api/voices              Lister voix natives + custom
  GET  /api/voices/templates    6 templates de design prédéfinies
  POST /api/voices/design-flow  SSE design vocal (LLM brief → TTS)
  POST /api/voices/clone        Clonage vocal (audio reference + texte)
  POST /api/voices/lock         Verrouiller une voix custom pour la session
  POST /api/voices/preview      Pré-écoute d'une voix

Onglet 4 — ASSIGNATION
  GET  /api/assign              Charger les assignations voix/langue/vitesse
  POST /api/assign              Sauvegarder les assignations
  POST /api/assign/apply-all    Appliquer une voix à toutes les étapes
  POST /api/assign/preview/{id} Pré-écoute d'une étape avec ses paramètres

Onglet 5 — GENERATION
  GET  /api/generate/summary    Estimations (durée, voix uniques)
  POST /api/generate            SSE génération batch TTS
  POST /api/generate/sample     Échantillon sur 3 étapes

Onglet 6 — EXPORT
  POST /api/export              SSE post-traitement audio + création ZIP
  GET  /api/export/download     Télécharger le ZIP (auth hybride)
```

---

## Le backend (la logique)

### L'assembleur : server.py (~194 lignes)

C'est le point d'entrée de l'application. Il ne contient **aucune logique métier**. Son rôle est d'assembler les composants :

```python
# Simplifié pour la compréhension
app = FastAPI()

# 1. Cycle de vie (startup + shutdown)
@asynccontextmanager
async def lifespan(app):
    _init_sessions_db()       # Créer la table sessions SQLite
    _purge_old_sessions()     # Supprimer les sessions > 90 jours
    _purge_temp_files()       # Nettoyer les fichiers temporaires
    yield                     # L'application tourne
    # ... cleanup au shutdown (fermeture httpx client)

# 2. Middleware sécurité et performance
app.add_middleware(SecurityHeadersMiddleware)  # CSP, X-Frame-Options, HSTS, COOP
app.add_middleware(GZipMiddleware)             # Compression GZip (seuil 500 octets)
app.add_middleware(CacheControlMiddleware)     # Cache 1h en prod, no-cache en dev
app.add_middleware(CORSMiddleware, ...)        # Origins autorisées

# 3. Enregistrer les 10 routeurs d'un coup
register_all(app)

# 4. Monter les fichiers statiques (le front)
app.mount("/css", StaticFiles(directory="frontend/out/css"))
app.mount("/js", StaticFiles(directory="frontend/out/js"))
app.mount("/dsfr", StaticFiles(directory="frontend/out/dsfr"))

# 5. Route racine → la SPA
@app.get("/")
async def root():
    return FileResponse("frontend/out/index.html")
```

**Mode MINIFY** : la variable `OMNISTUDIO_MINIFY` contrôle le mode de service des fichiers front. En production (`true`), `server.py` sert les fichiers depuis `frontend/dist/` (JS/CSS minifiés par esbuild via `scripts/build-frontend.sh`). En développement (`false` ou absent), il sert directement `frontend/out/` (sources lisibles).

**Headers de sécurité avancés** : en plus du CSP et des headers classiques, `SecurityHeadersMiddleware` ajoute un header HSTS (HTTP Strict Transport Security) conditionnel quand la connexion est en HTTPS, et un header `Cross-Origin-Opener-Policy: same-origin` (COOP) pour isoler le contexte de navigation.

**Endpoint de santé** : `/api/health` est un probe non authentifié qui vérifie l'état des services critiques (OmniVoice, Keycloak, base de données, SoX, ffmpeg). Il retourne 200 si tout est opérationnel, 503 sinon. Utilisé par le superviseur (`scripts/run-forever.sh`) et le monitoring (`scripts/monitor.sh`).

### Les singletons : dependencies.py

Les objets partagés par tous les routeurs, créés une seule fois au démarrage :

```python
graph_app     # Machine d'état LangGraph (le cerveau du workflow)
design_app    # Sous-graphe de design vocal
vox_client    # Client HTTP vers OmniVoice (le moteur TTS)
limiter       # Rate limiter (slowapi)
```

**Les verrous SSE** empêchent deux opérations longues en parallèle sur la même session :

```python
_cleaning_locks = {}      # {thread_id: timestamp}
_generating_locks = {}
_exporting_locks = {}
```

Quand un nettoyage démarre, `_lock()` enregistre le `thread_id` avec un timestamp. Si un deuxième appel arrive pour la même session, `_is_locked()` renvoie `True` et l'API refuse avec le code `CLEAN_IN_PROGRESS`. À la fin (même en cas de crash), le `finally` du générateur SSE appelle `_unlock()` pour libérer le verrou.

**Les helpers** uniformisent les réponses :

```python
# Réponse succès
return api_response({"steps": steps})
# → {"data": {"steps": [...]}, "error": null}

# Réponse erreur
return api_error("TTS_BUSY", "Génération en cours", 503)
# → {"data": null, "error": {"code": "TTS_BUSY", "message": "..."}}
```

### Anatomie d'un endpoint typique

```python
# routers/assign.py (simplifié)
@router.post("/api/assign/preview/{step_id}")
@limiter.limit("10/minute")                        # Max 10 previews/min
async def preview_step(
    step_id: str,
    request: Request,
    user=Depends(get_current_user),                 # 1. Vérifie le JWT
):
    thread_id = get_thread_id(request)              # 2. Lit X-Thread-Id

    # 3. Lire l'état du workflow dans LangGraph
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)

    # 4. Récupérer les paramètres de l'étape
    step = find_step(state, step_id)
    voice = step["voice"]
    text = step["text_tts"] or step["text_original"]

    # 5. Appeler OmniVoice pour générer l'audio
    wav_path = await asyncio.to_thread(
        vox_client.preset, text, voice, step["language"]
    )

    # 6. Repondre avec l'URL du fichier audio
    return api_response({"audio_url": f"/api/audio/{wav_path}"})
```

**Le `asyncio.to_thread()`** est essentiel : LangGraph et OmniVoice sont des appels synchrones (ils bloquent le thread). Sans `to_thread`, un appel TTS de 30 secondes bloquerait toute l'application. `to_thread` délègue l'appel à un thread séparé pendant que la boucle async reste libre de traiter d'autres requêtes.

---

## Le middleware (entre le front et la logique)

### Authentification (auth.py)

```
Navigateur                    OmniStudio                     Keycloak
    │                            │                              │
    │── POST /api/auth/login ──►│                              │
    │   {username, password}     │── POST /token ──────────────►│
    │                            │◄── access_token (JWT RS256) ─│
    │◄── {access_token, refresh} │                              │
    │                            │                              │
    │── GET /api/steps ─────────►│                              │
    │   Authorization: Bearer xxx│                              │
    │                            │── Vérifie signature JWT      │
    │                            │   (JWKS en cache 1h)         │
    │◄── {data: {steps: [...]}} │                              │
```

Le jeton JWT est signé en RS256 par Keycloak. OmniStudio vérifie la signature avec la clé publique (JWKS), **sans rappeler Keycloak à chaque requête**. Le cache JWKS dure 1 heure.

Côté front, `auth.js` planifie un refresh automatique 60 secondes avant l'expiration du jeton. L'utilisateur n'a jamais à se re-connecter pendant une session de travail.

### Sécurité (server.py middleware)

Chaque réponse HTTP passe par le `SecurityHeadersMiddleware` qui ajoute :

| Header | Valeur | Protection |
|--------|--------|------------|
| Content-Security-Policy | `default-src 'self'; script-src 'self'; ...` | Bloque les scripts externes (XSS) |
| X-Frame-Options | `DENY` | Empêche l'embedding en iframe (clickjacking) |
| X-Content-Type-Options | `nosniff` | Empêche le sniffing de type MIME |
| Referrer-Policy | `strict-origin-when-cross-origin` | Limite les infos envoyées aux sites tiers |
| Permissions-Policy | `camera=(), microphone=(self)` | Restreint les APIs navigateur |

### Rate limiting (dependencies.py)

Certains endpoints sont coûteux (appel LLM, génération TTS). Le rate limiter empêche les abus :

```python
@limiter.limit("2/minute")    # Génération batch (coûteux en GPU)
@limiter.limit("3/minute")    # Nettoyage LLM (appel Albert, PRD-031)
@limiter.limit("5/minute")    # Login (anti brute-force)
@limiter.limit("10/minute")   # Preview voix, import fichier (modéré)
```

`_get_real_ip()` lit le header `X-Forwarded-For` pour identifier le vrai client derriere le proxy Tailscale Funnel.

### Verification de propriété de session (PRD-031)

Chaque endpoint qui accepte un `thread_id` vérifie que l'utilisateur authentifié est bien le propriétaire de cette session via `_verify_session_owner(thread_id, user["user_id"])`. Cette vérification empêche un utilisateur d'accéder aux données d'un autre (BOLA/IDOR).

```python
# Routeurs protégés : import_steps, clean, assign, generate, export, voices, sessions, audio
_verify_session_owner(thread_id, user["user_id"])  # -> 403 si non propriétaire
```

### Verification JWT issuer (PRD-031)

Le token JWT est vérifie avec signature, expiration, audience ET issuer :

```python
jwt.decode(token, jwks, algorithms=["RS256"],
    audience=KEYCLOAK_CLIENT_ID,
    issuer=f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}",
    options={"verify_exp": True})
```

---

## Le workflow LangGraph (le cerveau)

LangGraph est une **machine d'état persistée**. Chaque session utilisateur a un `thread_id` et un état complet sauvegardé dans SQLite. Même si le serveur redémarre, l'état est conservé — l'utilisateur reprend là où il en était.

### Le graphe principal

```
START → import → prepare_clean → clean (sous-graphe) → finalize_clean
                                                            │
                                          validated? ───► design (sous-graphe)
                                          retry?    ───► prepare_clean
                                                            │
                                                        assign → generate → export → END
```

### Les interrupts (l'interaction humaine)

C'est le mécanisme clé de LangGraph. À chaque étape, le graphe **s'arrête et attend une décision humaine** :

```python
# Configuration du graphe
interrupt_before=["prepare_clean", "design", "assign", "generate", "export"]
```

L'utilisateur fait ses choix dans le front (valide les textes, choisit les voix, etc.), puis le front appelle l'API qui injecte la décision et relance le graphe :

```python
# Le routeur reçoit la décision de l'utilisateur
graph_app.update_state(config, {"décision": "validated"})

# Le graphe reprend exactement là où il s'était arrêté
graph_app.invoke(None, config)
```

### Les sous-graphes (boucles iteratives)

Deux étapes nécessitent des allers-retours avec l'utilisateur :

**clean_loop** (nettoyage des textes) :

```
START → propose_corrections (Layer B + LLM) → human_review [interrupt]
                                                    │
                                          validated → END
                                          retry     → propose_corrections
                                          (max 10 iterations)
```

Le LLM propose des corrections, l'utilisateur valide/modifie, le LLM re-propose si nécessaire.

**design_loop** (design vocal) :

```
START → generate_instruct (LLM) → synthesize (TTS) → human_review [interrupt]
                                                          │
                                                lock    → END (voix sauvegardée)
                                                regenerate → generate_instruct
                                                (max 20 iterations)
```

Le LLM génère une description de voix (6 axes : genre, timbre, texture, ton, rythme, style), OmniVoice la synthétise, l'utilisateur écoute et choisit de garder, régénérer ou modifier.

### Le state (ce qui est persiste)

```python
# Champs clés du WorkflowState
steps: List[Dict]                    # Les étapes du scenario
assignments: Dict                    # step_id → voix assignée
generated_files: List[Dict]          # Fichiers WAV générés
locked_voices: List[str]             # Voix custom verrouillées
domain_glossary: Dict                # Glossaire métier
correction_patterns: Dict            # JSON corrections (Layer B)
cleaning_validated: bool             # Nettoyage validé ?
generation_complete: bool            # Génération terminée ?
```

Les champs annotés `Annotated[List, add]` sont en mode **append-only** : quand on fait `update_state({"generated_files": [new_file]})`, le nouveau fichier s'ajoute à la liste existante au lieu de la remplacer. C'est le pattern "reducer" de LangGraph.

---

## Le nettoyage des textes (2 couches)

Le nettoyage transforme un texte source (pensée pour être lu par un humain) en texte TTS (optimisé pour la synthèse vocale). Il fonctionne en 2 couches appliquées dans l'ordre :

### Layer B — Corrections déterministes (avant le LLM)

Chargées optionnellement via un fichier JSON. Trois types de corrections :

| Clé | Mécanisme | Exemple |
|-----|-----------|---------|
| `patterns` | Regex (`re.sub`) | `\bEPS\b` → "éducation physique et sportive" |
| `parentheses` | Remplacement exact | `(cf. annexe)` → "" (supprime) |
| `majuscules` | Remplacement exact | `COMPETENCES` → "competences" |

**Pourquoi avant le LLM ?** Le LLM reçoit un texte déjà pre-nettoyé, ce qui améliore la cohérence. Les sigles sont développés de manière uniforme sur toutes les étapes, pas au hasard selon l'humeur du LLM.

### Layer LLM — Nettoyage semantique

Un LLM (Albert par défaut) reformule le texte pour le TTS : il transforme les listes à puces en phrases fluides, développe les abréviations restantes, ajuste la ponctuation pour un rythme naturel.

Le prompt système inclut le glossaire projet si fourni.

### Layer A — Fallback sans LLM

Si le LLM est indisponible (rate-limit, timeout), un nettoyage basique regex prend le relais : suppression des listes (`-`), normalisation des espaces, ponctuation finale.

---

## Le flux complet d'une génération

Pour concrétiser, voici ce qui se passe quand l'utilisateur clique "Générer" :

```
1. tab-generate.js
   → fetchSSE('/api/generate', {fidelity: 'quality'})
   → Ouvre un flux SSE vers le backend

2. routers/generate.py reçoit la requête
   → Vérifie le JWT (get_current_user)
   → Vérifie le verrou (_is_locked → false, OK)
   → Pose le verrou (_lock)
   → Lance le générateur SSE (EventSourceResponse)

3. Le générateur groupe les étapes par (voix, langue, vitesse)
   → Pour chaque groupe :
      → Appelle vox_client.batch_preset(texts, voice, language)
         → OmniVoice reçoit les textes, charge le modèle GPU
         → Génère les WAV un par un
         → Renvoie les chemins fichiers
      → Émet un événement SSE "progress"
         → Le front met à jour la barre de progression
      → Émet un heartbeat toutes les 15s
         → Garde la connexion vivante (évite timeout navigateur)

4. Quand tout est fini :
   → Émet l'événement SSE "done" avec la liste des fichiers
   → Libère le verrou dans le finally (même si crash)

5. tab-generate.js
   → Reçoit "done", affiche les résultats avec audio players
   → Émet 'generation-complete' via l'event bus
   → tab-export.js active son bouton (il était grisé avant)
```

---

## La sécurité (couches de protection)

| Couche | Mécanisme | Fichier |
|--------|-----------|---------|
| Authentification | JWT RS256 Keycloak, JWKS cache 1h, issuer vérifie (PRD-031) | auth.py |
| Autorisation | `Depends(get_current_user)` sur 43 endpoints | routers/*.py |
| Isolation session | `_verify_session_owner` sur tous les endpoints thread-bound (PRD-031) | 9 routeurs |
| XSS | `escapeHtml()` / `escapeAttr()` sur tout contenu dynamique (PRD-031) | dom-utils.js, app.js |
| Injection SQL | Requêtes paramétrées (`?`) exclusivement | dependencies.py |
| Path traversal | `Path.resolve()` + vérification préfixe + BOLA (PRD-031) | audio.py, export.py |
| CSP | 5 directives (default-src, script-src, style-src, img-src, frame-ancestors) | server.py |
| CORS | 2 origins explicites, credentials=false | server.py |
| Rate limiting | slowapi sur 14 endpoints coûteux (PRD-031 : +clean, +import) | routers/*.py |
| Brute force | 5 tentatives/min sur login | auth_routes.py |

---

## Les outils audio (post-traitement)

OmniVoice génère du PCM 16 bits, mono, 24 kHz (limite du modèle). L'export transforme ces fichiers bruts en audio professionnel :

```
Audio brut (OmniVoice)              Post-traitement (SoX/ffmpeg)
  PCM 16 bits                       → 24 bits
  Mono                              → Stereo
  24 kHz                            → 48 kHz
  Volume variable                   → Normalisé (gain -n -3)
  Fichiers séparés                  → Concaténés avec silence inter-étapes
```

SoX est l'outil prioritaire (plus précis). Si SoX n'est pas installé, ffmpeg prend le relais comme fallback.

---

## Résumé par couche

| Couche | Rôle | Technologies |
|--------|------|--------------|
| **Front** | Interface 6 onglets, event bus, responsive | HTML/CSS/JS pur + DSFR 1.11.2 |
| **API** | 44 endpoints, format JSON uniforme | FastAPI + 10 routeurs |
| **Middleware** | Sécurité, auth JWT, rate limiting | Starlette + slowapi + python-jose |
| **Workflow** | Machine d'état persistée, orchestration | LangGraph + SQLite checkpoint |
| **Métier** | Nettoyage LLM, client TTS, audio, sous-titres | LLMClient + OmniVoiceClient + SubtitleClient (faster-whisper) + SoX/ffmpeg |
| **TTS** | Synthèse vocale GPU + tags émotionnels | OmniVoice (k2-fsa, Apple Silicon MPS) |
| **Auth** | Identité, jetons, sessions | Keycloak (Docker, realm harmonia, client `omnistudio`) |

---

## Différences structurelles omnistudio vs voxstudio

Les 4 différences suivantes sont spécifiques à ce fork. Voir le PRD v1.5 pour le détail des décisions.

### 1. Isolation multi-utilisateur des voix custom (décision 7, PRD-032)

Le schéma `meta.json` d'une voix custom est enrichi de deux champs : `owner` (sub JWT du créateur) et `system` (booléen). Le filtrage se fait **côté omnistudio** :

- `GET /api/voices` filtre : `owner == JWT.sub OR system == true`
- `DELETE`, `PATCH`, rename vérifient `owner == JWT.sub` (403 sinon, 403 toujours si `system: true`)
- `POST /voices/custom` injecte automatiquement `owner = JWT.sub`

OmniVoice ne connaît pas le concept d'utilisateur : il voit un pool global. L'isolation est la responsabilité d'omnistudio via les filtres dans `routers/voices.py`.

### 2. Multi-voix par étape via tag explicite (décision 8, PRD-033)

Chaque étape peut recevoir 1 à N segments, chacun avec sa voix. Le parser lit les tags `[voice:Marianne]` dans le texte :

```
"Bonjour. [voice:Jean] Salut ! [voice:Marianne] À vous."
→ 3 segments (Marianne par défaut, Jean, Marianne)
```

Schéma LangGraph State enrichi :

```python
class SegmentAssignment(TypedDict):
    segment_id: str
    text: str
    voice: str
    language: str
    speed: float
    instruct: Optional[str]

class StepAssignment(TypedDict):
    step_id: str
    segments: List[SegmentAssignment]
```

Voir [ARCHITECTURE-LANGGRAPH-OMNI.md](./ARCHITECTURE-LANGGRAPH-OMNI.md) pour le détail.

### 3. Anti-cascade session stale (décision 9, PRD-034)

3 intercepteurs préviennent les cascades d'erreurs 409/423 :

- **Front (`api-client.js`)** : compteur par `thread_id`, affichage fr-alert à 3 erreurs consécutives, bouton « Nouvelle session »
- **Back SSE** : check `session.is_stale()` avant chaque heartbeat, émission d'un event `stale` + fermeture propre
- **Back `dependencies.py`** : `release_stale_locks()` au démarrage de chaque SSE (seuil 10 min configurable via `OMNISTUDIO_STALE_THRESHOLD_MIN`)

### 4. Auth hybride audio préservée (pattern hérité de voxstudio)

`/api/audio/{filename}` accepte Bearer header **OU** query params `?token=&tid=` pour les `<audio src>` HTML5 qui ne transmettent pas les headers Authorization. Les deux chemins passent par `check_voice_ownership` pour empêcher les contournements IDOR.

Tests dédiés : `test_auth_hybride_audio.py` (2 scénarios : Bearer malveillant + query token malveillant).

### 5. Fast API sans `root_path` + `<base href="/omni/">`

**Décision Phase 0bis validée empiriquement** : Tailscale Funnel avec `--set-path=/omni` strippe le préfixe avant de forwarder au backend. Donc FastAPI fonctionne à la racine (pas de `root_path="/omni"` qui casserait les mounts statiques).

La cohérence est assurée par `<base href="/omni/">` dans `<head>` de `index.html`, qui normalise tous les chemins relatifs côté navigateur, que l'URL d'entrée soit `http://localhost:7870/` ou `https://mac-studio-alex.tail0fc408.ts.net/omni/`.

Les 5 `fetch('/api/...')` absolus identifiés dans `auth.js` et `app.js` doivent être rendus relatifs (`fetch('api/...')`), le `<base href>` ne s'applique pas aux fetch programmatiques. Voir [RUNBOOK-DEPLOYMENT.md](../../RUNBOOK-DEPLOYMENT.md).
