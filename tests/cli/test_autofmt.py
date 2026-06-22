"""Tests for cli.autofmt module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pyflowx as px
from pyflowx.cli import autofmt


# ---------------------------------------------------------------------- #
# auto_add_docstrings
# ---------------------------------------------------------------------- #
class TestAutoAddDocstrings:
    """Test auto_add_docstrings function."""

    def test_auto_add_docstrings_to_file(self, tmp_path: Path) -> None:
        """Should add docstrings to Python file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test_func():\n    pass\n")

        with patch.object(autofmt, "add_docstring_to_file") as mock_add:
            autofmt.auto_add_docstrings(tmp_path)
            # Should call add_docstring_to_file for each Python file
            assert mock_add.called

    def test_auto_add_docstrings_skips_non_python_files(self, tmp_path: Path) -> None:
        """Should skip non-Python files."""
        text_file = tmp_path / "test.txt"
        text_file.write_text("not a python file")

        with patch.object(autofmt, "add_docstring_to_file") as mock_add:
            autofmt.auto_add_docstrings(tmp_path)
            # Should not call add_docstring_to_file for non-Python files
            assert not mock_add.called


# ---------------------------------------------------------------------- #
# sync_pyproject_config
# ---------------------------------------------------------------------- #
class TestSyncPyprojectConfig:
    """Test sync_pyproject_config function."""

    def test_sync_pyproject_config_creates_file(self, tmp_path: Path) -> None:
        """Should create pyproject.toml if it doesn't exist."""
        with patch.object(Path, "exists", return_value=False), patch.object(Path, "write_text") as mock_write:
            autofmt.sync_pyproject_config(tmp_path)
            # Should create pyproject.toml
            assert mock_write.called

    def test_sync_pyproject_config_updates_file(self, tmp_path: Path) -> None:
        """Should update existing pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.ruff]\n")

        with patch.object(Path, "exists", return_value=True), patch.object(
            Path, "read_text", return_value="[tool.ruff]\n"
        ), patch.object(Path, "write_text") as mock_write:
            autofmt.sync_pyproject_config(tmp_path)
            # Should update pyproject.toml
            assert mock_write.called


# ---------------------------------------------------------------------- #
# format_all
# ---------------------------------------------------------------------- #
class TestFormatAll:
    """Test format_all function."""

    def test_format_all_runs_ruff_format(self) -> None:
        """Should run ruff format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.format_all(Path())
            # Should call ruff format
            assert mock_run.called

    def test_format_all_runs_ruff_check(self) -> None:
        """Should run ruff check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.format_all(Path())
            # Should call ruff check
            assert mock_run.call_count >= 2


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_fmt_default_target(self) -> None:
        """main() should handle fmt with default target."""
        with patch("sys.argv", ["autofmt", "fmt"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert "ruff" in spec.cmd
                assert "format" in spec.cmd
                assert "." in spec.cmd

    def test_main_fmt_custom_target(self) -> None:
        """main() should handle fmt with custom target."""
        with patch("sys.argv", ["autofmt", "fmt", "--target", "src"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert "ruff" in spec.cmd
                assert "format" in spec.cmd
                assert "src" in spec.cmd

    def test_main_lint_default_target(self) -> None:
        """main() should handle lint with default target."""
        with patch("sys.argv", ["autofmt", "lint"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert "ruff" in spec.cmd
                assert "check" in spec.cmd

    def test_main_lint_with_fix(self) -> None:
        """main() should handle lint with fix."""
        with patch("sys.argv", ["autofmt", "lint", "--fix"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert "ruff" in spec.cmd
                assert "check" in spec.cmd
                assert "--fix" in spec.cmd
                assert "--unsafe-fixes" in spec.cmd

    def test_main_lint_custom_target(self) -> None:
        """main() should handle lint with custom target."""
        with patch("sys.argv", ["autofmt", "lint", "--target", "src"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_doc_default_root(self) -> None:
        """main() should handle doc with default root."""
        with patch("sys.argv", ["autofmt", "doc"]), patch.object(px, "run") as mock_run, patch.object(
            autofmt, "auto_add_docstrings"
        ):
            autofmt.main()
            assert mock_run.called

    def test_main_doc_custom_root(self) -> None:
        """main() should handle doc with custom root."""
        with patch("sys.argv", ["autofmt", "doc", "--root-dir", "src"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(autofmt, "auto_add_docstrings"):
            autofmt.main()
            assert mock_run.called

    def test_main_sync_default_root(self) -> None:
        """main() should handle sync with default root."""
        with patch("sys.argv", ["autofmt", "sync"]), patch.object(px, "run") as mock_run, patch.object(
            autofmt, "sync_pyproject_config"
        ):
            autofmt.main()
            assert mock_run.called

    def test_main_sync_custom_root(self) -> None:
        """main() should handle sync with custom root."""
        with patch("sys.argv", ["autofmt", "sync", "--root-dir", "src"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(autofmt, "sync_pyproject_config"):
            autofmt.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["autofmt"]), pytest.raises(SystemExit) as exc_info:
            autofmt.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_specs_with_verbose(self) -> None:
        """main() should create TaskSpecs with verbose=True."""
        with patch("sys.argv", ["autofmt", "fmt"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert spec.verbose is True

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["autofmt", "fmt"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
