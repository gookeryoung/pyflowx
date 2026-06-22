"""Tests for cli.clearscreen module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                clearscreen.clear_screen()
                assert mock_run.called

    def test_clear_screen_linux(self) -> None:
        """Should clear screen on Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            clearscreen.clear_screen()
            assert mock_run.called


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_creates_graph_and_runs(self) -> None:
        """main() should create a Graph and run it."""
        with patch.object(px, "run") as mock_run:
            clearscreen.main()
            assert mock_run.called
