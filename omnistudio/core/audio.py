import logging
import subprocess
import os
import shutil
import tempfile
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

def change_speed(input_path: str, speed: float) -> bool:
    """Change la vitesse d'un fichier audio via SoX tempo (sans changer le pitch)."""
    if not speed or speed == 1.0:
        return True
    import uuid as _uuid
    tmp_path = input_path + f".tmp.{_uuid.uuid4().hex[:8]}.wav"
    try:
        subprocess.run(
            ["sox", input_path, tmp_path, "tempo", str(speed)],
            check=True, capture_output=True
        )
        shutil.move(tmp_path, input_path)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", input_path, "-af", f"atempo={speed}", tmp_path],
                check=True, capture_output=True
            )
            shutil.move(tmp_path, input_path)
            return True
        except Exception as e:
            logger.error("Erreur change_speed fallback FFmpeg: %s", e)
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            return False


def process_audio(input_path: str, output_path: str, config: dict):
    """Post-traitement audio SoX/FFmpeg."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        cmd = ["sox", input_path, output_path]
        if config.get("normalize"): cmd.extend(["gain", "-n", "-3"])
        if config.get("stereo"): cmd.extend(["channels", "2"])
        if config.get("rate"): cmd.extend(["rate", str(config["rate"])])
        bd = config.get("bit_depth")
        if bd in (16, 24, 32): cmd.extend(["-b", str(bd)])
        if config.get("speed") and config["speed"] != 1.0: cmd.extend(["tempo", str(config["speed"])])
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            cmd = ["ffmpeg", "-y", "-i", input_path]
            filters = []
            if config.get("normalize"): filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
            if filters: cmd.extend(["-af", ",".join(filters)])
            if config.get("stereo"): cmd.extend(["-ac", "2"])
            if config.get("rate"): cmd.extend(["-ar", str(config["rate"])])
            bd = config.get("bit_depth")
            if bd == 16: cmd.extend(["-sample_fmt", "s16"])
            elif bd == 24: cmd.extend(["-sample_fmt", "s24"])
            elif bd == 32: cmd.extend(["-sample_fmt", "s32"])
            cmd.append(output_path)
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except Exception as e:
            logger.error("Erreur process_audio fallback copie: %s", e)
            try:
                if os.path.exists(input_path):
                    shutil.copy(input_path, output_path)
            except Exception as copy_err:
                logger.error("Erreur lors de la copie de secours: %s", copy_err)
            return False

def convert_to_mp3(input_path: str, output_path: str, bitrate: str = "192k") -> bool:
    """Convertit un fichier WAV en MP3 via SoX ou FFmpeg."""
    if not os.path.exists(input_path):
        return False
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    try:
        subprocess.run(
            ["sox", input_path, "-C", bitrate.replace("k", ""), output_path],
            check=True, capture_output=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", input_path, "-codec:a", "libmp3lame",
                 "-b:a", bitrate, output_path],
                check=True, capture_output=True
            )
            return True
        except Exception as e:
            logger.error("Erreur convert_to_mp3: %s", e)
            return False


def concatenate_audio(file_paths: List[str], output_path: str, silence_duration: float = 1.0, config: dict = None):
    """Concatène avec silences alignés sur la config utilisateur."""
    if not file_paths: return False
    config = config or {"rate": 48000, "stereo": True}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        silence_file = os.path.join(tmpdir, "silence.wav")
        try:
            # 1. Créer silence avec les bons paramètres
            channels = "2" if config.get("stereo") else "1"
            rate = str(config.get("rate", 48000))
            
            # Création via SoX
            try:
                subprocess.run([
                    "sox", "-n", "-r", rate, "-c", channels, silence_file, 
                    "trim", "0.0", str(silence_duration)
                ], check=True, capture_output=True)
            except Exception:
                # Fallback FFmpeg pour le silence
                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={rate}:cl={'stereo' if channels=='2' else 'mono'}", 
                    "-t", str(silence_duration), silence_file
                ], check=True, capture_output=True)

            # 2. Concaténation SoX
            cmd = ["sox"]
            for i, path in enumerate(file_paths):
                cmd.append(path)
                if i < len(file_paths) - 1: cmd.append(silence_file)
            cmd.append(output_path)
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except Exception as e:
            logger.error("Erreur concat: %s", e)
            # Fallback FFmpeg concat simple
            list_path = os.path.join(tmpdir, "list.txt")
            try:
                with open(list_path, "w") as f:
                    for p in file_paths: f.write(f"file '{os.path.abspath(p)}'\n")
                subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path], check=True, capture_output=True)
                return True
            except Exception as e:
                logger.error("Erreur concatenate_audio fallback FFmpeg: %s", e)
                try:
                    if os.path.exists(list_path):
                        os.unlink(list_path)
                except Exception:
                    pass
                return False
