"""Tests for cli.folderzip module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli import folderzip


# ---------------------------------------------------------------------- #
# zip_folder
# ---------------------------------------------------------------------- #
class TestZipFolder:
    """Test zip_folder function."""

    def test_zip_folder_with_source_and_output(self, tmp_path: Path) -> None:
        """Should zip folder with source and output paths."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        output_file = tmp_path / "output.zip"

        with patch("zipfile.ZipFile") as mock_zip:
            folderzip.zip_folder(str(source_dir), str(output_file))
            assert mock_zip.called


# ---------------------------------------------------------------------- #
# unzip_folder
# ---------------------------------------------------------------------- #
class TestUnzipFolder:
    """Test unzip_folder function."""

    def test_unzip_folder_with_zip_and_output(self, tmp_path: Path) -> None:
        """Should unzip folder with zip and output paths."""
        zip_file = tmp_path / "test.zip"
        zip_file.write_bytes(b"ZIP content")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("zipfile.ZipFile") as mock_zip:
            folderzip.unzip_folder(str(zip_file), str(output_dir))
            assert mock_zip.called


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_calls_run_cli(self) -> None:
        """main() should create a CliRunner and call run_cli()."""
        with pytest.raises(SystemExit) as exc_info:
            folderzip.main()
        # run_cli() calls sys.exit(), so we should get SystemExit
        assert exc_info.value.code in (0, 1, 2)

    def test_main_with_list_argument(self) -> None:
        """main() should handle --list argument."""
        with patch("sys.argv", ["folderzip", "--list"]), pytest.raises(SystemExit) as exc_info:
            folderzip.main()
        assert exc_info.value.code == 0

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["folderzip"]), pytest.raises(SystemExit) as exc_info:
            folderzip.main()
        assert exc_info.value.code == 1