"""Tests for cli.lscalc module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pyflowx as px
from pyflowx.cli import lscalc
from pyflowx.conditions import Constants


# ---------------------------------------------------------------------- #
# get_ls_dyna_command
# ---------------------------------------------------------------------- #
class TestGetLsDynaCommand:
    """Test get_ls_dyna_command function."""

    def test_get_ls_dyna_command_windows(self) -> None:
        """Should get LS-DYNA command for Windows."""
        with patch.object(Constants, "IS_WINDOWS", True), patch.object(Constants, "IS_MACOS", False):
            cmd = lscalc.get_ls_dyna_command("input.k", 4)
            assert "ls-dyna_mpp" in cmd
            assert "i=input.k" in cmd
            assert "ncpu=4" in cmd

    def test_get_ls_dyna_command_linux(self) -> None:
        """Should get LS-DYNA command for Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), patch.object(Constants, "IS_MACOS", False):
            cmd = lscalc.get_ls_dyna_command("input.k", 8)
            assert "ls-dyna_mpp" in cmd
            assert "i=input.k" in cmd
            assert "ncpu=8" in cmd


# ---------------------------------------------------------------------- #
# run_ls_dyna
# ---------------------------------------------------------------------- #
class TestRunLsDyna:
    """Test run_ls_dyna function."""

    def test_run_ls_dyna_success(self, tmp_path: Path) -> None:
        """Should run LS-DYNA successfully."""
        input_file = tmp_path / "input.k"
        input_file.write_text("LS-DYNA input")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            lscalc.run_ls_dyna(str(input_file), ncpu=4)
            assert mock_run.called

    def test_run_ls_dyna_file_not_found(self, tmp_path: Path) -> None:
        """Should handle nonexistent input file."""
        input_file = tmp_path / "nonexistent.k"

        lscalc.run_ls_dyna(str(input_file), ncpu=4)
        # Should print error message

    def test_run_ls_dyna_command_not_found(self, tmp_path: Path) -> None:
        """Should handle command not found."""
        input_file = tmp_path / "input.k"
        input_file.write_text("LS-DYNA input")

        with patch("subprocess.run", side_effect=FileNotFoundError):
            lscalc.run_ls_dyna(str(input_file), ncpu=4)
            # Should print error message


# ---------------------------------------------------------------------- #
# run_ls_dyna_mpi
# ---------------------------------------------------------------------- #
class TestRunLsDynaMpi:
    """Test run_ls_dyna_mpi function."""

    def test_run_ls_dyna_mpi_success(self, tmp_path: Path) -> None:
        """Should run LS-DYNA MPI successfully."""
        input_file = tmp_path / "input.k"
        input_file.write_text("LS-DYNA input")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            lscalc.run_ls_dyna_mpi(str(input_file), ncpu=8)
            assert mock_run.called

    def test_run_ls_dyna_mpi_file_not_found(self, tmp_path: Path) -> None:
        """Should handle nonexistent input file."""
        input_file = tmp_path / "nonexistent.k"

        lscalc.run_ls_dyna_mpi(str(input_file), ncpu=8)
        # Should print error message


# ---------------------------------------------------------------------- #
# check_ls_dyna_status
# ---------------------------------------------------------------------- #
class TestCheckLsDynaStatus:
    """Test check_ls_dyna_status function."""

    def test_check_ls_dyna_status_windows(self) -> None:
        """Should check LS-DYNA status on Windows."""
        with patch.object(Constants, "IS_WINDOWS", True), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ls-dyna_mpp.exe", returncode=0)
            lscalc.check_ls_dyna_status()
            assert mock_run.called

    def test_check_ls_dyna_status_linux(self) -> None:
        """Should check LS-DYNA status on Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="1234", returncode=0)
            lscalc.check_ls_dyna_status()
            assert mock_run.called


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_run_command(self, tmp_path: Path) -> None:
        """main() should handle run command."""
        input_file = tmp_path / "input.k"
        input_file.write_text("LS-DYNA input")

        with patch("sys.argv", ["lscalc", "run", str(input_file)]), patch.object(px, "run") as mock_run:
            lscalc.main()
            assert mock_run.called

    def test_main_run_command_with_ncpu(self, tmp_path: Path) -> None:
        """main() should handle run command with ncpu."""
        input_file = tmp_path / "input.k"
        input_file.write_text("LS-DYNA input")

        with patch("sys.argv", ["lscalc", "run", str(input_file), "--ncpu", "8"]), patch.object(px, "run") as mock_run:
            lscalc.main()
            assert mock_run.called

    def test_main_mpi_command(self, tmp_path: Path) -> None:
        """main() should handle mpi command."""
        input_file = tmp_path / "input.k"
        input_file.write_text("LS-DYNA input")

        with patch("sys.argv", ["lscalc", "mpi", str(input_file)]), patch.object(px, "run") as mock_run:
            lscalc.main()
            assert mock_run.called

    def test_main_status_command(self) -> None:
        """main() should handle status command."""
        with patch("sys.argv", ["lscalc", "status"]), patch.object(px, "run") as mock_run:
            lscalc.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help."""
        with patch("sys.argv", ["lscalc"]):
            lscalc.main()
            # Should print help and return
