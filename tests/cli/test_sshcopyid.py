"""Tests for cli.sshcopyid module."""

from __future__ import annotations

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

    def test_ssh_copy_id_success(self) -> None:
        """ssh_copy_id should deploy SSH key successfully."""
        pytest.importorskip("paramiko")
        with patch("paramiko.SSHClient") as mock_ssh_client, patch.object(
            Path, "exists", return_value=True
        ), patch.object(Path, "read_text", return_value="ssh-rsa AAAAB3..."):
            mock_client = MagicMock()
            mock_ssh_client.return_value = mock_client
            mock_client.connect.return_value = None
            mock_client.exec_command.return_value = (MagicMock(), MagicMock(), MagicMock())

            result = sshcopyid.ssh_copy_id("localhost", "user", "password")
            assert result is None  # Function doesn't return anything

    def test_ssh_copy_id_with_custom_port(self) -> None:
        """ssh_copy_id should handle custom port."""
        pytest.importorskip("paramiko")
        with patch("paramiko.SSHClient") as mock_ssh_client, patch.object(
            Path, "exists", return_value=True
        ), patch.object(Path, "read_text", return_value="ssh-rsa AAAAB3..."):
            mock_client = MagicMock()
            mock_ssh_client.return_value = mock_client
            mock_client.connect.return_value = None
            mock_client.exec_command.return_value = (MagicMock(), MagicMock(), MagicMock())

            sshcopyid.ssh_copy_id("localhost", "user", "password", port=2222)
            # Verify that connect was called with custom port
            mock_client.connect.assert_called_once()
            call_args = mock_client.connect.call_args
            assert call_args[1]["port"] == 2222

    def test_ssh_copy_id_with_custom_keypath(self) -> None:
        """ssh_copy_id should handle custom key path."""
        pytest.importorskip("paramiko")
        with patch("paramiko.SSHClient") as mock_ssh_client, patch.object(
            Path, "exists", return_value=True
        ), patch.object(Path, "read_text", return_value="ssh-rsa AAAAB3..."):
            mock_client = MagicMock()
            mock_ssh_client.return_value = mock_client
            mock_client.connect.return_value = None
            mock_client.exec_command.return_value = (MagicMock(), MagicMock(), MagicMock())

            result = sshcopyid.ssh_copy_id("localhost", "user", "password", keypath="/custom/key.pub")
            # Verify that the custom keypath was used
            assert result is None


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
