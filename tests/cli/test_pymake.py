"""Tests for cli.pymake module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pyflowx.cli import pymake


# ---------------------------------------------------------------------- #
# TaskSpec definitions
# ---------------------------------------------------------------------- #
def _find_task(name: str) -> pymake.px.TaskSpec:
    """从 pymake.tasks 或 aliases 中查找指定名称的 TaskSpec."""
    for spec in pymake.tasks:
        if spec.name == name:
            return spec
    # 单任务别名（doc/lint/tox）内联在 aliases dict 中
    value = pymake.aliases.get(name)
    if isinstance(value, pymake.px.TaskSpec):
        return value
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
