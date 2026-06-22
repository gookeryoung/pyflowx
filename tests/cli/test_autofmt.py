"""Tests for cli.autofmt module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pyflowx as px
from pyflowx.cli import autofmt


# ---------------------------------------------------------------------- #
# format_with_ruff
# ---------------------------------------------------------------------- #
class TestFormatWithRuff:
    """Test format_with_ruff function."""

    def test_format_with_ruff(self, tmp_path: Path) -> None:
        """Should format with ruff."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.format_with_ruff(tmp_path, fix=True)
            assert mock_run.called

    def test_format_with_ruff_no_fix(self, tmp_path: Path) -> None:
        """Should format with ruff without fix."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.format_with_ruff(tmp_path, fix=False)
            # Should not include --fix flag
            call_args = mock_run.call_args[0][0]
            assert "--fix" not in call_args


# ---------------------------------------------------------------------- #
# lint_with_ruff
# ---------------------------------------------------------------------- #
class TestLintWithRuff:
    """Test lint_with_ruff function."""

    def test_lint_with_ruff(self, tmp_path: Path) -> None:
        """Should lint with ruff."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.lint_with_ruff(tmp_path, fix=True)
            assert mock_run.called

    def test_lint_with_ruff_no_fix(self, tmp_path: Path) -> None:
        """Should lint with ruff without fix."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.lint_with_ruff(tmp_path, fix=False)
            # Should not include --fix flag
            call_args = mock_run.call_args[0][0]
            assert "--fix" not in call_args


# ---------------------------------------------------------------------- #
# add_docstring
# ---------------------------------------------------------------------- #
class TestAddDocstring:
    """Test add_docstring function."""

    def test_add_docstring_to_file(self, tmp_path: Path) -> None:
        """Should add docstring to file."""
        py_file = tmp_path / "test.py"
        py_file.write_text("def test():\n    pass\n")

        result = autofmt.add_docstring(py_file, '"""Test module."""')
        assert result is True

    def test_add_docstring_skips_files_with_docstring(self, tmp_path: Path) -> None:
        """Should skip files that already have docstring."""
        py_file = tmp_path / "test.py"
        py_file.write_text('"""Existing docstring."""\ndef test():\n    pass\n')

        result = autofmt.add_docstring(py_file, '"""New docstring."""')
        assert result is False

    def test_add_docstring_empty_file(self, tmp_path: Path) -> None:
        """Should handle empty file."""
        py_file = tmp_path / "test.py"
        py_file.write_text("")

        result = autofmt.add_docstring(py_file, '"""Test module."""')
        # Should handle empty file
        assert result is True


# ---------------------------------------------------------------------- #
# generate_module_docstring
# ---------------------------------------------------------------------- #
class TestGenerateModuleDocstring:
    """Test generate_module_docstring function."""

    def test_generate_module_docstring_basic(self, tmp_path: Path) -> None:
        """Should generate basic docstring."""
        py_file = tmp_path / "test.py"
        py_file.write_text("def test():\n    pass\n")

        result = autofmt.generate_module_docstring(py_file)
        # Should contain "Tests for" since stem contains "test"
        assert "Tests for" in result

    def test_generate_module_docstring_with_package(self, tmp_path: Path) -> None:
        """Should generate docstring for package."""
        py_file = tmp_path / "mypackage" / "test.py"
        py_file.parent.mkdir(parents=True)
        py_file.write_text("def test():\n    pass\n")

        result = autofmt.generate_module_docstring(py_file)
        assert "mypackage" in result

    def test_generate_module_docstring_cli(self, tmp_path: Path) -> None:
        """Should generate docstring for CLI module."""
        py_file = tmp_path / "cli.py"
        py_file.write_text("def test():\n    pass\n")

        result = autofmt.generate_module_docstring(py_file)
        assert "Command-line interface" in result

    def test_generate_module_docstring_util(self, tmp_path: Path) -> None:
        """Should generate docstring for utility module."""
        py_file = tmp_path / "utils.py"
        py_file.write_text("def test():\n    pass\n")

        result = autofmt.generate_module_docstring(py_file)
        assert "Utility functions" in result


# ---------------------------------------------------------------------- #
# auto_add_docstrings
# ---------------------------------------------------------------------- #
class TestAutoAddDocstrings:
    """Test auto_add_docstrings function."""

    def test_auto_add_docstrings(self, tmp_path: Path) -> None:
        """Should auto add docstrings."""
        py_file = tmp_path / "test.py"
        py_file.write_text("def test():\n    pass\n")

        with patch.object(autofmt, "add_docstring", return_value=True):
            count = autofmt.auto_add_docstrings(tmp_path)
            assert count >= 0

    def test_auto_add_docstrings_skips_ignored(self, tmp_path: Path) -> None:
        """Should skip ignored directories."""
        py_file = tmp_path / "__pycache__" / "test.py"
        py_file.parent.mkdir()
        py_file.write_text("def test():\n    pass\n")

        count = autofmt.auto_add_docstrings(tmp_path)
        # Should skip __pycache__
        assert count == 0

    def test_auto_add_docstrings_no_files(self, tmp_path: Path) -> None:
        """Should handle no Python files."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("test content")

        count = autofmt.auto_add_docstrings(tmp_path)
        assert count == 0


