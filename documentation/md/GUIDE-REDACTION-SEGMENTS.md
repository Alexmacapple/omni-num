# Guide de rédaction pour la synthèse vocale

OmniStudio accepte 6 formats d'import : Excel (.xlsx), CSV (.csv), Markdown (.md), Word (.docx), PDF (.pdf) et Texte brut (.txt). Ce guide se concentre sur le format Excel comme format principal de rédaction. Les spécificités des autres formats sont documentées dans l'accordéon FAQ de l'onglet Import.

Ce guide recense les bonnes pratiques pour rédiger les textes des scénarios. Un texte bien rédigé en amont produit directement un audio de qualité, sans corrections intermédiaires. Les règles ci-dessous s'appliquent quel que soit le format d'import utilisé.

---

## 1. Écrire pour l'oreille, pas pour l'écran

Le texte sera lu à voix haute par un moteur de synthèse vocale. Il faut donc écrire **exactement ce qu'on veut entendre**.

Concret :
- Lire son texte à voix haute avant de le valider
- Se demander : "est-ce qu'un narrateur lirait ça naturellement ?"
- Éviter toute mise en forme visuelle (le moteur ne voit que du texte brut)

---

## 2. Orthographe et accents

Le moteur TTS est sensible aux fautes : un mot mal orthographié sera mal prononcé ou ignoré.

| Fréquent dans les fichiers | Forme correcte |
|---------------------------|----------------|
| beneficiaire, bénéfiiaire, bénéficaire | bénéficiaire |
| selectionner, séléctionner | sélectionner |
| necessaire, nécéssaire | nécessaire |
| reception | réception |
| instuire | instruire |
| chagement | changement |
| boutoon | bouton |

Recommandations :
- Activer le correcteur orthographique d'Excel (Révision > Orthographe)
- Porter une attention particulière aux **accents** : é, è, ê, à, ç, ô, î, û
- Relire les mots techniques et les noms propres lettre par lettre

---

## 3. Pas de listes à puces ni de numérotation

Les listes sont un formatage visuel. À l'oral, elles n'existent pas.

Mauvais :
```
Le bénéficiaire peut :
- accepter le dossier
- refuser le dossier
- demander une modification
```

Bon :
```
Le bénéficiaire peut accepter le dossier, le refuser, ou demander une modification.
```

Règle : rédiger des **phrases complètes et fluides**, reliées par des virgules ou des points.

---

## 4. Pas de parenthèses

Les parenthèses créent une rupture de rythme incompatible avec la lecture orale. Le moteur les ignore ou les lit de manière mécanique.

Mauvais :
```
Le délégué instruit le dossier (Vérification des erreurs éventuelles)
```

Bon :
```
Le délégué instruit le dossier, en vérifiant les erreurs éventuelles.
```

Mauvais :
```
Le formulaire ADN (Page 1 et 2)
```

Bon :
```
Le formulaire ADN, pages 1 et 2.
```

Règle : intégrer le contenu des parenthèses directement dans la phrase, avec une virgule ou une reformulation.

---

## 5. Pas de guillemets

