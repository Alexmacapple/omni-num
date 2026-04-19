import logging
import httpx
import os
import re
import zipfile
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class OmniVoiceBusyError(Exception):
    """Le moteur TTS est occupé (503)."""
    pass

class OmniVoiceTimeoutError(Exception):
    """La génération a dépassé le timeout (504 ou httpx.ReadTimeout)."""
    pass


# OmniVoice k2-fsa : items valides par catégorie (1 item max par catégorie).
# Cf. erreur 500 de /design qui liste les items non supportés.
_OMNIVOICE_VALID_ITEMS = {
    "american accent", "australian accent", "british accent", "canadian accent",
    "chinese accent", "indian accent", "japanese accent", "korean accent",
    "portuguese accent", "russian accent",
    "child", "teenager", "young adult", "middle-aged", "elderly",
    "female", "male",
    "very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch",
    "whisper",
}

# Catégories exclusives (1 item par catégorie sinon 500 "Conflicting")
_CATEGORIES = {
    "gender": {"male", "female"},
    "age": {"child", "teenager", "young adult", "middle-aged", "elderly"},
    "pitch": {"very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch"},
    "accent": {"american accent", "australian accent", "british accent", "canadian accent",
               "chinese accent", "indian accent", "japanese accent", "korean accent",
               "portuguese accent", "russian accent"},
    "special": {"whisper"},
}

# Mapping keyword → item whitelist (permet d'accepter un prompt prose).
# Mots NON ambigus uniquement : "moderate"/"high"/"low" seul exclus car peut
# qualifier autre chose que le pitch (moderate pace, high energy, etc.).
_KEYWORD_TO_ITEM = {
    # genre
    "male": "male", "man": "male", "masculine": "male", "masculin": "male", "masculine voice": "male", "male voice": "male",
    "female": "female", "woman": "female", "feminine": "female", "féminin": "female", "feminin": "female", "féminine": "female", "feminine voice": "female", "female voice": "female",
    # âge
    "child": "child", "kid": "child", "enfant": "child",
    "teenager": "teenager", "teen": "teenager", "adolescent": "teenager",
    "young adult": "young adult", "young": "young adult", "jeune": "young adult",
    "middle-aged": "middle-aged", "middle aged": "middle-aged", "mature": "middle-aged", "adult": "middle-aged",
    "elderly": "elderly", "senior": "elderly", "aged": "elderly", "âgé": "elderly", "old voice": "elderly",
    # pitch (phrases explicites + synonymes non ambigus)
    "very low pitch": "very low pitch", "very deep": "very low pitch",
    "low pitch": "low pitch", "deep voice": "low pitch", "deep": "low pitch", "grave": "low pitch", "bass": "low pitch", "cavernous": "low pitch",
    "moderate pitch": "moderate pitch", "médium": "moderate pitch", "medium pitch": "moderate pitch",
    "high pitch": "high pitch", "aigu": "high pitch", "high-pitched": "high pitch",
    "very high pitch": "very high pitch",
    # accent (on évite de matcher seulement "french" etc. qui qualifie souvent la langue)
    "american accent": "american accent",
    "british accent": "british accent",
    "australian accent": "australian accent",
    "canadian accent": "canadian accent",
    "chinese accent": "chinese accent",
    "indian accent": "indian accent",
    "japanese accent": "japanese accent",
    "korean accent": "korean accent",
    "portuguese accent": "portuguese accent",
    "russian accent": "russian accent",
    # special
    "whisper": "whisper", "whispered": "whisper", "chuchoté": "whisper",
}


