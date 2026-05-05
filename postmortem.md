# Postmortem prospectif — Gate prod OmniStudio

Date : 2026-05-05
Objet : identifier ce qui pourrait empecher OmniStudio de partir en production et poser une gate de validation en 10 points.

> Ce document est une premortem de production : on suppose que le lancement a echoue, puis on transforme les causes probables en criteres go/no-go.

## Etat connu

- Depot : `omni-num`
- Branche : `main`
- Dernier commit de cloture : `9c9029b chore: Sauvegarde clôture session`
- CI GitHub Actions : verte sur `main`
- Tests locaux references : `590 passed / 162 skipped / 0 failed`
- Coverage Python : `84 %`
- Qualite depot : **18/20 atteint** en Phase 10
- Stack cible : Keycloak `8082`, OmniVoice `8070`, OmniStudio `7870`, Funnel public `/omni`
- URL publique : `https://mac-studio-alex.tail0fc408.ts.net/omni/`

## Synthese premortem

Le risque principal n'est plus le depot. La CI, les tests, le build frontend, les smokes assets et le scan securite donnent un socle correct.

Le risque principal est de confondre **repo pret** et **service operable en production**. OmniStudio peut etre techniquement sain dans GitHub Actions et echouer en prod sur Keycloak, Funnel `/omni`, OmniVoice, memoire MPS/Whisper, backup SQLite, droits utilisateurs, quotas ou audit RGAA final.

## Decision de cadrage

Avant la gate, choisir explicitement le niveau de production vise.

| Type de prod | Niveau de blocage |
|---|---|
| Prod controlee / interne / utilisateurs connus | Gate 10 points obligatoire, RGAA approfondi recommande |
| Prod publique large / institutionnelle | Gate 10 points obligatoire, RGAA approfondi bloquant, quotas et privacy voix bloquants |

## Gate prod en 10 points

Chaque point doit avoir une preuve concrete avant le go prod. Si une preuve manque, le statut est **No-Go** ou **Go limite**.

### 1. Cadrage prod valide

**Question go/no-go :** sait-on exactement pour qui on ouvre OmniStudio et a quel niveau d'exposition ?

**Critere Go :**
- audience definie : interne, beta controlee ou publique ;
- nombre d'utilisateurs attendu ;
- proprietaire operationnel identifie ;
- regle de support connue.

**Preuve attendue :**
- une ligne de decision dans `todo.md`, `RUNBOOK-DEPLOYMENT.md` ou un ticket de lancement.

**No-Go si :**
- on dit seulement "on met en prod" sans preciser audience, support et niveau d'exposition.

### 2. Stack runtime saine

**Question go/no-go :** les trois services critiques repondent-ils ensemble ?

**Critere Go :**
- Keycloak repond sur `8082` ;
- OmniVoice repond sur `8070` ;
- OmniStudio repond sur `7870` ;
- Funnel `/omni` sert l'application publique.

**Preuve attendue :**

```bash
./scripts/monitor.sh
curl http://localhost:7870/api/health
curl http://localhost:8070/health
tailscale funnel status
```

**No-Go si :**
- un service est degrade ;
- `memory_pressure` depasse le seuil cible ;
- Funnel ne route plus `/omni`.

### 3. Auth Keycloak reelle

**Question go/no-go :** un vrai utilisateur peut-il se connecter et appeler l'API ?

**Critere Go :**
- login Keycloak OK ;
- JWT contient `aud=omnistudio` ;
- refresh token OK ;
- appel API authentifie OK apres refresh.

**Preuve attendue :**
- test manuel ou E2E avec `omni-e2e` ;
- absence de `401 Invalid audience`.

**No-Go si :**
- login OK mais API refuse le token ;
- mapper audience absent ;
- client `omnistudio` mal recree dans le realm `harmonia`.

### 4. Routage Funnel `/omni` intact

**Question go/no-go :** l'application fonctionne-t-elle derriere Funnel sans casser les assets ?

**Critere Go :**
- aucun `root_path="/omni"` dans FastAPI ;
- `<base href="/omni/">` present dans `index.html` ;
- assets CSS/JS servis en HTTP 200 sous `/omni/`.

**Preuve attendue :**

```bash
./scripts/verify-assets-prefix.sh
WARN_AS_ERROR=1 ./scripts/test-smoke.sh
```

**No-Go si :**
- assets en 404 via Funnel ;
- regression `root_path` ;
- chemins frontend absolus revenus dans le build.

### 5. Parcours utilisateur complet valide

**Question go/no-go :** un utilisateur peut-il produire un livrable de bout en bout ?

**Critere Go :**
- import d'un scenario ;
- preparation et sauvegarde ;
- selection ou creation de voix ;
- assignation voix/langue/vitesse ;
- generation batch ;
- export ZIP avec audio ;
- option SRT testee au moins une fois.

