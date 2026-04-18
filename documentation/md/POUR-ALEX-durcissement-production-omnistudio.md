# Durcissement production OmniStudio — Ce qu'il faut retenir

Ce document décortique le travail de durcissement réalisé le 21 mars 2026, de la note initiale de 16/20 jusqu'au 19.5/20 final. Pas un tutoriel — un retour d'expérience sur les décisions prises, les erreurs commises et les leçons à garder.

---

## 1. Approche choisie

On est parti d'un audit brut : lancer les 4 analyses en parallèle (structure, sécurité, tests, frontend), puis consolider les résultats en un score par axe. L'idée était de ne pas deviner ce qui manque, mais de le mesurer.

Le score 16/20 a réveillé l'évidence : le projet était fonctionnellement solide (28 PRD terminés, parcours complet, ops en place) mais les entrées utilisateur n'étaient jamais validées. C'est comme avoir une maison avec un bon toit, un bon chauffage, mais des fenêtres ouvertes au rez-de-chaussée.

La stratégie a été : un PRD unique (029) couvrant tout ce qui manque, exécuté en 5 phases ordonnées (sécurité d'abord, cosmétique en dernier). On ne touche pas à l'architecture — on durcit ce qui existe.

---

## 2. Alternatives écartées

**PRD multiples vs PRD unique** : on aurait pu faire un PRD sécurité, un PRD qualité, un PRD tests. On a choisi un PRD unique parce que les corrections sont interdépendantes : la validation du `thread_id` impacte les tests, qui impactent la couverture, qui impacte le score. Découper aurait créé des allers-retours inutiles.

**UUID strict vs regex permissive** : le council Red Team suggérait un pattern UUID strict (`^[0-9a-f]{8}-...`). On l'a écarté parce qu'on ne contrôle pas tous les systèmes qui pourraient générer des thread_id à l'avenir. La regex `^[a-zA-Z0-9\-_]{1,64}$` bloque les attaques (pas de `/`, pas de `..`, pas de `;`) sans casser la compatibilité. C'est le principe de la liste noire intelligente plutôt que la liste blanche rigide.

**noop_lifespan vs fix cause racine** : la première version du PRD proposait de masquer le crash lifespan avec un `os.chdir()` dans la fixture de test. Le council Red Team a identifié que c'était un pansement — la vraie maladie était un chemin relatif (`data/omnistudio_dsfr_sessions.db`). On a corrigé la cause racine avec `os.path.dirname(__file__)`. La leçon : quand un test échoue, ne jamais mocker le symptôme avant d'avoir compris la cause.

---

## 3. Architecture et articulation

L'ordre d'exécution n'est pas aléatoire :

1. **Sécurité d'abord** — parce que les validations d'entrée sont le socle. Si on corrige les `print()` avant de valider les entrées, on ajoute du logging sur des chemins potentiellement dangereux.
2. **Fix du test cassé** — parce qu'on ne peut pas mesurer la couverture si un test crashe.
3. **Tests de sécurité** — pour prouver que les corrections de l'étape 1 fonctionnent.
4. **print() -> logger** — nettoyage non-fonctionnel, risque de régression quasi nul.
5. **Frontend** — dernier car le moins risqué (suppression de `console.warn`, pas de logique ajoutée).

C'est le principe du chirurgien : on opère d'abord ce qui saigne, ensuite ce qui fait mal, ensuite ce qui est moche.

Les corrections touchent 3 couches distinctes qui ne se mélangent pas :
- **Couche entrée** (dependencies.py, routers) : validation des inputs
- **Couche interne** (core/, graph/) : remplacement print -> logger
- **Couche sortie** (frontend JS) : suppression des logs console

Chaque couche peut être testée indépendamment. Si on casse la validation thread_id, seuls les tests de sécurité échouent. Si on casse un logger, seul le test regex (`test_clean_loop`) échoue. Pas d'effet domino.

---

## 4. Outils et méthodes

**Analyse connu-inconnu (Rumsfeld)** : utilisée 3 fois sur le même PRD (v1.0, v2.0, v2.1). Chaque passage a révélé un angle mort que le précédent avait manqué. La première passe a trouvé les 2 endpoints hybrides. La deuxième a identifié le mauvais import slugify. La troisième a détecté le `.coveragerc` mal placé. C'est comme polir une lentille — chaque passe enlève une couche d'imperfection invisible à l'oeil nu.

**Council multi-modèles (devil's advocate)** : Claude en Red Team, Gemini en Blue Team, Codex en Purple Team. Le résultat le plus utile n'est pas venu du meilleur modèle (Claude, score 0.86) mais de la confrontation : Gemini défendait le `os.chdir()` comme « pragmatique », Claude l'attaquait comme « hack fragile ». La vérité était du côté de l'attaquant — mais sans le défenseur, on n'aurait pas poussé l'analyse aussi loin.

Ironie notable : Codex a analysé le mauvais PRD (un PRD du projet Council au lieu de OmniStudio). Son analyse était techniquement correcte mais complètement hors-sujet. Ça illustre un piège du multi-modèles : la confiance dans le nombre ne vaut que si tous les modèles regardent la même chose.

**Vérification d'état (skill)** : après chaque correction, on ne se fie jamais à la valeur de retour. On injecte des données synthétiques, on exécute, puis on lit séparément la source de vérité. Quand la regex rejette `../../../etc`, on ne croit pas le test unitaire — on vérifie avec un vrai `TestClient` et un endpoint réel.

---

## 5. Compromis

**Sécurité vs rétrocompatibilité** : la regex thread_id rejette les caractères spéciaux, ce qui bloque toute évolution vers des thread_id contenant des points ou des espaces. On a choisi la sécurité parce que les 20 thread_id en base sont des UUID (tirets + alphanum), et que les futurs thread_id seront générés par LangGraph (même format). Si un jour un système externe envoie des thread_id avec des points, la regex devra évoluer. Mais c'est un problème explicite, pas une faille silencieuse.

**Suppression des console.warn vs remplacement par un feedback utilisateur** : on a supprimé 6 `console.warn/error` sans les remplacer par des toasts ou des messages UI. Le compromis est que certains échecs deviennent silencieux (chargement des templates voix, pré-assignation). On l'a accepté parce que ces fonctionnalités sont optionnelles — l'utilisateur peut toujours taper l'instruction manuellement ou assigner à la main. Mais si un utilisateur se plaint que « les templates ne chargent plus », la première chose à faire sera d'ajouter un toast DSFR pour rendre l'échec visible.

**Keycloak `start` vs `start --optimized`** : le mode `start` (production) fait un build à chaque démarrage (~6s). Le mode `start --optimized` pré-compile une fois, puis démarre instantanément. On a choisi `start` parce que la configuration peut changer entre les redémarrages (ajout d'un client, modification du realm), et `--optimized` ignorerait ces changements. Pour 5 utilisateurs, 6 secondes de démarrage supplémentaires ne justifient pas la complexité d'un pipeline de build.

---

## 6. Erreurs et impasses

**Le noop_lifespan** : la première version du PRD proposait de mocker le lifespan avec un générateur vide. C'est comme débrancher l'alarme incendie parce qu'elle sonne — on supprime le symptôme sans traiter la cause. Le council Red Team l'a identifié, et la correction a été de rendre `_sessions_db_path` absolu. Moralité : quand un test échoue au setup, le problème est rarement dans le test.

**Le comptage des print()** : le council Red Team affirmait que le PRD listait 11 print() mais que l'audit en trouvait 10. On a recompté : 5 + 2 + 1 + 3 = 11. Le council s'était trompé. Ça illustre un piège de la revue par IA : un modèle qui affirme avec confiance « votre décompte est faux » peut vous faire douter de votre propre vérification. Toujours recompter soi-même.

**Le mot de passe admin Keycloak** : la variable `KEYCLOAK_ADMIN_PASSWORD` dans le docker-compose ne s'applique qu'à la première création de l'utilisateur admin. Quand la DB H2 existe déjà (volume persistant), le mot de passe env est ignoré. On a dû changer le mot de passe via `kcadm.sh set-password` en utilisant l'ancien mot de passe d'abord. C'est un piège classique de Docker : les variables d'environnement d'initialisation ne sont pas des variables de configuration.

**Le realm-export.json traqué en git** : le dossier `gitingore/` était bien dans `.gitignore`, mais le fichier avait été commité avant l'ajout de la règle. Git ne supprime pas automatiquement les fichiers déjà suivis quand on les ajoute au gitignore. Il faut un `git rm --cached` explicite. C'est comme fermer la porte après que le chat est sorti — il faut aussi aller chercher le chat.

---

## 7. Pièges à éviter

**Ne jamais faire confiance à `os.path.join()` avec des entrées utilisateur.** `os.path.join("uploads", "../../../etc/passwd")` retourne `../../../etc/passwd` — le premier argument est simplement ignoré. Toujours `os.path.basename()` avant de joindre.

**`except:` sans type attrape `KeyboardInterrupt` et `SystemExit`.** Un Ctrl+C pendant une concaténation audio serait avalé silencieusement. Toujours `except Exception:` au minimum.

**Docker `restart` ne recharge pas le `.env`.** Seul `docker compose up -d` (qui recrée le conteneur) prend en compte les changements de variables d'environnement. `docker compose restart` garde les anciennes valeurs. Nombre de « ça ne marche pas après modification du .env » viennent de là.

**`shutil.which()` est synchrone mais non-bloquant.** Pas besoin de `asyncio.to_thread()` pour vérifier si `sox` est installé — c'est un simple lookup dans le PATH, pas une exécution de commande.

**Les fichiers dans `out/` sont les sources, pas les outputs.** Le nom `out` est trompeur. Le vrai output de build est `out-dist/`. Le council Red Team a failli bloquer le PRD à cause de cette confusion de nommage. Si c'était à refaire, on renommerait `out/` en `src/` et `out-dist/` en `dist/`.

---

## 8. Regard expert

**La défense en profondeur fonctionne.** La validation du thread_id est faite dans `get_thread_id()` (point central) ET dans les 2 endpoints hybrides (défense en profondeur). Si un futur développeur ajoute un endpoint qui lit `X-Thread-Id` sans passer par `get_thread_id()`, la regex dans les endpoints hybrides sert de filet de sécurité. C'est le même principe que les ceintures de sécurité ET les airbags : on ne choisit pas l'un ou l'autre.

**Le `_BASE_DIR = os.path.dirname(__file__)` est le pattern le plus sous-estimé de Python.** Il transforme un chemin relatif fragile (dépendant du `cwd`) en chemin absolu robuste (dépendant du fichier source). Chaque projet Python devrait avoir cette ligne dans son module de configuration. Le fait que OmniStudio l'utilisait déjà pour les logs (ligne 39) mais pas pour la base de données (ligne 122) montre qu'un pattern correct appliqué à un endroit ne se propage pas automatiquement aux autres.

**Le score 19.5/20 est honnête parce que le demi-point manquant est structurel.** Le `unsafe-inline` dans la CSP est imposé par le DSFR (le Design System de l'État injecte des styles inline). Ce n'est pas un défaut du projet, c'est une contrainte du framework. Un évaluateur qui donnerait 20/20 en ignorant cette réalité serait malhonnête. Un évaluateur qui retirerait plus de 0.5 point pour une contrainte que le projet ne peut pas résoudre serait injuste.

---

## 9. Leçons transférables

**Un audit automatisé vaut mieux qu'une revue manuelle.** Lancer 4 agents en parallèle (structure, sécurité, tests, frontend) a produit en 90 secondes ce qu'une revue humaine aurait pris une journée. La clé : des questions précises (« chercher les print() dans tel répertoire ») plutôt que des instructions vagues (« vérifie la qualité »).

**L'analyse itérative bat l'analyse unique.** Trois passes de connu-inconnu sur le même PRD ont trouvé 7 problèmes que la première passe avait ratés. Chaque itération révèle les hypothèses implicites de l'itération précédente. C'est le principe du polissage : la première passe enlève le gros, les suivantes révèlent les défauts fins.

**Le meilleur test de sécurité est une donnée malveillante réelle.** Tester `X-Thread-Id: ../../../etc` contre un vrai endpoint avec un vrai `TestClient` est plus fiable que de tester la regex en isolation. L'intégration révèle les problèmes que l'unité masque (comme l'authentification qui rejette avant la validation).

**Documenter les dérogations explicitement.** Le PRD-029 modifie `graph/` et `core/` — zones déclarées « inchangées » dans le CLAUDE.md. Au lieu de le faire en silence, on a ajouté une section « Dérogation » dans le PRD et mis à jour le CLAUDE.md. Dans 6 mois, quand quelqu'un lira « ne jamais modifier graph/ », il verra la note « sauf PRD-029, modifications non-fonctionnelles » et comprendra pourquoi.

**Le council multi-modèles est utile pour la confrontation, pas pour le consensus.** Le modèle le plus utile n'est pas celui qui a raison le plus souvent, c'est celui qui pose la question que personne n'avait posée. Le `os.chdir()` serait passé en production sans la Red Team. Le vrai ROI du council n'est pas la réponse finale — c'est la question qui fait douter.
