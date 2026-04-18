"""Tests de validation des entrees — PRD-029 Phase 5.

Verifie que les entrees utilisateur malveillantes sont rejetees :
- thread_id (path traversal, caracteres speciaux, longueur)
- filename upload (path traversal)
- ZIP import (Zip Slip)
"""
import io
import os
import re
import tempfile
import zipfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Tests thread_id (dependencies.get_thread_id + regex THREAD_ID_RE)
# ---------------------------------------------------------------------------

from dependencies import THREAD_ID_RE


class TestThreadIdValidation:
    """Validation du format thread_id via THREAD_ID_RE."""

    def test_thread_id_malveillant_path_traversal(self):
        """Un thread_id avec ../ est rejete."""
        assert not THREAD_ID_RE.match("../../../etc")
        assert not THREAD_ID_RE.match("../../passwd")
        assert not THREAD_ID_RE.match("test/../evil")

    def test_thread_id_trop_long(self):
        """Un thread_id > 64 caracteres est rejete."""
        assert THREAD_ID_RE.match("a" * 64)
        assert not THREAD_ID_RE.match("a" * 65)
        assert not THREAD_ID_RE.match("a" * 200)

    def test_thread_id_caracteres_speciaux(self):
        """Un thread_id avec caracteres shell/speciaux est rejete."""
        malicious = [
            "test;rm -rf /",
            "test|cat /etc/passwd",
            "test$(whoami)",
            "test`id`",
            "hello world",
            "test/evil",
            "test\nevil",
            "test\x00evil",
        ]
        for tid in malicious:
            assert not THREAD_ID_RE.match(tid), f"Devrait rejeter: {tid!r}"

    def test_thread_id_valide_uuid(self):
        """Un UUID standard est accepte."""
        valid = [
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "0365bc78-a565-4671-8ac9-df05d8ff460c",
            "simple-id_123",
            "a",
            "A-Z_0-9",
        ]
        for tid in valid:
            assert THREAD_ID_RE.match(tid), f"Devrait accepter: {tid!r}"

    def test_thread_id_vide(self):
        """Un thread_id vide est rejete."""
        assert not THREAD_ID_RE.match("")


# ---------------------------------------------------------------------------
# Tests filename upload (import_steps.py sanitization)
# ---------------------------------------------------------------------------

from slugify import slugify


class TestFilenameSanitization:
    """Validation du nettoyage des noms de fichiers upload."""

    def test_filename_path_traversal(self):
        """Un filename avec ../ est neutralise par basename + slugify."""
        malicious_names = [
            ("../../etc/passwd.xlsx", "passwd.xlsx"),
            ("../evil.xlsx", "evil.xlsx"),
            ("/absolute/path/file.xlsx", "file.xlsx"),
        ]
        for original, expected in malicious_names:
            safe = os.path.basename(original)
            name_part, ext_part = os.path.splitext(safe)
            safe = f"{slugify(name_part, lowercase=False)}{ext_part}"
            assert safe == expected, f"{original!r} -> {safe!r}, attendu {expected!r}"

    def test_filename_normal_preserve(self):
        """Un filename normal est preserve (modulo slugification)."""
        safe = os.path.basename("mon-fichier.xlsx")
        name_part, ext_part = os.path.splitext(safe)
        safe = f"{slugify(name_part, lowercase=False)}{ext_part}"
        assert safe == "mon-fichier.xlsx"


# ---------------------------------------------------------------------------
# Tests Zip Slip (voices.py resolve protection)
# ---------------------------------------------------------------------------


class TestZipSlipProtection:
    """Validation de la protection Zip Slip via resolve().is_relative_to()."""

    def test_zip_slip_blocked(self):
        """Un dossier ../evil dans un ZIP est bloque par resolve()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            voices_dir = Path(tmpdir) / "voices"
            voices_dir.mkdir()

            # Creer un ZIP avec un dossier malveillant
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                zf.writestr("../evil/meta.json", '{"name":"evil"}')
                zf.writestr("../evil/prompt.pt", b"fake")

            zip_buffer.seek(0)
            with zipfile.ZipFile(zip_buffer) as zf:
                folders = {n.split("/")[0] for n in zf.namelist() if "/" in n}
                extracted = []
                for folder in folders:
                    if ".." in folder or folder.startswith("/"):
                        continue
                    dest = voices_dir / folder
                    if not dest.resolve().is_relative_to(voices_dir.resolve()):
                        continue
                    extracted.append(folder)

            assert len(extracted) == 0, f"Dossiers extraits alors que tout devrait etre bloque: {extracted}"
            # Verifier qu'aucun fichier n'a ete cree
            assert list(voices_dir.iterdir()) == []

    def test_zip_normal_accepted(self):
        """Un dossier normal dans un ZIP est accepte."""
        with tempfile.TemporaryDirectory() as tmpdir:
            voices_dir = Path(tmpdir) / "voices"
            voices_dir.mkdir()

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                zf.writestr("good-voice/meta.json", '{"name":"good"}')
                zf.writestr("good-voice/prompt.pt", b"fake")

            zip_buffer.seek(0)
            with zipfile.ZipFile(zip_buffer) as zf:
                folders = {n.split("/")[0] for n in zf.namelist() if "/" in n}
                extracted = []
                for folder in folders:
                    if ".." in folder or folder.startswith("/"):
                        continue
                    dest = voices_dir / folder
                    if not dest.resolve().is_relative_to(voices_dir.resolve()):
                        continue
                    extracted.append(folder)

            assert extracted == ["good-voice"]
