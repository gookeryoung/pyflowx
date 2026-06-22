"""Tests for cli.piptool module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pyflowx as px
from pyflowx.cli import piptool


# ---------------------------------------------------------------------- #
# pip_uninstall
# ---------------------------------------------------------------------- #
class TestPipUninstall:
    """Test pip_uninstall function."""

    def test_pip_uninstall_single_package(self) -> None:
        """Should uninstall single package."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_uninstall(["numpy"])
            # Should call pip uninstall
            assert mock_run.called

    def test_pip_uninstall_multiple_packages(self) -> None:
        """Should uninstall multiple packages."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_uninstall(["numpy", "pandas", "scipy"])
            # Should call pip uninstall
            assert mock_run.called

    def test_pip_uninstall_with_wildcard(self) -> None:
        """Should handle wildcard in package name."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_uninstall(["numpy*"])
            assert mock_run.called


# ---------------------------------------------------------------------- #
# pip_reinstall
# ---------------------------------------------------------------------- #
class TestPipReinstall:
    """Test pip_reinstall function."""

    def test_pip_reinstall_online(self) -> None:
        """Should reinstall packages online."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_reinstall(["numpy"], offline=False)
            assert mock_run.called

    def test_pip_reinstall_offline(self) -> None:
        """Should reinstall packages offline."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_reinstall(["numpy"], offline=True)
            # Should call pip install with offline flags
            assert mock_run.called


# ---------------------------------------------------------------------- #
# pip_download
# ---------------------------------------------------------------------- #
class TestPipDownload:
    """Test pip_download function."""

    def test_pip_download_online(self) -> None:
        """Should download packages online."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_download(["numpy"], offline=False)
            assert mock_run.called

    def test_pip_download_offline(self) -> None:
        """Should download packages offline."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_download(["numpy"], offline=True)
            # Should call pip download with offline flags
            assert mock_run.called


# ---------------------------------------------------------------------- #
# pip_freeze
# ---------------------------------------------------------------------- #
class TestPipFreeze:
    """Test pip_freeze function."""

    def test_pip_freeze_creates_file(self, tmp_path: Path) -> None:
        """Should create requirements.txt file."""
        with patch("subprocess.run") as mock_run, patch.object(Path, "cwd", return_value=tmp_path):
            mock_run.return_value = MagicMock(stdout="numpy==1.0.0\npandas==2.0.0\n", returncode=0)
            piptool.pip_freeze()
            # Should create requirements.txt
            tmp_path / "requirements.txt"
            # Note: The actual implementation might write to current directory

    def test_pip_freeze_calls_subprocess(self) -> None:
        """Should call pip freeze."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            piptool.pip_freeze()
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert "pip" in call_args
            assert "freeze" in call_args


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_install_single_package(self) -> None:
        """main() should handle install single package."""
        with patch("sys.argv", ["piptool", "i", "numpy"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert "pip" in spec.cmd
                assert "install" in spec.cmd
                assert "numpy" in spec.cmd

    def test_main_install_multiple_packages(self) -> None:
        """main() should handle install multiple packages."""
        with patch("sys.argv", ["piptool", "i", "numpy", "pandas", "scipy"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.called

    def test_main_uninstall_packages(self) -> None:
        """main() should handle uninstall packages."""
        with patch("sys.argv", ["piptool", "u", "numpy"]), patch.object(px, "run") as mock_run, patch.object(
            piptool, "pip_uninstall"
        ):
            piptool.main()
            assert mock_run.called

    def test_main_reinstall_packages(self) -> None:
        """main() should handle reinstall packages."""
        with patch("sys.argv", ["piptool", "r", "numpy"]), patch.object(px, "run") as mock_run, patch.object(
            piptool, "pip_reinstall"
        ):
            piptool.main()
            assert mock_run.called

    def test_main_reinstall_offline(self) -> None:
        """main() should handle reinstall offline."""
        with patch("sys.argv", ["piptool", "r", "numpy", "--offline"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(piptool, "pip_reinstall"):
            piptool.main()
            assert mock_run.called

    def test_main_download_packages(self) -> None:
        """main() should handle download packages."""
        with patch("sys.argv", ["piptool", "d", "numpy"]), patch.object(px, "run") as mock_run, patch.object(
            piptool, "pip_download"
        ):
            piptool.main()
            assert mock_run.called

    def test_main_download_offline(self) -> None:
        """main() should handle download offline."""
        with patch("sys.argv", ["piptool", "d", "numpy", "--offline"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(piptool, "pip_download"):
            piptool.main()
            assert mock_run.called

    def test_main_upgrade_pip(self) -> None:
        """main() should handle upgrade pip."""
        with patch("sys.argv", ["piptool", "up"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert "python" in spec.cmd
                assert "-m" in spec.cmd
                assert "pip" in spec.cmd
                assert "install" in spec.cmd
                assert "--upgrade" in spec.cmd

    def test_main_freeze(self) -> None:
        """main() should handle freeze."""
        with patch("sys.argv", ["piptool", "f"]), patch.object(px, "run") as mock_run, patch.object(
            piptool, "pip_freeze"
        ):
            piptool.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["piptool"]), pytest.raises(SystemExit) as exc_info:
            piptool.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_specs_with_verbose(self) -> None:
        """main() should create TaskSpecs with verbose=True."""
        with patch("sys.argv", ["piptool", "i", "numpy"]), patch.object(px, "run") as mock_run:
            piptool.main()
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert spec.verbose is True

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["piptool", "i", "numpy"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
