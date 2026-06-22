"""Tests for cli.filedate module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli import filedate


# ---------------------------------------------------------------------- #
# process_files_date
# ---------------------------------------------------------------------- #
class TestProcessFilesDate:
    """Test process_files_date function."""

    def test_process_files_date_add(self, tmp_path: Path) -> None:
        """Should add date prefix."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.object(filedate, "rename_file_with_date") as mock_rename:
            filedate.process_files_date([test_file], clear=False)
            assert mock_rename.called

    def test_process_files_date_clear(self, tmp_path: Path) -> None:
        """Should clear date prefix."""
        test_file = tmp_path / "2024-01-01_test.txt"
        test_file.write_text("test content")

        with patch.object(filedate, "rename_file_with_date") as mock_rename:
            filedate.process_files_date([test_file], clear=True)
            assert mock_rename.called

    def test_process_files_date_multiple_files(self, tmp_path: Path) -> None:
        """Should process multiple files."""
        test_files = [
            tmp_path / "test1.txt",
            tmp_path / "test2.txt",
            tmp_path / "test3.txt",
        ]
        for f in test_files:
            f.write_text("test content")

        with patch.object(filedate, "rename_file_with_date") as mock_rename:
            filedate.process_files_date(test_files, clear=False)
            assert mock_rename.call_count == 3


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_add_single_file(self) -> None:
        """main() should handle add command with single file."""
        with patch("sys.argv", ["filedate", "add", "test.txt"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(filedate, "process_files_date"):
            filedate.main()
            assert mock_run.called

    def test_main_add_multiple_files(self) -> None:
        """main() should handle add command with multiple files."""
        with patch("sys.argv", ["filedate", "add", "test1.txt", "test2.txt", "test3.txt"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(filedate, "process_files_date"):
            filedate.main()
            assert mock_run.called

    def test_main_clear_single_file(self) -> None:
        """main() should handle clear command with single file."""
        with patch("sys.argv", ["filedate", "clear", "test.txt"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(filedate, "process_files_date"):
            filedate.main()
            assert mock_run.called

    def test_main_clear_multiple_files(self) -> None:
        """main() should handle clear command with multiple files."""
        with patch("sys.argv", ["filedate", "clear", "test1.txt", "test2.txt", "test3.txt"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(filedate, "process_files_date"):
            filedate.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["filedate"]), pytest.raises(SystemExit) as exc_info:
            filedate.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_spec_with_correct_name(self) -> None:
        """main() should create TaskSpec with correct name."""
        with patch("sys.argv", ["filedate", "add", "test.txt"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(filedate, "process_files_date"):
            filedate.main()
            graph = mock_run.call_args[0][0]
            task_names = list(graph.all_specs().keys())
            assert "process_files_date" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["filedate", "add", "test.txt"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(filedate, "process_files_date"):
            filedate.main()
            assert mock_run.call_args[1]["strategy"] == "thread"