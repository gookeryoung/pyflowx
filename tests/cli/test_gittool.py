"""Tests for cli.gittool module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.cli import gittool


# ---------------------------------------------------------------------- #
# not_has_git_repo
# ---------------------------------------------------------------------- #
class TestNotHasGitRepo:
    """Test not_has_git_repo function."""

    def test_not_has_git_repo_true(self, tmp_path: Path) -> None:
        """Should return True when no .git directory."""
        with patch.object(Path, "cwd", return_value=tmp_path):
            result = gittool.not_has_git_repo()
            assert result is True

    def test_not_has_git_repo_false(self, tmp_path: Path) -> None:
        """Should return False when .git directory exists."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = gittool.not_has_git_repo()
            assert result is False

    def test_not_has_git_repo_cwd_not_exists(self, tmp_path: Path) -> None:
        """Should return True when cwd doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        with patch.object(Path, "cwd", return_value=nonexistent):
            result = gittool.not_has_git_repo()
            assert result is True


# ---------------------------------------------------------------------- #
# has_files
# ---------------------------------------------------------------------- #
class TestHasFiles:
    """Test has_files function."""

    def test_has_files_true(self, tmp_path: Path) -> None:
        """Should return True when files exist."""
        (tmp_path / "test.txt").write_text("test")

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = gittool.has_files()
            assert result is True

    def test_has_files_false(self, tmp_path: Path) -> None:
        """Should return False when no files."""
        with patch.object(Path, "cwd", return_value=tmp_path):
            result = gittool.has_files()
            assert result is False


# ---------------------------------------------------------------------- #
# init_sub_dirs
# ---------------------------------------------------------------------- #
class TestInitSubDirs:
    """Test init_sub_dirs function."""

    def test_init_sub_dirs_with_subdirectories(self, tmp_path: Path) -> None:
        """Should initialize git in subdirectories."""
        subdir1 = tmp_path / "subdir1"
        subdir1.mkdir()
        subdir2 = tmp_path / "subdir2"
        subdir2.mkdir()

        with patch.object(Path, "cwd", return_value=tmp_path), patch.object(px, "run") as mock_run:
            gittool.init_sub_dirs()
            # Should call px.run for each subdirectory
            assert mock_run.call_count == 2

    def test_init_sub_dirs_no_subdirectories(self, tmp_path: Path) -> None:
        """Should handle no subdirectories."""
        with patch.object(Path, "cwd", return_value=tmp_path), patch.object(px, "run") as mock_run:
            gittool.init_sub_dirs()
            # Should not call px.run
            assert mock_run.call_count == 0


# ---------------------------------------------------------------------- #
# TaskSpec definitions
# ---------------------------------------------------------------------- #
class TestTaskSpecDefinitions:
    """Test that all TaskSpec definitions are valid."""

    def test_push_spec(self) -> None:
        """push spec should be properly defined."""
        assert gittool.push.name == "push"
        assert gittool.push.cmd == ["git", "push"]

    def test_pull_spec(self) -> None:
        """pull spec should be properly defined."""
        assert gittool.pull.name == "pull"
        assert gittool.pull.cmd == ["git", "pull"]

    def test_kill_tgit_spec(self) -> None:
        """kill_tgit spec should be properly defined."""
        assert gittool.kill_tgit.name == "task_kill"
        assert "taskkill" in gittool.kill_tgit.cmd


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_calls_run_cli(self) -> None:
        """main() should create a CliRunner and call run_cli()."""
        with pytest.raises(SystemExit) as exc_info:
            gittool.main()
        # run_cli() calls sys.exit(), so we should get SystemExit
        assert exc_info.value.code in (0, 1, 2)

    def test_main_with_list_argument(self) -> None:
        """main() should handle --list argument."""
        with patch("sys.argv", ["gittool", "--list"]), pytest.raises(SystemExit) as exc_info:
            gittool.main()
        assert exc_info.value.code == 0

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["gittool"]), pytest.raises(SystemExit) as exc_info:
            gittool.main()
        assert exc_info.value.code == 1
