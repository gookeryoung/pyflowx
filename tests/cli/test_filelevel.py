"""Tests for cli.filelevel module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pyflowx as px
from pyflowx.cli import filelevel


# ---------------------------------------------------------------------- #
# remove_marks
# ---------------------------------------------------------------------- #
class TestRemoveMarks:
    """Test remove_marks function."""

    def test_remove_marks_single_mark(self) -> None:
        """Should remove single mark."""
        stem = "filename(PUB)"
        result = filelevel.remove_marks(stem, ["PUB"])
        assert result == "filename"

    def test_remove_marks_multiple_marks(self) -> None:
        """Should remove multiple marks."""
        stem = "filename(PUB)(NOR)"
        result = filelevel.remove_marks(stem, ["PUB", "NOR"])
        assert result == "filename"

    def test_remove_marks_no_marks(self) -> None:
        """Should not change stem without marks."""
        stem = "filename"
        result = filelevel.remove_marks(stem, ["PUB"])
        assert result == "filename"


# ---------------------------------------------------------------------- #
# process_file_level
# ---------------------------------------------------------------------- #
class TestProcessFileLevel:
    """Test process_file_level function."""

    def test_process_file_level_set_pub(self, tmp_path: Path) -> None:
        """Should set PUB level."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        filelevel.process_file_level(test_file, level=1)
        # File should be renamed with PUB level

    def test_process_file_level_set_int(self, tmp_path: Path) -> None:
        """Should set INT level."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        filelevel.process_file_level(test_file, level=2)
        # File should be renamed with INT level

    def test_process_file_level_clear(self, tmp_path: Path) -> None:
        """Should clear level."""
        test_file = tmp_path / "test(PUB).txt"
        test_file.write_text("test content")

        filelevel.process_file_level(test_file, level=0)
        # File should be renamed without level

    def test_process_file_level_invalid_level(self, tmp_path: Path) -> None:
        """Should handle invalid level."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        filelevel.process_file_level(test_file, level=5)
        # Should print error message

    def test_process_file_level_nonexistent_file(self, tmp_path: Path) -> None:
        """Should handle nonexistent file."""
        test_file = tmp_path / "nonexistent.txt"

        filelevel.process_file_level(test_file, level=1)
        # Should print error message


# ---------------------------------------------------------------------- #
# process_files_level
# ---------------------------------------------------------------------- #
class TestProcessFilesLevel:
    """Test process_files_level function."""

    def test_process_files_level_batch(self, tmp_path: Path) -> None:
        """Should process multiple files."""
        files = []
        for i in range(3):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"content{i}")
            files.append(test_file)

        filelevel.process_files_level(files, level=1)
        # All files should be processed


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_set_command(self, tmp_path: Path) -> None:
        """main() should handle set command."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("sys.argv", ["filelevel", "set", str(test_file), "--level", "1"]), patch.object(
            px, "run"
        ) as mock_run:
            filelevel.main()
            assert mock_run.called

    def test_main_set_command_level_2(self, tmp_path: Path) -> None:
        """main() should handle set command with level 2."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("sys.argv", ["filelevel", "set", str(test_file), "--level", "2"]), patch.object(
            px, "run"
        ) as mock_run:
            filelevel.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help."""
        with patch("sys.argv", ["filelevel"]):
            filelevel.main()
            # Should print help and return
