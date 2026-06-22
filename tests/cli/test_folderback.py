"""Tests for cli.folderback module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

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
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        with patch("shutil.copytree") as mock_copy:
            folderback.backup_folder(str(source_dir), str(backup_dir), 5)
            assert mock_copy.called

    def test_backup_folder_with_max_backups(self, tmp_path: Path) -> None:
        """Should backup folder with max backups."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        with patch("shutil.copytree") as mock_copy:
            folderback.backup_folder(str(source_dir), str(backup_dir), 10)
            assert mock_copy.called


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
        with pytest.raises(SystemExit) as exc_info:
            folderback.main()
        # run_cli() calls sys.exit(), so we should get SystemExit
        assert exc_info.value.code in (0, 1, 2)

    def test_main_with_list_argument(self) -> None:
        """main() should handle --list argument."""
        with patch("sys.argv", ["folderback", "--list"]), pytest.raises(SystemExit) as exc_info:
            folderback.main()
        assert exc_info.value.code == 0

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["folderback"]), pytest.raises(SystemExit) as exc_info:
            folderback.main()
        assert exc_info.value.code == 1