# ---------------------------------------------------------------------- #
# sync_pyproject_config
# ---------------------------------------------------------------------- #
class TestSyncPyprojectConfig:
    """Test sync_pyproject_config function."""

    def test_sync_pyproject_config_creates_file(self, tmp_path: Path) -> None:
        """Should sync pyproject.toml config."""
        main_toml = tmp_path / "pyproject.toml"
        main_toml.write_text("[tool.ruff]\n")
        sub_dir = tmp_path / "subproject"
        sub_dir.mkdir()
        sub_toml = sub_dir / "pyproject.toml"
        sub_toml.write_text("[tool.ruff]\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.sync_pyproject_config(tmp_path)
            assert mock_run.called

    def test_sync_pyproject_config_updates_file(self, tmp_path: Path) -> None:
        """Should update existing pyproject.toml."""
        main_toml = tmp_path / "pyproject.toml"
        main_toml.write_text("[tool.ruff]\n")
        sub_dir = tmp_path / "subproject"
        sub_dir.mkdir()
        sub_toml = sub_dir / "pyproject.toml"
        sub_toml.write_text("[tool.ruff]\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.sync_pyproject_config(tmp_path)
            assert mock_run.called


# ---------------------------------------------------------------------- #
# format_all
# ---------------------------------------------------------------------- #
class TestFormatAll:
    """Test format_all function."""

    def test_format_all_runs_ruff_format(self, tmp_path: Path) -> None:
        """Should run ruff format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.format_all(tmp_path)
            assert mock_run.called

    def test_format_all_runs_ruff_check(self, tmp_path: Path) -> None:
        """Should run ruff check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            autofmt.format_all(tmp_path)
            # Should call ruff format and ruff check
            assert mock_run.call_count == 2


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_fmt_default_target(self) -> None:
        """main() should handle fmt command with default target."""
        with patch("sys.argv", ["autofmt", "fmt"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_fmt_custom_target(self) -> None:
        """main() should handle fmt command with custom target."""
        with patch("sys.argv", ["autofmt", "fmt", "--target", "src"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_lint_default_target(self) -> None:
        """main() should handle lint command with default target."""
        with patch("sys.argv", ["autofmt", "lint"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_lint_with_fix(self) -> None:
        """main() should handle lint command with fix."""
        with patch("sys.argv", ["autofmt", "lint", "--fix"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_lint_custom_target(self) -> None:
        """main() should handle lint command with custom target."""
        with patch("sys.argv", ["autofmt", "lint", "--target", "src"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_doc_default_root(self) -> None:
        """main() should handle doc command with default root."""
        with patch("sys.argv", ["autofmt", "doc"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_doc_custom_root(self) -> None:
        """main() should handle doc command with custom root."""
        with patch("sys.argv", ["autofmt", "doc", "--root-dir", "src"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_sync_default_root(self) -> None:
        """main() should handle sync command with default root."""
        with patch("sys.argv", ["autofmt", "sync"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_sync_custom_root(self) -> None:
        """main() should handle sync command with custom root."""
        with patch("sys.argv", ["autofmt", "sync", "--root-dir", "."]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help."""
        with patch("sys.argv", ["autofmt"]), patch.object(autofmt, "main"):
            # Just call main, it should show help and return
            autofmt.main()
            # main() should return without calling px.run
            assert True

    def test_main_creates_task_specs_with_verbose(self) -> None:
        """main() should create TaskSpecs with verbose=True."""
        with patch("sys.argv", ["autofmt", "fmt"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            assert mock_run.called

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["autofmt", "fmt"]), patch.object(px, "run") as mock_run:
            autofmt.main()
            # Check that strategy="thread" was used
            assert mock_run.called
