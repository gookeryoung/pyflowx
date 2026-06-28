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
def _find_task(name: str) -> pymake.px.TaskSpec:
    """从 pymake.tasks 或单任务别名变量中查找指定名称的 TaskSpec."""
    for spec in pymake.tasks:
        if spec.name == name:
            return spec
    # 单任务别名变量（_doc/_lint/_tox）
    alias_map = {"doc": pymake._doc, "lint": pymake._lint, "tox": pymake._tox}
    if name in alias_map:
        return alias_map[name]
    raise KeyError(f"任务 {name!r} 未找到")


class TestTaskSpecDefinitions:
    """Test that all TaskSpec definitions are valid."""

    def test_uv_build_spec(self) -> None:
        """uv_build spec should be properly defined."""
        spec = _find_task("uv_build")
        assert spec.name == "uv_build"
        assert spec.cmd == ["uv", "build"]
        assert spec.skip_if_missing is False

    def test_maturin_build_spec(self) -> None:
        """maturin_build spec should be properly defined."""
        spec = _find_task("maturin_build")
        assert spec.name == "maturin_build"
        assert isinstance(spec.cmd, list)
        assert spec.skip_if_missing is False

    def test_uv_sync_spec(self) -> None:
        """uv_sync spec should be properly defined."""
        spec = _find_task("uv_sync")
        assert spec.name == "uv_sync"
        assert spec.cmd == ["uv", "sync"]
        assert spec.skip_if_missing is False

    def test_git_clean_spec(self) -> None:
        """git_clean spec should be properly defined."""
        spec = _find_task("git_clean")
        assert spec.name == "git_clean"
        assert spec.cmd == ["gitt", "c"]
        assert spec.skip_if_missing is False

    def test_test_spec(self) -> None:
        """test spec should be properly defined."""
        spec = _find_task("test")
        assert spec.name == "test"
        assert isinstance(spec.cmd, list)
        assert "pytest" in spec.cmd
        assert "-m" in spec.cmd
        assert "not slow" in spec.cmd
        assert spec.skip_if_missing is False

    def test_test_fast_spec(self) -> None:
        """test_fast spec should be properly defined."""
        spec = _find_task("test_fast")
        assert spec.name == "test_fast"
        assert isinstance(spec.cmd, list)
        assert "pytest" in spec.cmd
        assert "-n" not in spec.cmd  # test_fast doesn't use parallel
        assert spec.skip_if_missing is False

    def test_test_coverage_spec(self) -> None:
        """test_coverage spec should be properly defined."""
        spec = _find_task("test_coverage")
        assert spec.name == "test_coverage"
        assert isinstance(spec.cmd, list)
        assert "pytest" in spec.cmd
        assert "--cov" in spec.cmd
        assert spec.skip_if_missing is False

    def test_ruff_lint_spec(self) -> None:
        """lint spec should be properly defined."""
        spec = _find_task("lint")
        assert spec.name == "lint"
        assert isinstance(spec.cmd, list)
        assert "ruff" in spec.cmd
        assert "check" in spec.cmd
        assert spec.skip_if_missing is False

    def test_doc_spec(self) -> None:
        """doc spec should be properly defined."""
        spec = _find_task("doc")
        assert spec.name == "doc"
        assert isinstance(spec.cmd, list)
        assert "sphinx-build" in spec.cmd
        assert spec.skip_if_missing is False

    def test_hatch_publish_spec(self) -> None:
        """publish_python spec should be properly defined."""
        spec = _find_task("publish_python")
        assert spec.name == "publish_python"
        assert spec.cmd == ["hatch", "publish"]
        assert spec.skip_if_missing is False

    def test_twine_publish_spec(self) -> None:
        """twine_publish spec should be properly defined."""
        spec = _find_task("twine_publish")
        assert spec.name == "twine_publish"
        assert isinstance(spec.cmd, list)
        assert "twine" in spec.cmd
        assert "upload" in spec.cmd
        assert spec.skip_if_missing is False

    def test_tox_spec(self) -> None:
        """tox spec should be properly defined."""
        spec = _find_task("tox")
        assert spec.name == "tox"
        assert spec.cmd == ["tox", "-p", "auto"]
        assert spec.skip_if_missing is False


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
