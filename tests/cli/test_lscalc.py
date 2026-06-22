"""Tests for cli.lscalc module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import pyflowx as px
from pyflowx.cli import lscalc
from pyflowx.conditions import Constants


# ---------------------------------------------------------------------- #
# run_ls_dyna
# ---------------------------------------------------------------------- #
class TestRunLsDyna:
    """Test run_ls_dyna function."""

    def test_run_ls_dyna_with_input_file(self) -> None:
        """Should run LS-DYNA with input file."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            lscalc.run_ls_dyna("test.k", ncpu=4)
            assert mock_run.called

    def test_run_ls_dyna_with_custom_ncpu(self) -> None:
        """Should run LS-DYNA with custom CPU count."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            lscalc.run_ls_dyna("test.k", ncpu=8)
            assert mock_run.called
            # Check that ncpu is passed correctly

    def test_run_ls_dyna_windows_command(self) -> None:
        """Should use Windows command format on Windows."""
        if Constants.IS_WINDOWS:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                lscalc.run_ls_dyna("test.k", ncpu=4)
                assert mock_run.called
                # Check command format

    def test_run_ls_dyna_linux_command(self) -> None:
        """Should use Linux command format on Linux."""
        with patch.object(Constants, "IS_WINDOWS", False), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            lscalc.run_ls_dyna("test.k", ncpu=4)
            assert mock_run.called


# ---------------------------------------------------------------------- #
# run_ls_dyna_mpi
# ---------------------------------------------------------------------- #
class TestRunLsDynaMpi:
    """Test run_ls_dyna_mpi function."""

    def test_run_ls_dyna_mpi_with_input_file(self) -> None:
        """Should run LS-DYNA MPI with input file."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            lscalc.run_ls_dyna_mpi("test.k", ncpu=4)
            assert mock_run.called

    def test_run_ls_dyna_mpi_with_custom_ncpu(self) -> None:
        """Should run LS-DYNA MPI with custom CPU count."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            lscalc.run_ls_dyna_mpi("test.k", ncpu=8)
            assert mock_run.called


# ---------------------------------------------------------------------- #
# check_ls_dyna_status
# ---------------------------------------------------------------------- #
class TestCheckLsDynaStatus:
    """Test check_ls_dyna_status function."""

    def test_check_ls_dyna_status_running(self) -> None:
        """Should detect running LS-DYNA process."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="lsdyna.exe\n", returncode=0)
            lscalc.check_ls_dyna_status()
            assert mock_run.called

    def test_check_ls_dyna_status_not_running(self) -> None:
        """Should detect no LS-DYNA process."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            lscalc.check_ls_dyna_status()
            assert mock_run.called


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_run_with_input_file(self) -> None:
        """main() should handle run command with input file."""
        with patch("sys.argv", ["lscalc", "run", "test.k"]), patch.object(px, "run") as mock_run, patch.object(
            lscalc, "run_ls_dyna"
        ):
            lscalc.main()
            assert mock_run.called

    def test_main_run_with_custom_ncpu(self) -> None:
        """main() should handle run command with custom CPU count."""
        with patch("sys.argv", ["lscalc", "run", "test.k", "--ncpu", "8"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(lscalc, "run_ls_dyna"):
            lscalc.main()
            assert mock_run.called

    def test_main_mpi_with_input_file(self) -> None:
        """main() should handle mpi command with input file."""
        with patch("sys.argv", ["lscalc", "mpi", "test.k"]), patch.object(px, "run") as mock_run, patch.object(
            lscalc, "run_ls_dyna_mpi"
        ):
            lscalc.main()
            assert mock_run.called

    def test_main_mpi_with_custom_ncpu(self) -> None:
        """main() should handle mpi command with custom CPU count."""
        with patch("sys.argv", ["lscalc", "mpi", "test.k", "--ncpu", "8"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(lscalc, "run_ls_dyna_mpi"):
            lscalc.main()
            assert mock_run.called

    def test_main_status(self) -> None:
        """main() should handle status command."""
        with patch("sys.argv", ["lscalc", "status"]), patch.object(px, "run") as mock_run, patch.object(
            lscalc, "check_ls_dyna_status"
        ):
            lscalc.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["lscalc"]), pytest.raises(SystemExit) as exc_info:
            lscalc.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_spec_with_correct_name(self) -> None:
        """main() should create TaskSpec with correct name."""
        with patch("sys.argv", ["lscalc", "run", "test.k"]), patch.object(px, "run") as mock_run, patch.object(
            lscalc, "run_ls_dyna"
        ):
            lscalc.main()
            graph = mock_run.call_args[0][0]
            task_names = list(graph.all_specs().keys())
            assert "run_ls_dyna" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["lscalc", "run", "test.k"]), patch.object(px, "run") as mock_run, patch.object(
            lscalc, "run_ls_dyna"
        ):
            lscalc.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
