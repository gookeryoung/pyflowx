"""Tests for cli.clearscreen module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli import clearscreen
from pyflowx.conditions import Constants


# ---------------------------------------------------------------------- #
# clear_screen
# ---------------------------------------------------------------------- #
class TestClearScreen:
    """Test clear_screen function."""

    def test_clear_screen_windows(self) -> None:
        """Should clear screen on Windows."""
        if Constants.IS_WINDOWS:
            with patch("os.system") as mock_system:
                clearscreen.clear_screen()
                assert mock_system.called

    def test_clear_screen_linux(self) -> None:
        """Should clear screen on Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), \
             patch("os.system") as mock_system:
            clearscreen.clear_screen()
            assert mock_system.called


# ---------------------------------------------------------------------- #
# clear_screen_python
# ---------------------------------------------------------------------- #
class TestClearScreenPython:
    """Test clear_screen_python function."""

    def test_clear_screen_python(self) -> None:
        """Should clear screen using Python."""
        with patch("builtins.print") as mock_print:
            clearscreen.clear_screen_python()
            assert mock_print.called


# ---------------------------------------------------------------------- #
# clear_screen_cmd
# ---------------------------------------------------------------------- #
class TestClearScreenCmd:
    """Test clear_screen_cmd function."""

    def test_clear_screen_cmd(self) -> None:
        """Should clear screen using cmd."""
        with patch("os.system") as mock_system:
            clearscreen.clear_screen_cmd()
            assert mock_system.called


# ---------------------------------------------------------------------- #
# TaskSpec definitions
# ---------------------------------------------------------------------- #
class TestTaskSpecDefinitions:
    """Test that all TaskSpec definitions are valid."""

    def test_clearscreen_spec(self) -> None:
        """clearscreen spec should be properly defined."""
        assert clearscreen.clearscreen.name == "clearscreen"
        assert clearscreen.clearscreen.fn is not None

    def test_clearscreen_py_spec(self) -> None:
        """clearscreen_py spec should be properly defined."""
        assert clearscreen.clearscreen_py.name == "clearscreen_py"
        assert clearscreen.clearscreen_py.fn is not None

    def test_clearscreen_cmd_spec(self) -> None:
        """clearscreen_cmd spec should be properly defined."""
        assert clearscreen.clearscreen_cmd.name == "clearscreen_cmd"
        assert clearscreen.clearscreen_cmd.fn is not None


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_calls_run_cli(self) -> None:
        """main() should create a CliRunner and call run_cli()."""
        with pytest.raises(SystemExit) as exc_info:
            clearscreen.main()
        # run_cli() calls sys.exit(), so we should get SystemExit
        assert exc_info.value.code in (0, 1, 2)

    def test_main_with_list_argument(self) -> None:
        """main() should handle --list argument."""
        with patch("sys.argv", ["clearscreen", "--list"]), pytest.raises(SystemExit) as exc_info:
            clearscreen.main()
        assert exc_info.value.code == 0

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["clearscreen"]), pytest.raises(SystemExit) as exc_info:
            clearscreen.main()
        assert exc_info.value.code == 1