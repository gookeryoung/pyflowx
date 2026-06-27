"""Tests for cli.taskkill module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli.system import taskkill
from pyflowx.conditions import Constants


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_with_single_process(self) -> None:
        """main() should handle single process argument."""
        with patch("sys.argv", ["taskkill", "chrome.exe"]), patch.object(px, "run") as mock_run:
            taskkill.main()
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            assert isinstance(graph, px.Graph)

    def test_main_with_multiple_processes(self) -> None:
        """main() should handle multiple process arguments."""
        with patch("sys.argv", ["taskkill", "chrome.exe", "python.exe", "node.exe"]), patch.object(
            px, "run"
        ) as mock_run:
            taskkill.main()
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            assert isinstance(graph, px.Graph)

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["taskkill"]), pytest.raises(SystemExit) as exc_info:
            taskkill.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_specs_with_correct_names(self) -> None:
        """main() should create TaskSpecs with correct names."""
        with patch("sys.argv", ["taskkill", "chrome.exe", "python.exe"]), patch.object(px, "run") as mock_run:
            taskkill.main()
            graph = mock_run.call_args[0][0]
            task_names = list(graph.all_specs().keys())
            assert "kill_chrome.exe" in task_names
            assert "kill_python.exe" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["taskkill", "chrome.exe"]), patch.object(px, "run") as mock_run:
            taskkill.main()
            assert mock_run.call_args[1]["strategy"] == "thread"

    def test_main_windows_command_format(self) -> None:
        """main() should use Windows command format on Windows."""
        if Constants.IS_WINDOWS:
            with patch("sys.argv", ["taskkill", "chrome.exe"]), patch.object(px, "run") as mock_run:
                taskkill.main()
                graph = mock_run.call_args[0][0]
                specs = graph.all_specs()
                # Check that command includes Windows taskkill format
                for spec in specs.values():
                    assert spec.cmd[0] == "taskkill"
                    assert spec.cmd[1] == "/f"
                    assert spec.cmd[2] == "/im"

    def test_main_linux_command_format(self) -> None:
        """main() should use Linux command format on Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), patch("sys.argv", ["taskkill", "chrome.exe"]), patch.object(
            px, "run"
        ) as mock_run:
            taskkill.main()
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            # Check that command includes Linux pkill format
            for spec in specs.values():
                assert spec.cmd[0] == "pkill"
                assert spec.cmd[1] == "-f"

    def test_main_tasks_have_verbose_true(self) -> None:
        """main() should create tasks with verbose=True."""
        with patch("sys.argv", ["taskkill", "chrome.exe"]), patch.object(px, "run") as mock_run:
            taskkill.main()
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert spec.verbose is True

    def test_main_adds_wildcard_to_process_name(self) -> None:
        """main() should add wildcard to process name."""
        with patch("sys.argv", ["taskkill", "chrome.exe"]), patch.object(px, "run") as mock_run:
            taskkill.main()
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            # Check that wildcard is added
            for spec in specs.values():
                assert spec.cmd[-1].endswith("*")
