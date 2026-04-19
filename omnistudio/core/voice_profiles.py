"""VOICE_TEMPLATES — 12 profils de voix prédéfinis, format OmniVoice (EN).

PRD-MIGRATION-001 v1.5 décision 10 : 12 templates au format whitelist
OmniVoice (items séparés par virgules, 1 par catégorie : gender, age,
pitch, style, accent). Ces templates évitent le passage par un LLM
(Albert) pour les cas courants — le voice_instruct est directement
accepté par POST /design.

Catégories OmniVoice valides (cf. GET /design/attributes) :
- gender     : male, female
- age        : child, teenager, young adult, middle-aged, elderly
- pitch      : very low pitch, low pitch, moderate pitch, high pitch, very high pitch
- style      : whisper
- english_accent : American/Australian/British/Canadian/Chinese/Indian/
                   Japanese/Korean/Portuguese/Russian accent
"""
from typing import List, Dict

VOICE_TEMPLATES: List[Dict] = [
    {
        "name": "Narrateur institutionnel",
        "badge": "Institution",
        "gender": "male",
        "description": "Voix masculine grave et posée, pour discours officiels.",
        "voice_instruct": "male, middle-aged, low pitch",
    },
    {
        "name": "Narratrice pédagogique",
        "badge": "Formation",
        "gender": "female",
        "description": "Voix féminine chaleureuse, idéale e-learning et tutoriels.",
        "voice_instruct": "female, middle-aged, moderate pitch",
    },
    {
        "name": "Narrateur dynamique",
        "badge": "Promo",
        "gender": "male",
        "description": "Voix masculine jeune et énergique, promo et réseaux.",
        "voice_instruct": "male, young adult, moderate pitch",
    },
    {
        "name": "Narratrice claire",
        "badge": "Service",
        "gender": "female",
        "description": "Voix féminine neutre et factuelle, annonces de service.",
        "voice_instruct": "female, young adult, moderate pitch",
    },
    {
        "name": "Narrateur chaleureux",
        "badge": "Accompagnement",
        "gender": "male",
        "description": "Voix masculine rassurante pour sujets sensibles.",
        "voice_instruct": "male, middle-aged, moderate pitch",
    },
    {
        "name": "Narratrice experte",
        "badge": "Expert",
        "gender": "female",
        "description": "Voix féminine confiante et didactique, formations avancées.",
        "voice_instruct": "female, elderly, low pitch",
    },
    {
        "name": "Jeune narrateur",
        "badge": "Jeunesse",
        "gender": "male",
        "description": "Voix masculine jeune et pétillante, contenu fun et jeunesse.",
        "voice_instruct": "male, young adult, high pitch",
    },
    {
        "name": "Jeune narratrice",
        "badge": "Jeunesse",
        "gender": "female",
        "description": "Voix féminine jeune et dynamique, contenus ludiques.",
        "voice_instruct": "female, young adult, high pitch",
    },
    {
        "name": "Narrateur senior",
        "badge": "Senior",
        "gender": "male",
        "description": "Voix masculine âgée et posée, récits et mémoires.",
        "voice_instruct": "male, elderly, low pitch",
    },
    {
        "name": "Narratrice senior",
        "badge": "Senior",
        "gender": "female",
        "description": "Voix féminine âgée et veloutée, narration patrimoniale.",
        "voice_instruct": "female, elderly, moderate pitch",
    },
    {
        "name": "Narration confidentielle",
        "badge": "Chuchoté",
        "gender": "female",
        "description": "Voix féminine chuchotée, pour contenus intimistes et ASMR.",
        "voice_instruct": "female, middle-aged, moderate pitch, whisper",
    },
    {
        "name": "Narrateur anglophone",
        "badge": "Accent EN",
        "gender": "male",
        "description": "Voix masculine à accent britannique, contenu international.",
        "voice_instruct": "male, middle-aged, low pitch, British accent",
    },
]
