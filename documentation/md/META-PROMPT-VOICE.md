# Meta-prompt vocal - Guide k2-fsa OmniVoice Voice Design

Guide de rédaction des prompts vocaux (`voice_instruct`) pour k2-fsa OmniVoice via OmniVoice.
Basé sur les retours d'expérience du projet ADN Scénarios.

---

## Format attendu

k2-fsa OmniVoice Voice Design attend un `voice_instruct` en **une phrase descriptive continue**, attributs séparés par des virgules. Le modèle 1.7B-VoiceDesign lit cette description linéaire et en extrait un embedding vocal (`prompt.pt`).

```
Bon  : "Voix masculine française jeune, timbre clair, ton engageant, rythme soutenu"
Mauvais : "## Timbre\n- Clair\n## Ton\n- Engageant"
```

Pas de markdown, pas de bullets, pas de sections, pas de JSON.

---

## Les 6 axes vocaux

L'ordre n'est pas strict, mais ces axes couvrent l'espace vocal du modèle :

| Axe | Ce qu'il contrôle | Exemples de valeurs |
|-----|-------------------|---------------------|
| **Genre + langue + âge** | Identité de base | masculine/féminine, française, jeune/mature/âgée |
| **Timbre** | Couleur de la voix | clair/sombre, brillant/rond, grave/aigu, chaleureux/froid |
| **Texture** | Grain, souffle, proximité | sèche/soufflée, précise/veloutée, micro proche/distant |
| **Ton émotionnel** | Intention, émotion | engageant, rassurant, confiant, bienveillant, autoritaire |
| **Rythme** | Débit, pauses | lent/modéré/soutenu, pauses courtes/longues, respirations |
| **Style/référence** | Contexte d'usage | keynote, formation en ligne, documentaire, podcast |

---

## Template

```
Voix [genre] [langue] [âge relatif], timbre [couleur/graves/aigus], texture [grain/proximité], ton [émotion 1] [émotion 2] et [émotion 3], [énergie], rythme [débit] [pauses], style [référence contexte], diction [qualité]
```

### Longueur optimale

Entre **30 et 80 mots**. Les descriptions plus longues et détaillées (type frpro, 70 mots) produisent des voix plus stables et naturelles.

---

## Exemples

### Narrateur dynamique (v1 - 27 mots)

```
Voix masculine française jeune et énergique, ton engageant et moderne, rythme légèrement soutenu, style démo produit tech, diction précise
```

### Narrateur dynamique (v2 - 45 mots)

```
Voix masculine française jeune et brillante, timbre clair légèrement grave et chaleureux, texture sèche et précise type micro proche, ton engageant optimiste et confiant, haute énergie constante et passionnée, rythme soutenu avec pauses courtes entre les idées, style keynote démo produit tech, diction nette et articulée
```

### Narratrice institutionnelle

```
Voix féminine française mature, timbre rond et grave, texture veloutée type studio, ton rassurant bienveillant et professionnel, énergie calme et constante, rythme modéré avec respirations naturelles, style formation en ligne institutionnelle, diction soignée et articulée
```

### Narrateur chaleureux

```
Voix masculine française ronde et chaleureuse, timbre grave et doux, texture légèrement soufflée type proximité, ton rassurant empathique et accompagnant, énergie douce et régulière, rythme lent et posé, style guide d'accompagnement, diction soignée
```

### Français professionnel natif (référence qualité - 70 mots)

```
Voix masculine française native, extrêmement fluide et naturelle. L'élocution est celle d'un locuteur s'exprimant avec une aisance totale, sans aucune rupture de rythme. La prosodie est typiquement française : plate, régulière, avec des liaisons fluides entre les mots. Les fins de phrases sont posées et descendantes, sans l'intonation montante anglo-saxonne. Le timbre est chaleureux, professionnel et proche du micro. L'accent est neutre, de type métropolitain, sans aucune emphase dramatique.
```

---

## Ce que le modèle contrôle mal

| Aspect | Problème | Solution |
|--------|----------|----------|
| **Genre** | Le non-déterminisme peut inverser le genre perçu | Générer plusieurs fois, garder le bon |
| **Âge précis** | "25-35 ans" n'est pas interprétable | Utiliser "jeune", "mature", "âgée" |
| **Consignes négatives** | "pas de nasillard" est ignoré ou mal compris | Formuler positivement : "timbre clair et rond" |
| **Rythme chiffré** | "120 mots par minute" n'a pas de sens | Utiliser "lent", "modéré", "soutenu" |
| **Accents régionaux** | Le modèle ne distingue pas les accents fins | "français standard" suffit |

**Règle** : toujours formuler en termes positifs (ce qu'on veut), jamais en termes négatifs (ce qu'on ne veut pas).

---

## Conflits entre attributs

Quand deux attributs du `voice_instruct` se contredisent, le modèle arbitre de manière imprévisible.

| Conflit | Résultat probable | Recommandation |
|---------|-------------------|----------------|
| "grave" + "jeune énergique" | Instabilité de timbre entre les phrases | Choisir : grave mature OU aigu énergique |
| "lent" + "haute énergie" | Le modèle privilégie l'énergie, ignore le rythme | Aligner énergie et rythme |
| "chaleureux" + "autoritaire" | Oscillation entre les deux tons | Prioriser un ton, nuancer l'autre ("chaleureux avec une pointe d'assurance") |
| "soufflée" + "précise" | Textures incompatibles | Choisir l'une ou l'autre |

**Règle de précédence** : en cas de doute, prioriser **intelligibilité > style > expressivité**. Un résultat clair et plat vaut mieux qu'un résultat expressif mais instable.

---

## Artefact de démarrage

Le décodeur audio produit parfois un mot parasite en début de phrase. Ce n'est pas lié au prompt mais au modèle.

**Solutions** :
1. Préfixer le texte avec un mot de liaison ("Ensuite,", "Puis,")
2. Regénérer (non-déterminisme, chaque résultat diffère)
3. Trimmer les premières millisecondes en post-traitement

```bash
sox input.wav output.wav trim 0.2
```

---

## Workflow itératif

Le meta-prompt vocal n'est pas un one-shot. Le workflow réaliste :

1. **Rédiger** le `voice_instruct` avec le template (6 axes)
2. **Générer** 3-5 fois avec `/design` (non-déterminisme)
3. **Écouter**, identifier ce qui manque ou déborde
4. **Ajuster** les adjectifs (pas la structure)
5. **Sauvegarder** l'embedding quand le résultat convient

L'embedding sauvegardé (`prompt.pt`) fige la voix. Le `voice_instruct` n'est plus utilisé après la sauvegarde.

Quand un résultat est satisfaisant, le documenter comme **référence validée** : noter le `voice_instruct` exact, le texte de test, et conserver le WAV produit. Ces triplets (prompt, texte, audio) constituent le jeu de référence du projet.

---

**Dernière mise à jour** : 2026-03-19
**Basé sur** : k2-fsa OmniVoice 0.5B/1.7B via OmniVoice 0.9.x
