"""Tests for cli.bumpversion module."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

import pyflowx as px
from pyflowx.cli import bumpversion


# ---------------------------------------------------------------------- #
# bump_version
# ---------------------------------------------------------------------- #
class TestBumpVersion:
    """Test bump_version function."""

    def test_bump_version_patch(self) -> None:
        """Should bump patch version."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            bumpversion.bump_version("patch")
            assert mock_run.called

    def test_bump_version_minor(self) -> None:
        """Should bump minor version."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            bumpversion.bump_version("minor")
            assert mock_run.called

    def test_bump_version_major(self) -> None:
        """Should bump major version."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            bumpversion.bump_version("major")
            assert mock_run.called

    def test_bump_version_with_tag(self) -> None:
        """Should bump version with tag."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="v1.0.0")
            bumpversion.bump_version("patch", tag=True)
            assert mock_run.called

    def test_bump_version_with_commit(self) -> None:
        """Should bump version with commit."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            bumpversion.bump_version("patch", commit=True)
            assert mock_run.called

    def test_bump_version_file_not_found(self) -> None:
        """Should handle FileNotFoundError."""
        with patch("subprocess.run", side_effect=FileNotFoundError), pytest.raises(FileNotFoundError):
            bumpversion.bump_version("patch")


# ---------------------------------------------------------------------- #
# bump_version_alpha
# ---------------------------------------------------------------------- #
class TestBumpVersionAlpha:
    """Test bump_version_alpha function."""

    def test_bump_version_alpha_patch(self) -> None:
        """Should bump alpha patch version."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            bumpversion.bump_version_alpha("patch")
            assert mock_run.called


# ---------------------------------------------------------------------- #
# TaskSpec definitions
# ---------------------------------------------------------------------- #
class TestTaskSpecDefinitions:
    """Test that all TaskSpec definitions are valid."""

    def test_bump_patch_spec(self) -> None:
        """bump_patch spec should be properly defined."""
        assert bumpversion.bump_patch.name == "bump_patch"
        assert bumpversion.bump_patch.fn is not None

    def test_bump_minor_spec(self) -> None:
        """bump_minor spec should be properly defined."""
        assert bumpversion.bump_minor.name == "bump_minor"
        assert bumpversion.bump_minor.fn is not None

    def test_bump_major_spec(self) -> None:
        """bump_major spec should be properly defined."""
        assert bumpversion.bump_major.name == "bump_major"
        assert bumpversion.bump_major.fn is not None


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_calls_run_cli(self) -> None:
        """main() should create a CliRunner and call run_cli()."""
        with patch.object(px.CliRunner, "run_cli") as mock_run_cli:
            bumpversion.main()
            assert mock_run_cli.called