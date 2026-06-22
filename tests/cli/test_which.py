"""Tests for cli.which module."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli import which


# ---------------------------------------------------------------------- #
# which_command
# ---------------------------------------------------------------------- #
class TestWhichCommand:
    """Test which_command function."""

    def test_returns_path_when_command_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should return Path when command is found."""
        with patch.object(shutil, "which", return_value="/usr/bin/python"):
            result = which.which_command("python")
            assert result == Path("/usr/bin/python")
            captured = capsys.readouterr()
            assert "匹配路径" in captured.out
            assert "/usr/bin/python" in captured.out

    def test_returns_none_when_command_not_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should return None when command is not found."""
        with patch.object(shutil, "which", return_value=None):
            result = which.which_command("nonexistent_cmd")
            assert result is None
            captured = capsys.readouterr()
            assert "未找到" in captured.out
            assert "nonexistent_cmd" in captured.out

    def test_prints_match_path_on_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should print '匹配路径: - <path>' on success."""
        with patch.object(shutil, "which", return_value="C:\\Python\\python.exe"):
            _ = which.which_command("python")
            captured = capsys.readouterr()
            assert "匹配路径: - C:\\Python\\python.exe" in captured.out

    def test_prints_not_found_on_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should print '<command>: 未找到' on failure."""
        with patch.object(shutil, "which", return_value=None):
            _ = which.which_command("missing")
            captured = capsys.readouterr()
            assert "missing: 未找到" in captured.out


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
