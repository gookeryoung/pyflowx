"""Tests for cli.piptool module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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
        with patch.object(piptool, "_expand_wildcard_packages", return_value=["numpy", "numpy-core"]), patch(
            "subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_uninstall(["numpy*"])
            assert mock_run.called


# ---------------------------------------------------------------------- #
# pip_reinstall
# ---------------------------------------------------------------------- #
class TestPipReinstall:
    """Test pip_reinstall function."""

    def test_pip_reinstall_single_package(self) -> None:
        """Should reinstall single package."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_reinstall(["numpy"])
            # Should call pip uninstall and pip install
            assert mock_run.call_count == 2

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

    def test_pip_download_single_package(self) -> None:
        """Should download single package."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            piptool.pip_download(["numpy"])
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

    def test_pip_freeze(self, tmp_path: Path) -> None:
        """Should freeze dependencies."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="numpy==1.0.0\npandas==2.0.0", returncode=0)
            piptool.pip_freeze()
            assert mock_run.called


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_install_command(self) -> None:
        """main() should handle install command."""
        with patch("sys.argv", ["piptool", "i", "numpy", "pandas"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.called

    def test_main_uninstall_command(self) -> None:
        """main() should handle uninstall command."""
        with patch("sys.argv", ["piptool", "u", "numpy"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.called

    def test_main_reinstall_command(self) -> None:
        """main() should handle reinstall command."""
        with patch("sys.argv", ["piptool", "r", "numpy"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.called

    def test_main_download_command(self) -> None:
        """main() should handle download command."""
        with patch("sys.argv", ["piptool", "d", "numpy"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.called

    def test_main_upgrade_command(self) -> None:
        """main() should handle upgrade command."""
        with patch("sys.argv", ["piptool", "up"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.called

    def test_main_freeze_command(self) -> None:
        """main() should handle freeze command."""
        with patch("sys.argv", ["piptool", "f"]), patch.object(px, "run") as mock_run:
            piptool.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help."""
        with patch("sys.argv", ["piptool"]):
            piptool.main()
            # Should print help and return
