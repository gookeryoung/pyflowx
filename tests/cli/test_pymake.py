"""Tests for cli.pymake module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pyflowx.cli import pymake
from pyflowx.conditions import Constants


# ---------------------------------------------------------------------- #
# maturin_build_cmd
# ---------------------------------------------------------------------- #
class TestMaturinBuildCmd:
    """Test maturin_build_cmd function."""

    def test_returns_list(self) -> None:
        """Should return a list."""
        cmd = pymake.maturin_build_cmd()
        assert isinstance(cmd, list)

    def test_contains_maturin_build(self) -> None:
        """Should contain 'maturin' and 'build'."""
        cmd = pymake.maturin_build_cmd()
        assert "maturin" in cmd
        assert "build" in cmd

    def test_contains_release_flag(self) -> None:
        """Should contain release flag '-r'."""
        cmd = pymake.maturin_build_cmd()
        assert "-r" in cmd

    def test_windows_includes_target(self) -> None:
        """On Windows, should include target-specific flags."""
        cmd = pymake.maturin_build_cmd()
        if Constants.IS_WINDOWS:
            assert "--target" in cmd
            assert "x86_64-win7-windows-msvc" in cmd
            assert "-Zbuild-std" in cmd
            assert "-i" in cmd
            assert "python3.8" in cmd
        else:
            # On non-Windows, should not include Windows-specific flags
            assert "--target" not in cmd

    def test_does_not_mutate_on_multiple_calls(self) -> None:
        """Multiple calls should return independent lists."""
        cmd1 = pymake.maturin_build_cmd()
        cmd2 = pymake.maturin_build_cmd()
        assert cmd1 == cmd2
        # Mutating one should not affect the other
        cmd1.append("extra")
        assert "extra" not in cmd2

    def test_non_windows_excludes_target_flags(self) -> None:
        """On non-Windows, should not include Windows-specific flags (覆盖 22->32 分支)."""
        from unittest.mock import patch

        with patch.object(pymake.Constants, "IS_WINDOWS", False):
            cmd = pymake.maturin_build_cmd()
        assert "maturin" in cmd
        assert "build" in cmd
        assert "-r" in cmd
        assert "--target" not in cmd
        assert "-Zbuild-std" not in cmd


# ---------------------------------------------------------------------- #
# TaskSpec definitions
# ---------------------------------------------------------------------- #
class TestTaskSpecDefinitions:
    """Test that all TaskSpec definitions are valid."""

    def test_uv_build_spec(self) -> None:
        """uv_build spec should be properly defined."""
        assert pymake.uv_build.name == "uv_build"
        assert pymake.uv_build.cmd == ["uv", "build"]
        assert pymake.uv_build.skip_if_missing is True

    def test_maturin_build_spec(self) -> None:
        """maturin_build spec should be properly defined."""
        assert pymake.maturin_build.name == "maturin_build"
        assert isinstance(pymake.maturin_build.cmd, list)
        assert pymake.maturin_build.skip_if_missing is True

    def test_uv_sync_spec(self) -> None:
        """uv_sync spec should be properly defined."""
        assert pymake.uv_sync.name == "uv_sync"
        assert pymake.uv_sync.cmd == ["uv", "sync"]
        assert pymake.uv_sync.skip_if_missing is True

    def test_git_clean_spec(self) -> None:
        """git_clean spec should be properly defined."""
        assert pymake.git_clean.name == "git_clean"
        assert pymake.git_clean.cmd == ["gitt", "c"]
        assert pymake.git_clean.skip_if_missing is True

    def test_test_spec(self) -> None:
        """test spec should be properly defined."""
        assert pymake.test.name == "test"
        assert isinstance(pymake.test.cmd, list)
        assert "pytest" in pymake.test.cmd
        assert "-m" in pymake.test.cmd
        assert "not slow" in pymake.test.cmd
        assert pymake.test.skip_if_missing is True

    def test_test_fast_spec(self) -> None:
        """test_fast spec should be properly defined."""
        assert pymake.test_fast.name == "test_fast"
        assert isinstance(pymake.test_fast.cmd, list)
        assert "pytest" in pymake.test_fast.cmd
        assert "-n" not in pymake.test_fast.cmd  # test_fast doesn't use parallel
        assert pymake.test_fast.skip_if_missing is True

    def test_test_coverage_spec(self) -> None:
        """test_coverage spec should be properly defined."""
        assert pymake.test_coverage.name == "test_coverage"
        assert isinstance(pymake.test_coverage.cmd, list)
        assert "pytest" in pymake.test_coverage.cmd
        assert "--cov" in pymake.test_coverage.cmd
        assert pymake.test_coverage.skip_if_missing is True

    def test_ruff_lint_spec(self) -> None:
        """ruff_lint spec should be properly defined."""
        assert pymake.ruff_lint.name == "lint"
        assert isinstance(pymake.ruff_lint.cmd, list)
        assert "ruff" in pymake.ruff_lint.cmd
        assert "check" in pymake.ruff_lint.cmd
        assert pymake.ruff_lint.skip_if_missing is True

    def test_doc_spec(self) -> None:
        """doc spec should be properly defined."""
        assert pymake.doc.name == "doc"
        assert isinstance(pymake.doc.cmd, list)
        assert "sphinx-build" in pymake.doc.cmd
        assert pymake.doc.skip_if_missing is True

    def test_hatch_publish_spec(self) -> None:
        """hatch_publish spec should be properly defined."""
        assert pymake.hatch_publish.name == "publish_python"
        assert pymake.hatch_publish.cmd == ["hatch", "publish"]
        assert pymake.hatch_publish.skip_if_missing is True

    def test_twine_publish_spec(self) -> None:
        """twine_publish spec should be properly defined."""
        assert pymake.twine_publish.name == "twine_publish"
        assert isinstance(pymake.twine_publish.cmd, list)
        assert "twine" in pymake.twine_publish.cmd
        assert "upload" in pymake.twine_publish.cmd
        assert pymake.twine_publish.skip_if_missing is True

    def test_tox_spec(self) -> None:
        """tox spec should be properly defined."""
        assert pymake.tox.name == "tox"
        assert pymake.tox.cmd == ["tox", "-p", "auto"]
        assert pymake.tox.skip_if_missing is True


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_calls_run_cli(self) -> None:
        """main() should create a CliRunner and call run_cli()."""
        with pytest.raises(SystemExit) as exc_info:
            pymake.main()
        # run_cli() calls sys.exit(), so we should get SystemExit
        # The exit code depends on whether any commands are available
        assert exc_info.value.code in (0, 1, 2)

    def test_main_with_list_argument(self) -> None:
        """main() should handle --list argument."""
        with patch("sys.argv", ["pymake", "--list"]), pytest.raises(SystemExit) as exc_info:
            pymake.main()
        assert exc_info.value.code == 0

    def test_main_creates_runner_with_multiple_commands(self) -> None:
        """main() should create a CliRunner with multiple commands."""
        # We can't easily test the runner creation without mocking,
        # but we can verify that main() doesn't raise an error for --list
        with patch("sys.argv", ["pymake", "--list"]), pytest.raises(SystemExit):
            pymake.main()

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit with failure."""
        with patch("sys.argv", ["pymake"]), pytest.raises(SystemExit) as exc_info:
            pymake.main()
        assert exc_info.value.code == 1