def normalize_voice_instruct(raw: str) -> str:
    """Convertit un voice_instruct libre en items whitelist OmniVoice.

    Accepte :
    - Format déjà valide : "male, middle-aged, low pitch" → retourné tel quel
    - Prompt prose EN/FR : "Deep mature French male voice, calm authority" →
      "male, middle-aged, low pitch"

    Règle : 1 item max par catégorie (gender, age, pitch, accent, special).
    Le premier match par catégorie gagne (ordre de lecture).
    """
    if not raw:
        return ""
    lowered = raw.lower().strip()

    # Court-circuit : si tous les items sont déjà valides, on garde
    raw_items = [it.strip() for it in lowered.split(",") if it.strip()]
    if raw_items and all(it in _OMNIVOICE_VALID_ITEMS for it in raw_items):
        # Dédup + 1 par catégorie
        return _dedupe_by_category(raw_items)

    # Extraction keyword : balayage des mappings, 1 par catégorie
    seen_categories: Dict[str, str] = {}
    # Tri par longueur décroissante pour matcher "young adult" avant "young"
    sorted_keys = sorted(_KEYWORD_TO_ITEM.keys(), key=len, reverse=True)
    for kw in sorted_keys:
        if not _word_match(lowered, kw):
            continue
        item = _KEYWORD_TO_ITEM[kw]
        cat = _category_of(item)
        if cat and cat not in seen_categories:
            seen_categories[cat] = item

    result = list(seen_categories.values())
    if not result:
        # Fallback minimal : gender neutral non supporté → on met rien
        logger.warning("normalize_voice_instruct: aucun keyword reconnu dans '%s'", raw[:80])
        return ""
    return ", ".join(result)


def _word_match(text: str, keyword: str) -> bool:
    """Match mot entier ou sous-expression (pas de substring à l'intérieur d'un mot)."""
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return re.search(pattern, text) is not None


def _category_of(item: str) -> Optional[str]:
    for cat, items in _CATEGORIES.items():
        if item in items:
            return cat
    return None


def _dedupe_by_category(items: List[str]) -> str:
    """Garde le premier item de chaque catégorie."""
    seen: Dict[str, str] = {}
    for it in items:
        cat = _category_of(it)
        if cat and cat not in seen:
            seen[cat] = it
    return ", ".join(seen.values())


