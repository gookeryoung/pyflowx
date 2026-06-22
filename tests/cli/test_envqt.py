"""Tests for cli.envqt module."""

from __future__ import annotations

from unittest.mock import patch

import pyflowx as px
from pyflowx.cli import envqt


# ---------------------------------------------------------------------- #
# TaskSpec definitions
# ---------------------------------------------------------------------- #
class TestTaskSpecDefinitions:
    """Test that all TaskSpec definitions are valid."""

    def test_envqt_install_spec(self) -> None:
        """envqt_install spec should be properly defined."""
        assert envqt.envqt_install.name == "envqt_install"
        assert envqt.envqt_install.cmd is not None

    def test_envqt_fonts_spec(self) -> None:
        """envqt_fonts spec should be properly defined."""
        assert envqt.envqt_fonts.name == "envqt_fonts"
        assert envqt.envqt_fonts.cmd is not None


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_calls_run_cli(self) -> None:
        """main() should create a CliRunner and call run_cli()."""
        with patch.object(px.CliRunner, "run_cli") as mock_run_cli:
            envqt.main()
            assert mock_run_cli.called