Les guillemets (", « ») sont supprimés avant la synthèse. Si un terme doit être mis en valeur, reformuler la phrase.

Mauvais :
```
Il clique sur le bouton «Accepter»
```

Bon :
```
Il clique sur le bouton Accepter.
```

---

## 6. Pas de mots en MAJUSCULES

Les mots entièrement en majuscules sont destinés à l'affichage écran. Le moteur TTS les interprète mal (épellation lettre par lettre, ou ton robotique).

| Mauvais | Bon |
|---------|-----|
| MES DOSSIERS | Mes Dossiers |
| EN INSTRUCTION | en instruction |
| TOUT SÉLECTIONNER | Tout sélectionner |
| FORMULAIRE RECETTE | Formulaire Recette |

Règle : utiliser la **casse normale** (majuscule uniquement en début de phrase ou sur les noms propres).

---

## 7. Écrire les abréviations en toutes lettres

Le moteur prononce les abréviations telles quelles, ce qui donne un résultat incompréhensible.

| Mauvais | Bon |
|---------|-----|
| DN | Démarches Numériques |
| MOA | la maîtrise d'ouvrage |
| l'ETL | l'outil de synchronisation |
| CS | correspondant social |

Règle : **toujours développer les sigles et abréviations** dans le texte. Si un sigle revient souvent, le développer au moins à la première occurrence de chaque étape.

---

## 8. Ponctuation complète

La ponctuation guide le rythme et les pauses du moteur vocal. Un texte sans ponctuation sera lu d'une traite, sans respiration.

Recommandations :
- **Terminer chaque cellule par un point** (ou un point d'exclamation/interrogation)
- Utiliser les **virgules** pour marquer les pauses naturelles
- Mettre un **point entre chaque idée distincte** plutôt qu'un texte fleuve
- Vérifier qu'il y a un espace après chaque point

Mauvais :
```
Le délégué consulte la page ADN gestion composée d'un menu à gauche et d'une vue centrale il clique ensuite sur Mes Dossiers
```

Bon :
```
Le délégué consulte la page ADN gestion, composée d'un menu à gauche et d'une vue centrale. Il clique ensuite sur Mes Dossiers.
```

---

## 9. Une phrase, une idée

Les phrases longues produisent un rendu monotone et difficile à suivre. Découper les étapes complexes en phrases courtes.

Mauvais :
```
Le délégué choisit de cliquer sur le bouton correspondant au label indiqué soit le bouton à accepter si le dossier est jugé conforme soit le bouton à modifier si le dossier comporte des erreurs de saisies non conformes soit le bouton à refuser si le demandeur ne peut en bénéficier
```

Bon :
```
Le délégué choisit de cliquer sur le bouton correspondant au label indiqué. Soit le bouton Accepter, si le dossier est jugé conforme. Soit le bouton Modifier, si le dossier comporte des erreurs de saisie. Soit le bouton Refuser, si le demandeur ne peut en bénéficier.
```

---

## 10. Accords grammaticaux

Les erreurs d'accord ne sont pas corrigées par le moteur et s'entendent clairement à l'écoute.

| Mauvais | Bon |
|---------|-----|
| informations utile | informations utiles |
| sont fait via | sont faites via |
| transmis aux bénéficiaires | transmises aux bénéficiaires |
| composé d'un menu (pour "page") | composée d'un menu |

Règle : relire chaque phrase en vérifiant que les adjectifs et participes s'accordent avec leur sujet.

---

## 11. Pas de caractères spéciaux ni de références techniques

Certains caractères et notations sont illisibles par le moteur vocal.

| Mauvais | Bon |
|---------|-----|
| N°1234 | dossier numéro 1234 |
| mel | mail |
| / (comme séparateur) | ou, et |

Règle : remplacer les symboles par leur équivalent en mots.

---

## 12. Pas de mots collés ni de coquilles de saisie

Les mots collés ou les inversions de lettres ne sont pas interprétés par le moteur.

| Mauvais | Bon |
|---------|-----|
| depuisGrist | depuis Grist |
| sue positionne sue | se positionne sur |
| ll recherche | Il recherche |
| sI l'analyse | Si l'analyse |

Règle : relire chaque cellule en entier. Vérifier les espaces entre les mots et la première lettre de chaque phrase.

---

## Checklist avant livraison

Avant de transmettre le fichier Excel, vérifier pour chaque cellule de texte :

- [ ] Le texte se lit naturellement à voix haute
- [ ] Pas de fautes d'orthographe ni d'accents manquants
- [ ] Pas de listes à puces ni de numérotation
- [ ] Pas de parenthèses
- [ ] Pas de guillemets
- [ ] Pas de mots en MAJUSCULES (sauf noms propres)
- [ ] Toutes les abréviations sont développées
- [ ] Chaque cellule se termine par un point
- [ ] Phrases courtes, une idée par phrase
- [ ] Accords grammaticaux vérifiés
- [ ] Pas de caractères spéciaux (N°, /, etc.)
- [ ] Pas de mots collés ni d'espaces manquants
