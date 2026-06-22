"""Tests for cli.filedate module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pyflowx as px
from pyflowx.cli import filedate


# ---------------------------------------------------------------------- #
# get_file_timestamp
# ---------------------------------------------------------------------- #
class TestGetFileTimestamp:
    """Test get_file_timestamp function."""

    def test_get_file_timestamp(self, tmp_path: Path) -> None:
        """Should get file timestamp."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        timestamp = filedate.get_file_timestamp(test_file)
        assert len(timestamp) == 8  # YYYYMMDD format
        assert timestamp.isdigit()


# ---------------------------------------------------------------------- #
# remove_date_prefix
# ---------------------------------------------------------------------- #
class TestRemoveDatePrefix:
    """Test remove_date_prefix function."""

    def test_remove_date_prefix_with_date(self, tmp_path: Path) -> None:
        """Should remove date prefix from filename."""
        test_file = tmp_path / "20240101_test.txt"
        test_file.write_text("test content")

        new_path = filedate.remove_date_prefix(test_file)
        assert new_path.name == "test.txt"

    def test_remove_date_prefix_without_date(self, tmp_path: Path) -> None:
        """Should not change filename without date prefix."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        new_path = filedate.remove_date_prefix(test_file)
        assert new_path == test_file


# ---------------------------------------------------------------------- #
# add_date_prefix
# ---------------------------------------------------------------------- #
class TestAddDatePrefix:
    """Test add_date_prefix function."""

    def test_add_date_prefix(self, tmp_path: Path) -> None:
        """Should add date prefix to filename."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        new_path = filedate.add_date_prefix(test_file)
        assert new_path.name.startswith("20")  # Starts with year
        assert "_test.txt" in new_path.name


# ---------------------------------------------------------------------- #
# process_file_date
# ---------------------------------------------------------------------- #
class TestProcessFileDate:
    """Test process_file_date function."""

    def test_process_file_date_add(self, tmp_path: Path) -> None:
        """Should add date prefix."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        filedate.process_file_date(test_file, clear=False)
        # File should be renamed with date prefix

    def test_process_file_date_clear(self, tmp_path: Path) -> None:
        """Should clear date prefix."""
        test_file = tmp_path / "20240101_test.txt"
        test_file.write_text("test content")

        filedate.process_file_date(test_file, clear=True)
        # File should be renamed without date prefix


# ---------------------------------------------------------------------- #
# process_files_date
# ---------------------------------------------------------------------- #
class TestProcessFilesDate:
    """Test process_files_date function."""

    def test_process_files_date_batch(self, tmp_path: Path) -> None:
        """Should process multiple files."""
        files = []
        for i in range(3):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"content{i}")
            files.append(test_file)

        filedate.process_files_date(files, clear=False)
        # All files should be processed


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_add_command(self, tmp_path: Path) -> None:
        """main() should handle add command."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("sys.argv", ["filedate", "add", str(test_file)]), patch.object(px, "run") as mock_run:
            filedate.main()
            assert mock_run.called

    def test_main_clear_command(self, tmp_path: Path) -> None:
        """main() should handle clear command."""
        test_file = tmp_path / "20240101_test.txt"
        test_file.write_text("test content")

        with patch("sys.argv", ["filedate", "clear", str(test_file)]), patch.object(px, "run") as mock_run:
            filedate.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help."""
        with patch("sys.argv", ["filedate"]):
            filedate.main()
            # Should print help and return