class OmniVoiceClient:
    """Client pour l'API OmniVoice (k2-fsa OmniVoice)."""

    def __init__(self, base_url: str = "http://localhost:8070"):
        self.base_url = base_url.rstrip("/")
        # Timeouts httpx différenciés par catégorie
        # REGLE : timeout httpx > timeout OmniVoice (semaphore) pour chaque catégorie
        self.timeout_admin = float(os.getenv("OMNISTUDIO_TIMEOUT_ADMIN", "10"))
        self.timeout_preview = float(os.getenv("OMNISTUDIO_TIMEOUT_PREVIEW", "90"))
        self.timeout_generate = float(os.getenv("OMNISTUDIO_TIMEOUT_GENERATE", "120"))
        self.timeout_batch = float(os.getenv("OMNISTUDIO_TIMEOUT_BATCH", "600"))

    def _check_tts_error(self, response: httpx.Response):
        """Lève une exception typée si OmniVoice retourne 503 ou 504."""
        if response.status_code == 503:
            raise OmniVoiceBusyError("Moteur TTS occupé")
        if response.status_code == 504:
            raise OmniVoiceTimeoutError("Génération timeout côté OmniVoice")

    def health_check(self) -> bool:
        """Vérifie si l'API est joignable."""
        try:
            response = httpx.get(f"{self.base_url}/", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    def get_voices(self) -> List[Dict]:
        """Récupère la liste des voix."""
        try:
            response = httpx.get(f"{self.base_url}/voices", timeout=self.timeout_admin)
            if response.status_code == 200:
                return response.json().get("voices", [])
            return []
        except Exception as e:
            logger.error("Erreur get_voices: %s", e)
            return []

    def get_custom_voice_details(self, name: str) -> Optional[Dict]:
        """Détails d'une voix custom."""
        try:
            response = httpx.get(f"{self.base_url}/voices/custom/{name}", timeout=self.timeout_admin)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def delete_custom_voice(self, name: str) -> bool:
        """Supprime une voix custom."""
        try:
            response = httpx.delete(f"{self.base_url}/voices/custom/{name}", timeout=self.timeout_admin)
            return response.status_code == 200
        except Exception:
            return False

    def reload_custom_voices(self) -> bool:
        """Force OmniVoice à rescanner les voix custom depuis le disque."""
        try:
            response = httpx.post(f"{self.base_url}/voices/reload", timeout=10.0)
            return response.status_code == 200
        except Exception:
            return False

    def preload_models(
        self,
        design: bool = True,
        clone: bool = False,
        preset: bool = True,
        clone_1_7b: bool = True,
        clone_0_6b: bool = False,
    ) -> bool:
        """Pré-charge les modèles côté serveur."""
        try:
            params = {
                "design": design,
                "clone": clone,
                "preset": preset,
                "clone_1_7b": clone_1_7b,
                "clone_0_6b": clone_0_6b,
            }
            response = httpx.post(f"{self.base_url}/models/preload", params=params, timeout=self.timeout_batch)
            return response.status_code == 200
        except Exception:
            return False

    def get_languages(self) -> List[str]:
        """Récupère les langues supportées."""
        try:
            response = httpx.get(f"{self.base_url}/languages", timeout=self.timeout_admin)
            if response.status_code == 200:
                return response.json().get("languages", ["fr", "en", "zh", "jp", "ko"])
            return ["fr", "en"]
        except Exception:
            return ["fr", "en"]

    def get_models_status(self) -> Optional[Dict]:
        """Récupère l'état des modèles chargés."""
        try:
            response = httpx.get(f"{self.base_url}/models/status", timeout=5.0)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def estimate_duration(self, texts: List[str]) -> float:
        """Estime la durée totale via le tokenizer."""
        try:
            if not texts:
                return 0.0
            full_text = " ".join(texts)
            if not full_text.strip():
                return 0.0
            response = httpx.post(f"{self.base_url}/tokenizer/encode", json={"text": full_text}, timeout=self.timeout_admin)
            if response.status_code == 200:
                tokens = response.json().get("tokens", [])
                # Formule empirique : 1 token ≈ 0.05 seconde
                return max(0.0, len(tokens) * 0.05)
            return max(0.0, len(full_text) * 0.01) # Fallback
        except Exception:
            return 0.0

    def preset(self, text: str, voice: str, language: str = "fr",
               model: str = "1.7B", output_dir: str = "temp", speed: Optional[float] = None,
               timeout: Optional[float] = None) -> Optional[str]:
        """Génère un audio avec choix du modèle (fidelity)."""
        os.makedirs(output_dir, exist_ok=True)
        t = timeout or self.timeout_generate
        try:
            data = {
                "text": text,
                "voice": voice,
                "language": language,
                "model": model
            }
            if speed and speed != 1.0:
                data["speed"] = speed
            response = httpx.post(f"{self.base_url}/preset", data=data, timeout=t)
            self._check_tts_error(response)
            if response.status_code == 200:
                filename = f"step_{hash(text + voice + model) % 10000}.wav"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return filepath
            return None
        except (OmniVoiceBusyError, OmniVoiceTimeoutError):
            raise
        except httpx.ReadTimeout:
            raise OmniVoiceTimeoutError(f"Timeout httpx ({t}s) sur /preset")
        except Exception as e:
            logger.error("Erreur preset: %s", e)
            return None

    def preset_instruct(self, text: str, voice: str, instruct: str, language: str = "fr",
                        model: str = "1.7B", output_dir: str = "temp", speed: Optional[float] = None,
                        timeout: Optional[float] = None) -> Optional[str]:
        """Génère un audio avec instruction émotionnelle (/preset/instruct)."""
        os.makedirs(output_dir, exist_ok=True)
        t = timeout or self.timeout_generate
        try:
            data = {
                "text": text,
                "voice": voice,
                "instruct": instruct,
                "language": language,
                "model": model
            }
            if speed and speed != 1.0:
                data["speed"] = speed
            response = httpx.post(f"{self.base_url}/preset/instruct", data=data, timeout=t)
            self._check_tts_error(response)
            if response.status_code == 200:
                filename = f"step_{hash(text + voice + instruct + model) % 10000}.wav"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return filepath
            return None
        except (OmniVoiceBusyError, OmniVoiceTimeoutError):
            raise
        except httpx.ReadTimeout:
            raise OmniVoiceTimeoutError(f"Timeout httpx ({t}s) sur /preset/instruct")
        except Exception as e:
            logger.error("Erreur preset_instruct: %s", e)
            return None

    def batch_preset(self, texts: List[str], voice: str, language: str = "fr",
                     model: str = "1.7B", output_dir: str = "temp", prefix: str = "batch",
                     speed: Optional[float] = None,
                     advanced: Optional[Dict] = None) -> List[str]:
        """Génère un lot via l'API batch et extrait les WAV (ordre du ZIP).

        `advanced` : dict optionnel de paramètres OmniVoice avancés (PRD v1.5
        décision 14). Clés acceptées : num_step, speed, t_shift,
        position_temperature, class_temperature, layer_penalty_factor,
        audio_chunk_duration, audio_chunk_threshold, denoise, postprocess_output.
        Les valeurs None sont ignorées (OmniVoice applique ses défauts).
        """
        os.makedirs(output_dir, exist_ok=True)
        try:
            data = {
                "texts": texts,
                "voice": voice,
                "language": language,
                "model": model
            }
            if speed and speed != 1.0:
                data["speed"] = speed
            if advanced:
                # Whitelist des clés OmniVoice acceptées par /batch/preset (pas de guidance_scale ici)
                allowed = {"num_step", "speed", "t_shift", "position_temperature",
                           "class_temperature", "layer_penalty_factor",
                           "audio_chunk_duration", "audio_chunk_threshold",
                           "denoise", "postprocess_output"}
                for k, v in advanced.items():
                    if v is not None and k in allowed:
                        data[k] = v
            response = httpx.post(f"{self.base_url}/batch/preset", json=data, timeout=self.timeout_batch)
            self._check_tts_error(response)
            if response.status_code != 200:
                logger.warning("batch_preset HTTP %d pour voix '%s': %s", response.status_code, voice, response.text[:300])
                return []
            zip_path = os.path.join(output_dir, f"{prefix}.zip")
            with open(zip_path, "wb") as f:
                f.write(response.content)

            extracted = []
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".wav")]
                names.sort()
                for idx, name in enumerate(names, start=1):
                    target_name = f"{prefix}_{idx:03d}.wav"
                    target_path = os.path.join(output_dir, target_name)
                    with zf.open(name) as src, open(target_path, "wb") as dst:
                        dst.write(src.read())
                    extracted.append(target_path)
            return extracted
        except (OmniVoiceBusyError, OmniVoiceTimeoutError):
            raise
        except httpx.ReadTimeout:
            raise OmniVoiceTimeoutError(f"Timeout httpx ({self.timeout_batch}s) sur /batch/preset")
        except Exception as e:
            logger.error("Erreur batch_preset: %s", e)
            return []

    def design(self, text: str, voice_instruct: str, language: str = "fr",
               output_dir: str = "temp", timeout: Optional[float] = None) -> Optional[str]:
        os.makedirs(output_dir, exist_ok=True)
        t = timeout or self.timeout_generate
        # Normalise voice_instruct vers items whitelist OmniVoice
        # (accepte prompt prose EN/FR → items valides, 1 par catégorie)
        normalized_instruct = normalize_voice_instruct(voice_instruct)
        if not normalized_instruct:
            logger.error("design: voice_instruct '%s' n'a produit aucun item valide", voice_instruct[:80])
            return None
        if normalized_instruct != voice_instruct.strip():
            logger.info("design: voice_instruct normalisé '%s' → '%s'",
                        voice_instruct[:60], normalized_instruct)
        try:
            data = {
                "text": text,
                "voice_instruct": normalized_instruct,
                "language": language
            }
            # OmniVoice /design attend un body JSON (pas form-encoded comme /preset)
            response = httpx.post(f"{self.base_url}/design", json=data, timeout=t)
            self._check_tts_error(response)
            if response.status_code == 200:
                filepath = os.path.join(output_dir, f"design_{hash(voice_instruct)%1000}.wav")
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return filepath
            return None
        except (OmniVoiceBusyError, OmniVoiceTimeoutError):
            raise
        except httpx.ReadTimeout:
            raise OmniVoiceTimeoutError(f"Timeout httpx ({t}s) sur /design")
        except Exception as e:
            logger.error("Erreur design: %s", e)
            return None

    def save_custom_voice(self, name: str, source: str, voice_instruct: str = "",
                          audio_path: str = "", transcription: str = "",
                          model: str = "1.7B", language: str = "fr") -> dict:
        """Sauvegarde une voix custom. Retourne {"ok": bool, "detail": str}."""
        audio_file = None
        try:
            data = {"name": name, "source": source, "model": model, "language": language}
            files = {}
            if source == "design":
                # Normalise vers items whitelist pour que /preset sur cette voix fonctionne
                normalized = normalize_voice_instruct(voice_instruct)
                if not normalized:
                    return {"ok": False, "detail": f"voice_instruct '{voice_instruct[:60]}' ne contient aucun item reconnu par OmniVoice"}
                if normalized != voice_instruct.strip():
                    logger.info("save_custom_voice: voice_instruct normalisé '%s' → '%s'",
                                voice_instruct[:60], normalized)
                data["voice_description"] = normalized
            elif source == "clone":
                audio_file = open(audio_path, "rb")
                files["reference_audio"] = audio_file
                data["reference_text"] = transcription

            response = httpx.post(
                f"{self.base_url}/voices/custom",
                data=data,
                files=files if files else None,
                timeout=self.timeout_generate
            )
            if response.status_code in (200, 201):
                return {"ok": True, "detail": response.text}
            return {"ok": False, "detail": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}
        finally:
            if audio_file:
                try:
                    audio_file.close()
                except Exception:
                    pass

    # =========================================================================
    # Méthodes spécifiques OmniVoice (nouveautés omni-num, PRD v1.5)
    # =========================================================================

    def transcribe_audio(self, audio_path: str, language: str = "auto") -> Optional[str]:
        """Appel POST /transcribe (Whisper intégré OmniVoice). Retourne le texte ou None."""
        try:
            with open(audio_path, "rb") as f:
                files = {"audio": f}
                data = {"language": language}
                response = httpx.post(
                    f"{self.base_url}/transcribe",
                    files=files,
                    data=data,
                    timeout=self.timeout_generate,
                )
                if response.status_code == 200:
                    return response.json().get("text", "")
                return None
        except Exception as e:
            logger.error("Erreur transcribe_audio: %s", e)
            return None

    def get_tags(self) -> List[str]:
        """Récupère la liste des 13 tags émotionnels non-verbaux (GET /tags)."""
        try:
            response = httpx.get(f"{self.base_url}/tags", timeout=self.timeout_admin)
            if response.status_code == 200:
                return response.json().get("tags", [])
            return []
        except Exception:
            return []

    def get_design_attributes(self) -> Dict:
        """Récupère les attributs Voice Design (GET /design/attributes) pour peupler les selects."""
        try:
            response = httpx.get(f"{self.base_url}/design/attributes", timeout=self.timeout_admin)
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception:
            return {}

    def random_auto(self, text: str, language: str = "auto", output_dir: str = "temp") -> Optional[str]:
        """Appel POST /auto (voix aléatoire cohérente). Retourne le chemin du WAV généré."""
        os.makedirs(output_dir, exist_ok=True)
        try:
            data = {"text": text, "language": language}
            response = httpx.post(f"{self.base_url}/auto", json=data, timeout=self.timeout_generate)
            self._check_tts_error(response)
            if response.status_code == 200:
                filepath = os.path.join(output_dir, f"random_{hash(text) % 10000}.wav")
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return filepath
            return None
        except (OmniVoiceBusyError, OmniVoiceTimeoutError):
            raise
        except Exception as e:
            logger.error("Erreur random_auto: %s", e)
            return None

    def preload_model(self) -> bool:
        """POST /models/preload — charge le modèle OmniVoice en VRAM au démarrage."""
        try:
            response = httpx.post(f"{self.base_url}/models/preload", timeout=120)
            return response.status_code == 200
        except Exception as e:
            logger.error("Erreur preload_model: %s", e)
            return False


