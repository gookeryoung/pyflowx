"""Tests for cli.folderback module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pyflowx as px
from pyflowx.cli import folderback


# ---------------------------------------------------------------------- #
# remove_dump
# ---------------------------------------------------------------------- #
class TestRemoveDump:
    """Test remove_dump function."""

    def test_remove_dump_no_files(self, tmp_path: Path) -> None:
        """Should handle no zip files."""
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "backup"
        dst.mkdir()

        folderback.remove_dump(src, dst, 5)
        # Should not raise error

    def test_remove_dump_within_limit(self, tmp_path: Path) -> None:
        """Should not remove files within limit."""
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "backup"
        dst.mkdir()

        # Create some zip files
        for i in range(3):
            zip_file = dst / f"source_20240101_12000{i}.zip"
            zip_file.write_bytes(b"ZIP content")

        folderback.remove_dump(src, dst, 5)
        # All files should remain
        assert len(list(dst.glob("*.zip"))) == 3

    def test_remove_dump_exceeds_limit(self, tmp_path: Path) -> None:
        """Should remove oldest files when exceeds limit."""
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "backup"
        dst.mkdir()

        # Create more zip files than limit
        for i in range(7):
            zip_file = dst / f"source_20240101_12000{i}.zip"
            zip_file.write_bytes(b"ZIP content")

        folderback.remove_dump(src, dst, 5)
        # Should have only 5 files
        assert len(list(dst.glob("*.zip"))) == 5


# ---------------------------------------------------------------------- #
# zip_target
# ---------------------------------------------------------------------- #
class TestZipTarget:
    """Test zip_target function."""

    def test_zip_target_creates_zip(self, tmp_path: Path) -> None:
        """Should create zip file."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "test.txt").write_text("test content")
        dst = tmp_path / "backup"
        dst.mkdir()

        with patch("time.strftime", return_value="_20240101_120000"):
            folderback.zip_target(src, dst, 5)

        # Should create zip file
        zip_files = list(dst.glob("*.zip"))
        assert len(zip_files) == 1

    def test_zip_target_with_subdirectories(self, tmp_path: Path) -> None:
        """Should zip files in subdirectories."""
        src = tmp_path / "source"
        src.mkdir()
        subdir = src / "subdir"
        subdir.mkdir()
        (src / "test.txt").write_text("test content")
        (subdir / "nested.txt").write_text("nested content")
        dst = tmp_path / "backup"
        dst.mkdir()

        with patch("time.strftime", return_value="_20240101_120000"):
            folderback.zip_target(src, dst, 5)

        # Should create zip file
        zip_files = list(dst.glob("*.zip"))
        assert len(zip_files) == 1


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

    def test_backup_folder_creates_dst(self, tmp_path: Path) -> None:
        """Should create destination directory."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "test.txt").write_text("test content")
        backup_dir = tmp_path / "backup"

        with patch.object(folderback, "zip_target") as mock_zip:
            folderback.backup_folder(str(source_dir), str(backup_dir), 5)
            assert backup_dir.exists()
            assert mock_zip.called


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
