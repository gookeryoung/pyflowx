"""Tests for cli.filelevel module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli import filelevel


# ---------------------------------------------------------------------- #
# process_files_level
# ---------------------------------------------------------------------- #
class TestProcessFilesLevel:
    """Test process_files_level function."""

    def test_process_files_level_clear(self, tmp_path: Path) -> None:
        """Should clear level markers."""
        test_file = tmp_path / "[PUB]test.txt"
        test_file.write_text("test content")

        with patch.object(filelevel, "rename_file_with_level") as mock_rename:
            filelevel.process_files_level([test_file], level=0)
            assert mock_rename.called

    def test_process_files_level_pub(self, tmp_path: Path) -> None:
        """Should set PUB level."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.object(filelevel, "rename_file_with_level") as mock_rename:
            filelevel.process_files_level([test_file], level=1)
            assert mock_rename.called

    def test_process_files_level_int(self, tmp_path: Path) -> None:
        """Should set INT level."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.object(filelevel, "rename_file_with_level") as mock_rename:
            filelevel.process_files_level([test_file], level=2)
            assert mock_rename.called

    def test_process_files_level_con(self, tmp_path: Path) -> None:
        """Should set CON level."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.object(filelevel, "rename_file_with_level") as mock_rename:
            filelevel.process_files_level([test_file], level=3)
            assert mock_rename.called

    def test_process_files_level_cla(self, tmp_path: Path) -> None:
        """Should set CLA level."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.object(filelevel, "rename_file_with_level") as mock_rename:
            filelevel.process_files_level([test_file], level=4)
            assert mock_rename.called

    def test_process_files_level_multiple_files(self, tmp_path: Path) -> None:
        """Should process multiple files."""
        test_files = [
            tmp_path / "test1.txt",
            tmp_path / "test2.txt",
            tmp_path / "test3.txt",
        ]
        for f in test_files:
            f.write_text("test content")

        with patch.object(filelevel, "rename_file_with_level") as mock_rename:
            filelevel.process_files_level(test_files, level=1)
            assert mock_rename.call_count == 3


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_set_single_file(self) -> None:
        """main() should handle set command with single file."""
        with patch("sys.argv", ["filelevel", "set", "test.txt", "--level", "1"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(filelevel, "process_files_level"):
            filelevel.main()
            assert mock_run.called

    def test_main_set_multiple_files(self) -> None:
        """main() should handle set command with multiple files."""
        with patch(
            "sys.argv", ["filelevel", "set", "test1.txt", "test2.txt", "test3.txt", "--level", "2"]
        ), patch.object(px, "run") as mock_run, patch.object(filelevel, "process_files_level"):
            filelevel.main()
            assert mock_run.called

    def test_main_set_level_0(self) -> None:
        """main() should handle set command with level 0."""
        with patch("sys.argv", ["filelevel", "set", "test.txt", "--level", "0"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(filelevel, "process_files_level"):
            filelevel.main()
            assert mock_run.called

    def test_main_set_level_1(self) -> None:
        """main() should handle set command with level 1."""
        with patch("sys.argv", ["filelevel", "set", "test.txt", "--level", "1"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(filelevel, "process_files_level"):
            filelevel.main()
            assert mock_run.called

    def test_main_set_level_2(self) -> None:
        """main() should handle set command with level 2."""
        with patch("sys.argv", ["filelevel", "set", "test.txt", "--level", "2"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(filelevel, "process_files_level"):
            filelevel.main()
            assert mock_run.called

    def test_main_set_level_3(self) -> None:
        """main() should handle set command with level 3."""
        with patch("sys.argv", ["filelevel", "set", "test.txt", "--level", "3"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(filelevel, "process_files_level"):
            filelevel.main()
            assert mock_run.called

    def test_main_set_level_4(self) -> None:
        """main() should handle set command with level 4."""
        with patch("sys.argv", ["filelevel", "set", "test.txt", "--level", "4"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(filelevel, "process_files_level"):
            filelevel.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["filelevel"]), pytest.raises(SystemExit) as exc_info:
            filelevel.main()
        assert exc_info.value.code == 2

    def test_main_invalid_level_shows_error(self) -> None:
        """main() with invalid level should show error."""
        with patch("sys.argv", ["filelevel", "set", "test.txt", "--level", "5"]), pytest.raises(SystemExit) as exc_info:
            filelevel.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_spec_with_correct_name(self) -> None:
        """main() should create TaskSpec with correct name."""
        with patch("sys.argv", ["filelevel", "set", "test.txt", "--level", "1"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(filelevel, "process_files_level"):
            filelevel.main()
            graph = mock_run.call_args[0][0]
            task_names = list(graph.all_specs().keys())
            assert "process_files_level" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["filelevel", "set", "test.txt", "--level", "1"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(filelevel, "process_files_level"):
            filelevel.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
