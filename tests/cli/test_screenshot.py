"""Tests for cli.screenshot module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pyflowx as px
from pyflowx.cli import screenshot
from pyflowx.conditions import Constants


# ---------------------------------------------------------------------- #
# get_screenshot_path
# ---------------------------------------------------------------------- #
class TestGetScreenshotPath:
    """Test get_screenshot_path function."""

    def test_get_screenshot_path_with_filename(self, tmp_path: Path) -> None:
        """Should get screenshot path with filename."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = screenshot.get_screenshot_path("test.png")
            assert result.name == "test.png"

    def test_get_screenshot_path_without_filename(self, tmp_path: Path) -> None:
        """Should get screenshot path without filename."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = screenshot.get_screenshot_path()
            assert "screenshot_" in result.name
            assert result.suffix == ".png"


# ---------------------------------------------------------------------- #
# take_screenshot_full
# ---------------------------------------------------------------------- #
class TestTakeScreenshotFull:
    """Test take_screenshot_full function."""

    def test_take_screenshot_full_windows(self, tmp_path: Path) -> None:
        """Should take full screenshot on Windows."""
        with patch.object(Constants, "IS_WINDOWS", True), patch.object(Constants, "IS_MACOS", False), patch.object(
            Path, "home", return_value=tmp_path
        ), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_full()
            assert mock_run.called

    def test_take_screenshot_full_macos(self, tmp_path: Path) -> None:
        """Should take full screenshot on macOS."""
        with patch.object(Constants, "IS_WINDOWS", False), patch.object(Constants, "IS_MACOS", True), patch.object(
            Path, "home", return_value=tmp_path
        ), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_full()
            assert mock_run.called

    def test_take_screenshot_full_linux(self, tmp_path: Path) -> None:
        """Should take full screenshot on Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), patch.object(Constants, "IS_MACOS", False), patch.object(
            Path, "home", return_value=tmp_path
        ), patch("subprocess.run") as mock_run:
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
        with patch.object(Constants, "IS_WINDOWS", True), patch.object(Constants, "IS_MACOS", False), patch.object(
            Path, "home", return_value=tmp_path
        ), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_area()
            assert mock_run.called

    def test_take_screenshot_area_macos(self, tmp_path: Path) -> None:
        """Should take area screenshot on macOS."""
        with patch.object(Constants, "IS_WINDOWS", False), patch.object(Constants, "IS_MACOS", True), patch.object(
            Path, "home", return_value=tmp_path
        ), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_area()
            assert mock_run.called

    def test_take_screenshot_area_linux(self, tmp_path: Path) -> None:
        """Should take area screenshot on Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), patch.object(Constants, "IS_MACOS", False), patch.object(
            Path, "home", return_value=tmp_path
        ), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            screenshot.take_screenshot_area()
            assert mock_run.called


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_full_command(self, tmp_path: Path) -> None:
        """main() should handle full command."""
        with patch("sys.argv", ["screenshot", "full"]), patch.object(px, "run") as mock_run:
            screenshot.main()
            assert mock_run.called

    def test_main_area_command(self, tmp_path: Path) -> None:
        """main() should handle area command."""
        with patch("sys.argv", ["screenshot", "area"]), patch.object(px, "run") as mock_run:
            screenshot.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help."""
        with patch("sys.argv", ["screenshot"]):
            screenshot.main()
            # Should print help and return
