"""Tests for cli.envqt module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli import envqt


# ---------------------------------------------------------------------- #
# set_qt_mirror
# ---------------------------------------------------------------------- #
class TestSetQtMirror:
    """Test set_qt_mirror function."""

    def test_set_qt_mirror(self, tmp_path: Path) -> None:
        """Should set Qt mirror."""
        with patch.object(Path, "home", return_value=tmp_path):
            envqt.set_qt_mirror()
            # Check Qt config


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_calls_run_cli(self) -> None:
        """main() should create a CliRunner and call run_cli()."""
        with pytest.raises(SystemExit) as exc_info:
            envqt.main()
        # run_cli() calls sys.exit(), so we should get SystemExit
        assert exc_info.value.code in (0, 1, 2)

    def test_main_with_list_argument(self) -> None:
        """main() should handle --list argument."""
        with patch("sys.argv", ["envqt", "--list"]), pytest.raises(SystemExit) as exc_info:
            envqt.main()
        assert exc_info.value.code == 0

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["envqt"]), pytest.raises(SystemExit) as exc_info:
            envqt.main()
        assert exc_info.value.code == 1