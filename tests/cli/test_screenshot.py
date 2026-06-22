"""Tests for cli.screenshot module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pyflowx as px
from pyflowx.cli import screenshot
from pyflowx.conditions import Constants


# ---------------------------------------------------------------------- #
# take_screenshot_full
# ---------------------------------------------------------------------- #
class TestTakeScreenshotFull:
    """Test take_screenshot_full function."""

    def test_take_screenshot_full_windows(self, tmp_path: Path) -> None:
        """Should take full screenshot on Windows."""
        if Constants.IS_WINDOWS:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                screenshot.take_screenshot_full(filename="test.png")
                assert mock_run.called

    def test_take_screenshot_full_linux(self, tmp_path: Path) -> None:
        """Should take full screenshot on Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_full(filename="test.png")
            assert mock_run.called

    def test_take_screenshot_full_with_custom_filename(self) -> None:
        """Should take screenshot with custom filename."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_full(filename="custom.png")
            assert mock_run.called

    def test_take_screenshot_full_default_filename(self) -> None:
        """Should use default filename."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_full()
            assert mock_run.called


# ---------------------------------------------------------------------- #
# take_screenshot_area
# ---------------------------------------------------------------------- #
class TestTakeScreenshotArea:
    """Test take_screenshot_area function."""

    def test_take_screenshot_area_windows(self, tmp_path: Path) -> None:
        """Should take area screenshot on Windows."""
        if Constants.IS_WINDOWS:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                screenshot.take_screenshot_area(filename="test.png")
                assert mock_run.called

    def test_take_screenshot_area_linux(self, tmp_path: Path) -> None:
        """Should take area screenshot on Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_area(filename="test.png")
            assert mock_run.called

    def test_take_screenshot_area_with_custom_filename(self) -> None:
        """Should take screenshot with custom filename."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_area(filename="custom.png")
            assert mock_run.called

    def test_take_screenshot_area_default_filename(self) -> None:
        """Should use default filename."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_area()
            assert mock_run.called


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_full_default_filename(self) -> None:
        """main() should handle full command with default filename."""
        with patch("sys.argv", ["screenshot", "full"]), patch.object(px, "run") as mock_run, patch.object(
            screenshot, "take_screenshot_full"
        ):
            screenshot.main()
            assert mock_run.called

    def test_main_full_custom_filename(self) -> None:
        """main() should handle full command with custom filename."""
        with patch("sys.argv", ["screenshot", "full", "--filename", "custom.png"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(screenshot, "take_screenshot_full"):
            screenshot.main()
            assert mock_run.called

    def test_main_area_default_filename(self) -> None:
        """main() should handle area command with default filename."""
        with patch("sys.argv", ["screenshot", "area"]), patch.object(px, "run") as mock_run, patch.object(
            screenshot, "take_screenshot_area"
        ):
            screenshot.main()
            assert mock_run.called

    def test_main_area_custom_filename(self) -> None:
        """main() should handle area command with custom filename."""
        with patch("sys.argv", ["screenshot", "area", "--filename", "custom.png"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(screenshot, "take_screenshot_area"):
            screenshot.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["screenshot"]), pytest.raises(SystemExit) as exc_info:
            screenshot.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_spec_with_correct_name(self) -> None:
        """main() should create TaskSpec with correct name."""
        with patch("sys.argv", ["screenshot", "full"]), patch.object(px, "run") as mock_run, patch.object(
            screenshot, "take_screenshot_full"
        ):
            screenshot.main()
            graph = mock_run.call_args[0][0]
            task_names = list(graph.all_specs().keys())
            assert "screenshot_full" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["screenshot", "full"]), patch.object(px, "run") as mock_run, patch.object(
            screenshot, "take_screenshot_full"
        ):
            screenshot.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
