"""Tests for cli.folderback module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pyflowx as px
from pyflowx.cli import folderback


# ---------------------------------------------------------------------- #
# backup_folder
# ---------------------------------------------------------------------- #
class TestBackupFolder:
    """Test backup_folder function."""

    def test_backup_folder_with_source_and_backup(self, tmp_path: Path) -> None:
        """Should backup folder with source and backup paths."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "test.txt").write_text("test content")
        backup_dir = tmp_path / "backup"

        with patch.object(folderback, "zip_target") as mock_zip:
            folderback.backup_folder(str(source_dir), str(backup_dir), 5)
            assert mock_zip.called

    def test_backup_folder_with_max_backups(self, tmp_path: Path) -> None:
        """Should backup folder with max backups."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "test.txt").write_text("test content")
        backup_dir = tmp_path / "backup"

        with patch.object(folderback, "zip_target") as mock_zip:
            folderback.backup_folder(str(source_dir), str(backup_dir), 10)
            assert mock_zip.called

    def test_backup_folder_source_not_exists(self, tmp_path: Path) -> None:
        """Should handle non-existent source folder."""
        source_dir = tmp_path / "nonexistent"
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        folderback.backup_folder(str(source_dir), str(backup_dir), 5)
        # Should print error message and return


# ---------------------------------------------------------------------- #
# TaskSpec definitions
# ---------------------------------------------------------------------- #
class TestTaskSpecDefinitions:
    """Test that all TaskSpec definitions are valid."""

    def test_folderback_default_spec(self) -> None:
        """folderback_default spec should be properly defined."""
        assert folderback.folderback_default.name == "folderback_default"
        assert folderback.folderback_default.fn is not None


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_calls_run_cli(self) -> None:
        """main() should create a CliRunner and call run_cli()."""
        with patch.object(px.CliRunner, "run_cli") as mock_run_cli:
            folderback.main()
            assert mock_run_cli.called
