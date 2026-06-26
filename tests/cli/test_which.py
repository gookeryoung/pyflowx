"""Tests for cli.which module."""

from __future__ import annotations

import shutil
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli import which


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_with_single_command(self) -> None:
        """main() should handle single command argument."""
        with patch("sys.argv", ["which", "python"]), patch.object(
            shutil, "which", return_value="/usr/bin/python"
        ), patch.object(px, "run") as mock_run:
            which.main()
            # Should create a graph with one task
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            assert isinstance(graph, px.Graph)

    def test_main_with_multiple_commands(self) -> None:
        """main() should handle multiple command arguments."""
        with patch("sys.argv", ["which", "python", "pip", "node"]), patch.object(
            shutil, "which", return_value="/usr/bin/cmd"
        ), patch.object(px, "run") as mock_run:
            which.main()
            # Should create a graph with three tasks
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            assert isinstance(graph, px.Graph)

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["which"]), pytest.raises(SystemExit) as exc_info:
            which.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_specs_with_correct_names(self) -> None:
        """main() should create TaskSpecs with correct names."""
        with patch("sys.argv", ["which", "git", "npm"]), patch.object(
            shutil, "which", return_value="/usr/bin/cmd"
        ), patch.object(px, "run") as mock_run:
            which.main()
            graph = mock_run.call_args[0][0]
            # Check that task names are correct
            task_names = list(graph.all_specs().keys())
            assert "which_git" in task_names
            assert "which_npm" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["which", "python"]), patch.object(
            shutil, "which", return_value="/usr/bin/python"
        ), patch.object(px, "run") as mock_run:
            which.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
