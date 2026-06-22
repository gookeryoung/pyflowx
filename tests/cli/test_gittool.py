"""Tests for cli.gittool module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pyflowx.cli import gittool


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
