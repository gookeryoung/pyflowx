"""Tests for cli.sshcopyid module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pyflowx as px
from pyflowx.cli import sshcopyid


# ---------------------------------------------------------------------- #
# ssh_copy_id
# ---------------------------------------------------------------------- #
class TestSshCopyId:
    """Test ssh_copy_id function."""

    def test_ssh_copy_id_pub_key_not_exists(self, tmp_path: Path) -> None:
        """Should handle nonexistent public key."""
        with patch.object(Path, "expanduser", return_value=tmp_path / "nonexistent.pub"), pytest.raises(SystemExit):
            sshcopyid.ssh_copy_id("localhost", "user", "password")

    def test_ssh_copy_id_sshpass_not_found(self, tmp_path: Path) -> None:
        """Should handle sshpass not found."""
        pub_key = tmp_path / "id_rsa.pub"
        pub_key.write_text("ssh-rsa AAAAB3...")

        with patch.object(Path, "expanduser", return_value=pub_key), patch(
            "subprocess.run", side_effect=FileNotFoundError
        ), pytest.raises(SystemExit):
            sshcopyid.ssh_copy_id("localhost", "user", "password")

    def test_ssh_copy_id_timeout(self, tmp_path: Path) -> None:
        """Should handle SSH timeout."""
        pub_key = tmp_path / "id_rsa.pub"
        pub_key.write_text("ssh-rsa AAAAB3...")

        with patch.object(Path, "expanduser", return_value=pub_key), patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)
        ), pytest.raises(SystemExit):
            sshcopyid.ssh_copy_id("localhost", "user", "password")

    def test_ssh_copy_id_process_error(self, tmp_path: Path) -> None:
        """Should handle SSH process error."""
        pub_key = tmp_path / "id_rsa.pub"
        pub_key.write_text("ssh-rsa AAAAB3...")

        with patch.object(Path, "expanduser", return_value=pub_key), patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")
        ), pytest.raises(SystemExit):
            sshcopyid.ssh_copy_id("localhost", "user", "password")

    def test_ssh_copy_id_success(self, tmp_path: Path) -> None:
        """Should deploy SSH key successfully."""
        pub_key = tmp_path / "id_rsa.pub"
        pub_key.write_text("ssh-rsa AAAAB3...")

        with patch.object(Path, "expanduser", return_value=pub_key), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            sshcopyid.ssh_copy_id("localhost", "user", "password")
            assert mock_run.called

    def test_ssh_copy_id_with_custom_port(self, tmp_path: Path) -> None:
        """Should handle custom port."""
        pub_key = tmp_path / "id_rsa.pub"
        pub_key.write_text("ssh-rsa AAAAB3...")

        with patch.object(Path, "expanduser", return_value=pub_key), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            sshcopyid.ssh_copy_id("localhost", "user", "password", port=2222)
            # Verify port is used
            call_args = mock_run.call_args[0][0]
            assert "2222" in call_args

    def test_ssh_copy_id_with_custom_keypath(self, tmp_path: Path) -> None:
        """Should handle custom keypath."""
        custom_key = tmp_path / "custom.pub"
        custom_key.write_text("ssh-rsa AAAAB3...")

        with patch.object(Path, "expanduser", return_value=custom_key), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            sshcopyid.ssh_copy_id("localhost", "user", "password", keypath=str(custom_key))
            assert mock_run.called

    def test_ssh_copy_id_with_custom_timeout(self, tmp_path: Path) -> None:
        """Should handle custom timeout."""
        pub_key = tmp_path / "id_rsa.pub"
        pub_key.write_text("ssh-rsa AAAAB3...")

        with patch.object(Path, "expanduser", return_value=pub_key), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            sshcopyid.ssh_copy_id("localhost", "user", "password", timeout=60)
            # Verify timeout is used in ConnectTimeout option
            call_args = mock_run.call_args[0][0]
            assert "ConnectTimeout=60" in call_args


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_with_required_args(self) -> None:
        """main() should handle required arguments."""
        with patch("sys.argv", ["sshcopyid", "localhost", "user", "password"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(sshcopyid, "ssh_copy_id"):
            sshcopyid.main()
            assert mock_run.called
            graph = mock_run.call_args[0][0]
            assert isinstance(graph, px.Graph)

    def test_main_with_custom_port(self) -> None:
        """main() should handle custom port argument."""
        with patch("sys.argv", ["sshcopyid", "localhost", "user", "password", "--port", "2222"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(sshcopyid, "ssh_copy_id"):
            sshcopyid.main()
            assert mock_run.called

    def test_main_with_custom_keypath(self) -> None:
        """main() should handle custom keypath argument."""
        with patch(
            "sys.argv", ["sshcopyid", "localhost", "user", "password", "--keypath", "/custom/key.pub"]
        ), patch.object(px, "run") as mock_run, patch.object(sshcopyid, "ssh_copy_id"):
            sshcopyid.main()
            assert mock_run.called

    def test_main_with_custom_timeout(self) -> None:
        """main() should handle custom timeout argument."""
        with patch("sys.argv", ["sshcopyid", "localhost", "user", "password", "--timeout", "60"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(sshcopyid, "ssh_copy_id"):
            sshcopyid.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["sshcopyid"]), pytest.raises(SystemExit) as exc_info:
            sshcopyid.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_spec_with_correct_name(self) -> None:
        """main() should create TaskSpec with correct name."""
        with patch("sys.argv", ["sshcopyid", "localhost", "user", "password"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(sshcopyid, "ssh_copy_id"):
            sshcopyid.main()
            graph = mock_run.call_args[0][0]
            task_names = list(graph.all_specs().keys())
            assert "ssh_deploy" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["sshcopyid", "localhost", "user", "password"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(sshcopyid, "ssh_copy_id"):
            sshcopyid.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
