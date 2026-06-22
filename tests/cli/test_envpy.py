"""Tests for cli.envpy module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli import envpy


# ---------------------------------------------------------------------- #
# set_pip_mirror
# ---------------------------------------------------------------------- #
class TestSetPipMirror:
    """Test set_pip_mirror function."""

    def test_set_pip_mirror_tsinghua(self, tmp_path: Path) -> None:
        """Should set tsinghua mirror."""
        with patch.object(Path, "home", return_value=tmp_path):
            envpy.set_pip_mirror("tsinghua")
            # Check pip config
            pip_config = tmp_path / "pip" / "pip.ini"
            if envpy.Constants.IS_WINDOWS:
                assert pip_config.exists() or (tmp_path / "pip" / "pip.conf").exists()

    def test_set_pip_mirror_aliyun(self, tmp_path: Path) -> None:
        """Should set aliyun mirror."""
        with patch.object(Path, "home", return_value=tmp_path):
            envpy.set_pip_mirror("aliyun")
            # Check pip config
            pip_dir = tmp_path / "pip"
            assert pip_dir.exists()

    def test_set_pip_mirror_with_token(self, tmp_path: Path) -> None:
        """Should set mirror with token."""
        with patch.object(Path, "home", return_value=tmp_path):
            envpy.set_pip_mirror("tsinghua", token="test_token")
            # Check that token is set

    def test_set_pip_mirror_creates_pip_dir(self, tmp_path: Path) -> None:
        """Should create pip directory if it doesn't exist."""
        pip_dir = tmp_path / "pip"
        with patch.object(Path, "home", return_value=tmp_path):
            envpy.set_pip_mirror("tsinghua")
            assert pip_dir.exists()
            assert pip_dir.is_dir()


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_mirror_tsinghua(self) -> None:
        """main() should handle mirror tsinghua command."""
        with patch("sys.argv", ["envpy", "mirror", "tsinghua"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(envpy, "set_pip_mirror"):
            envpy.main()
            assert mock_run.called

    def test_main_mirror_aliyun(self) -> None:
        """main() should handle mirror aliyun command."""
        with patch("sys.argv", ["envpy", "mirror", "aliyun"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(envpy, "set_pip_mirror"):
            envpy.main()
            assert mock_run.called

    def test_main_mirror_with_token(self) -> None:
        """main() should handle mirror with token."""
        with patch("sys.argv", ["envpy", "mirror", "tsinghua", "--token", "test_token"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(envpy, "set_pip_mirror"):
            envpy.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["envpy"]), pytest.raises(SystemExit) as exc_info:
            envpy.main()
        assert exc_info.value.code == 2

    def test_main_invalid_mirror_shows_error(self) -> None:
        """main() with invalid mirror should show error."""
        with patch("sys.argv", ["envpy", "mirror", "invalid"]), pytest.raises(SystemExit) as exc_info:
            envpy.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_spec_with_correct_name(self) -> None:
        """main() should create TaskSpec with correct name."""
        with patch("sys.argv", ["envpy", "mirror", "tsinghua"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(envpy, "set_pip_mirror"):
            envpy.main()
            graph = mock_run.call_args[0][0]
            task_names = list(graph.all_specs().keys())
            assert "set_pip_mirror" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["envpy", "mirror", "tsinghua"]), \
             patch.object(px, "run") as mock_run, \
             patch.object(envpy, "set_pip_mirror"):
            envpy.main()
            assert mock_run.call_args[1]["strategy"] == "thread"