**Preuve attendue :**
- capture de test manuel ou Playwright ;
- ZIP exporte et reouvert ;
- logs sans traceback.

**No-Go si :**
- la CI est verte mais aucun parcours reel complet n'a ete rejoue sur l'URL publique.

### 6. Charge, memoire et modeles lourds

**Question go/no-go :** OmniVoice, MPS et Whisper tiennent-ils sous un usage realiste ?

**Critere Go :**
- generation batch representative terminee ;
- transcription SRT representative terminee ;
- premier boot Whisper documente ;
- `memory_pressure < 0.5` sous charge cible.

**Preuve attendue :**

```bash
./scripts/monitor.sh
```

**No-Go si :**
- la generation longue bloque la machine ;
- Whisper telecharge ou charge le modele au mauvais moment ;
- OmniVoice devient instable quand VoxStudio tourne en parallele.

### 7. Donnees, sauvegarde et restauration

**Question go/no-go :** peut-on perdre la machine sans perdre le service ?

**Critere Go :**
- base SQLite LangGraph sauvegardee ;
- voix custom et metadonnees sauvegardees si elles sont en scope prod ;
- restauration testee une fois ;
- nettoyage exports/uploads defini.

**Preuve attendue :**

```bash
./scripts/backup-db.sh
# puis test de restauration selon documentation/md/RUNBOOK-OPS.md
```

**No-Go si :**
- backup configure mais jamais restaure ;
- emplacement exact des donnees critiques flou ;
- exports audio s'accumulent sans retention.

### 8. Securite, secrets et abus

**Question go/no-go :** l'exposition ne permet-elle pas fuite de secrets, abus GPU/disque ou fichiers invalides ?

**Critere Go :**
- `scripts/security-smoke.sh` vert ;
- uploads bornes ;
- types audio valides ;
- aucun secret versionne ;
- politique de taille max scenario/export connue ;
- quotas ou limite d'usage decidee pour une prod large.

**Preuve attendue :**

```bash
./scripts/security-smoke.sh
git status -sb
```

**No-Go si :**
- secret en clair ;
- absence de limite sur generation/transcription pour une exposition publique ;
- runtime audio genere visible dans Git.

### 9. RGAA, DSFR et compatibilite navigateur

**Question go/no-go :** l'interface est-elle acceptable pour le niveau d'exposition vise ?

**Critere Go :**
- DSFR intact ;
- navigation clavier critique OK ;
- contrastes et labels critiques OK ;
- pas d'overlap UI bloquant ;
- audit RGAA approfondi realise avant prod publique large.

**Preuve attendue :**
- rapport RGAA/a11y ou checklist manuelle ;
- Lighthouse si exposition publique plus large.

**No-Go si :**
- prod publique large sans audit RGAA final ;
- parcours principal inaccessible au clavier ;
- erreurs DSFR visibles sur le workflow 6 onglets.

### 10. Runbook, rollback et responsabilite

**Question go/no-go :** sait-on quoi faire si la prod casse ?

**Critere Go :**
- procedure start/stop connue ;
- logs localises ;
- rollback possible ;
- backup disponible ;
- personne responsable identifiee ;
- procedure Keycloak connue ;
- commande Funnel connue.

**Preuve attendue :**
- `RUNBOOK-DEPLOYMENT.md` et `documentation/md/RUNBOOK-OPS.md` a jour ;
- test restart realise ;
- dernier commit deploye note.

**No-Go si :**
- personne ne sait restaurer, redemarrer Keycloak, retirer `/omni` ou revenir au dernier commit sain.

## Verdict operationnel

| Niveau | Verdict |
|---|---|
| Depot / CI / qualite code | Pret Phase 10, **18/20 atteint** |
| Prod controlee interne | Probablement proche, sous reserve de passer la gate 10 points |
| Prod publique large | Pas encore sans audit RGAA approfondi, quotas, backup/restore prouve et validation privacy voix |

## Checklist finale go/no-go

- [ ] Niveau de prod choisi : interne, beta controlee ou publique large
- [ ] `./scripts/monitor.sh` vert
- [ ] `/api/health` OmniStudio vert
- [ ] `/health` OmniVoice vert
- [ ] Funnel `/omni` verifie
- [ ] Login Keycloak utilisateur reel OK
- [ ] Parcours complet import -> generation -> export OK sur URL publique
- [ ] SRT teste une fois avec Whisper
- [ ] Backup + restauration testes
- [ ] `scripts/security-smoke.sh` vert
- [ ] Audit RGAA adapte au niveau d'exposition
- [ ] Rollback et responsable prod identifies

## Prochaine action recommandee

Executer la gate comme une revue de lancement courte : 60 a 90 minutes, preuves dans ce fichier, puis decision **Go**, **Go limite** ou **No-Go**.