# =============================================================================
# Helpers Voice Design étendu (6 catégories)
# =============================================================================

DIALECT_UI_TO_CHINESE = {
    "Henan": "河南话",
    "Shaanxi": "陕西话",
    "Sichuan": "四川话",
    "Guizhou": "贵州话",
    "Yunnan": "云南话",
    "Guilin": "桂林话",
    "Jinan": "济南话",
    "Shijiazhuang": "石家庄话",
    "Gansu": "甘肃话",
    "Ningxia": "宁夏话",
    "Qingdao": "青岛话",
    "Northeast": "东北话",
}


def map_dialect_to_chinese_chars(dialect: str) -> Optional[str]:
    """Convertit un nom de dialecte UI (anglais) en caractères chinois pour OmniVoice.

    Exemples:
        "Sichuan" → "四川话"
        "Inconnu" → None
    """
    return DIALECT_UI_TO_CHINESE.get(dialect)


def design_from_attributes(
    gender: str,
    age: str,
    pitch: str,
    style: str,
    language: str = "fr",
    accent: Optional[str] = None,
    dialect: Optional[str] = None,
    extra_en: str = "",
) -> str:
    """Compose la chaîne EN de description de voix depuis les selects Guidé.

    Règles (PRD v1.5 décision 12) :
    - Gender, Age, Pitch, Style : toujours inclus
    - English Accent : ajouté seulement si language == "en"
    - Chinese Dialect : converti en caractères chinois, ajouté seulement si language == "zh"
    - Style "Neutral" est omis (valeur par défaut OmniVoice)
    - extra_en : texte libre additionnel (mode Expert peut passer des nuances)

    Exemples:
        design_from_attributes("Female", "Young Adult", "High Pitch", "Neutral")
        → "female, young adult, high pitch"

        design_from_attributes("Female", "Middle-aged", "Moderate Pitch", "Neutral",
                               language="en", accent="British")
        → "female, middle-aged, moderate pitch, british accent"

        design_from_attributes("Male", "Middle-aged", "Moderate Pitch", "Neutral",
                               language="zh", dialect="Sichuan")
        → "male, middle-aged, moderate pitch, 四川话"
    """
    parts = []

    # Core 4 attributs (toujours)
    parts.append(gender.lower())
    parts.append(age.lower())
    parts.append(pitch.lower())
    if style and style.lower() != "neutral":
        parts.append(style.lower())

    # Accent anglais (conditionnel)
    if accent and language == "en":
        parts.append(f"{accent.lower()} accent")

    # Dialecte chinois (conditionnel + mapping caractères)
    if dialect and language == "zh":
        chinese_chars = map_dialect_to_chinese_chars(dialect)
        if chinese_chars:
            parts.append(chinese_chars)

    # Texte libre additionnel (mode Expert)
    if extra_en:
        parts.append(extra_en.strip())

    return ", ".join(parts)
