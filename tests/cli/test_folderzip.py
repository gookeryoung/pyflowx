"""Tests for cli.folderzip module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pyflowx as px
from pyflowx.cli import folderzip


# ---------------------------------------------------------------------- #
# archive_folder
# ---------------------------------------------------------------------- #
class TestArchiveFolder:
    """Test archive_folder function."""

    def test_archive_folder(self, tmp_path: Path) -> None:
        """Should archive a folder."""
        folder = tmp_path / "test_folder"
        folder.mkdir()
        (folder / "test.txt").write_text("test content")

        with patch("shutil.make_archive") as mock_archive:
            folderzip.archive_folder(folder)
            assert mock_archive.called


# ---------------------------------------------------------------------- #
# zip_folders
# ---------------------------------------------------------------------- #
class TestZipFolders:
    """Test zip_folders function."""

    def test_zip_folders_with_cwd(self, tmp_path: Path) -> None:
        """Should zip folders in cwd."""
        # Create some folders
        (tmp_path / "folder1").mkdir()
        (tmp_path / "folder2").mkdir()
        (tmp_path / ".git").mkdir()  # Should be ignored

        with patch.object(folderzip, "archive_folder") as mock_archive:
            folderzip.zip_folders(str(tmp_path))
            # Should archive folder1 and folder2, but not .git
            assert mock_archive.call_count == 2

    def test_zip_folders_nonexistent_cwd(self, tmp_path: Path) -> None:
        """Should handle nonexistent cwd."""
        folderzip.zip_folders(str(tmp_path / "nonexistent"))
        # Should print error message and return


# ---------------------------------------------------------------------- #
# TaskSpec definitions
# ---------------------------------------------------------------------- #
class TestTaskSpecDefinitions:
    """Test that all TaskSpec definitions are valid."""

    def test_folderzip_default_spec(self) -> None:
        """folderzip_default spec should be properly defined."""
        assert folderzip.folderzip_default.name == "folderzip_default"
        assert folderzip.folderzip_default.fn is not None


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_calls_run_cli(self) -> None:
        """main() should create a CliRunner and call run_cli()."""
        with patch.object(px.CliRunner, "run_cli") as mock_run_cli:
            folderzip.main()
            assert mock_run_cli.called
