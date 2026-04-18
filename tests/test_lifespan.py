"""Tests des fonctions lifespan (purge, quota) — PRD-029."""
import os
import time
import logging
import pytest


class TestPurgeStaleExports:
    """Tests de _purge_stale_exports()."""

    def test_removes_old_zips(self, tmp_path, monkeypatch):
        """Les ZIP de plus de 72h sont supprimés."""
        monkeypatch.chdir(tmp_path)
        export_dir = tmp_path / "export"
        export_dir.mkdir()

        # Créer un vieux ZIP (> 72h)
        old_zip = export_dir / "old_export.zip"
        old_zip.write_text("fake")
        old_time = time.time() - (73 * 3600)
        os.utime(old_zip, (old_time, old_time))

        # Créer un ZIP récent
        new_zip = export_dir / "new_export.zip"
        new_zip.write_text("fake")

        from dependencies import _purge_stale_exports
        _purge_stale_exports(max_age_hours=72)

        assert not old_zip.exists()
        assert new_zip.exists()

    def test_no_crash_if_dir_missing(self, tmp_path, monkeypatch):
        """Pas d'erreur si export/ n'existe pas."""
        monkeypatch.chdir(tmp_path)
        from dependencies import _purge_stale_exports
        _purge_stale_exports()  # Ne doit pas crasher

    def test_ignores_non_zip_files(self, tmp_path, monkeypatch):
        """Les fichiers non-ZIP ne sont pas supprimés."""
        monkeypatch.chdir(tmp_path)
        export_dir = tmp_path / "export"
        export_dir.mkdir()
        txt_file = export_dir / "readme.txt"
        txt_file.write_text("keep me")
        old_time = time.time() - (100 * 3600)
        os.utime(txt_file, (old_time, old_time))

        from dependencies import _purge_stale_exports
        _purge_stale_exports(max_age_hours=72)

        assert txt_file.exists()


class TestCheckDiskQuota:
    """Tests de _check_disk_quota()."""

    def test_no_crash_if_dir_missing(self, tmp_path, monkeypatch):
        """Pas d'erreur si data/voices/ n'existe pas."""
        monkeypatch.chdir(tmp_path)
        from dependencies import _check_disk_quota
        _check_disk_quota()

    def test_logs_warning_over_quota(self, tmp_path, monkeypatch, caplog):
        """Warning si l'espace dépasse le seuil."""
        monkeypatch.chdir(tmp_path)
        voices_dir = tmp_path / "data" / "voices"
        voices_dir.mkdir(parents=True)
        (voices_dir / "big.wav").write_bytes(b"\x00" * 2048)

        from dependencies import _check_disk_quota
        with caplog.at_level(logging.WARNING):
            _check_disk_quota(warn_gb=0)  # Seuil 0 → toujours warning

        assert any("Espace audio" in m and "Purge" in m for m in caplog.messages)

    def test_logs_info_under_quota(self, tmp_path, monkeypatch, caplog):
        """Info si l'espace est sous le seuil."""
        monkeypatch.chdir(tmp_path)
        voices_dir = tmp_path / "data" / "voices"
        voices_dir.mkdir(parents=True)
        (voices_dir / "small.wav").write_bytes(b"\x00" * 100)

        from dependencies import _check_disk_quota
        with caplog.at_level(logging.INFO):
            _check_disk_quota(warn_gb=10)

        assert any("Espace audio" in m for m in caplog.messages)
