"""Tests for cli.envrs module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pyflowx as px
from pyflowx.cli import envrs


# ---------------------------------------------------------------------- #
# set_rust_mirror
# ---------------------------------------------------------------------- #
class TestSetRustMirror:
    """Test set_rust_mirror function."""

    def test_set_rust_mirror_aliyun(self, tmp_path: Path) -> None:
        """Should set aliyun mirror."""
        with patch.object(Path, "home", return_value=tmp_path):
            envrs.set_rust_mirror("aliyun")
            # Check environment variables
            assert os.environ.get("RUSTUP_DIST_SERVER") == "https://mirrors.aliyun.com/rustup"
            assert os.environ.get("RUSTUP_UPDATE_ROOT") == "https://mirrors.aliyun.com/rustup/rustup"
            # Check cargo config
            cargo_config = tmp_path / ".cargo" / "config.toml"
            assert cargo_config.exists()
            content = cargo_config.read_text()
            assert "aliyun" in content

    def test_set_rust_mirror_ustc(self, tmp_path: Path) -> None:
        """Should set ustc mirror."""
        with patch.object(Path, "home", return_value=tmp_path):
            envrs.set_rust_mirror("ustc")
            assert os.environ.get("RUSTUP_DIST_SERVER") == "https://mirrors.ustc.edu.cn/rust-static"
            assert os.environ.get("RUSTUP_UPDATE_ROOT") == "https://mirrors.ustc.edu.cn/rust-static/rustup"

    def test_set_rust_mirror_tsinghua(self, tmp_path: Path) -> None:
        """Should set tsinghua mirror."""
        with patch.object(Path, "home", return_value=tmp_path):
            envrs.set_rust_mirror("tsinghua")
            assert os.environ.get("RUSTUP_DIST_SERVER") == "https://mirrors.tuna.tsinghua.edu.cn/rustup"
            assert os.environ.get("RUSTUP_UPDATE_ROOT") == "https://mirrors.tuna.tsinghua.edu.cn/rustup/rustup"

    def test_set_rust_mirror_unknown_uses_default(self, tmp_path: Path) -> None:
        """Should use default mirror for unknown mirror name."""
        with patch.object(Path, "home", return_value=tmp_path):
            # pyrefly: ignore [bad-argument-type]
            envrs.set_rust_mirror("unknown")
            # Should use default mirror (tsinghua)
            assert os.environ.get("RUSTUP_DIST_SERVER") == "https://mirrors.tuna.tsinghua.edu.cn/rustup"

    def test_set_rust_mirror_creates_cargo_dir(self, tmp_path: Path) -> None:
        """Should create .cargo directory if it doesn't exist."""
        cargo_dir = tmp_path / ".cargo"
        with patch.object(Path, "home", return_value=tmp_path):
            envrs.set_rust_mirror("aliyun")
            assert cargo_dir.exists()
            assert cargo_dir.is_dir()

    def test_set_rust_mirror_prints_message(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Should print mirror name."""
        with patch.object(Path, "home", return_value=tmp_path):
            envrs.set_rust_mirror("aliyun")
            captured = capsys.readouterr()
            assert "已设置 Rust 镜像源: aliyun" in captured.out


# ---------------------------------------------------------------------- #
# install_rust
# ---------------------------------------------------------------------- #
class TestInstallRust:
    """Test install_rust function."""

    def test_install_rust_stable(self) -> None:
        """Should install stable Rust."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            envrs.install_rust("stable")
            mock_run.assert_called_once_with(["rustup", "toolchain", "install", "stable"], check=True)

    def test_install_rust_nightly(self) -> None:
        """Should install nightly Rust."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            envrs.install_rust("nightly")
            mock_run.assert_called_once_with(["rustup", "toolchain", "install", "nightly"], check=True)

    def test_install_rust_beta(self) -> None:
        """Should install beta Rust."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            envrs.install_rust("beta")
            mock_run.assert_called_once_with(["rustup", "toolchain", "install", "beta"], check=True)

    def test_install_rust_file_not_found(self) -> None:
        """Should raise FileNotFoundError when rustup not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError), pytest.raises(FileNotFoundError):
            envrs.install_rust("stable")

    def test_install_rust_prints_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should print installation message."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            envrs.install_rust("stable")
            captured = capsys.readouterr()
            assert "已安装 Rust stable" in captured.out


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_mirror_aliyun(self) -> None:
        """main() should handle mirror aliyun command."""
        with patch("sys.argv", ["envrs", "mirror", "aliyun"]), patch.object(px, "run") as mock_run, patch.object(
            envrs, "set_rust_mirror"
        ):
            envrs.main()
            assert mock_run.called

    def test_main_mirror_ustc(self) -> None:
        """main() should handle mirror ustc command."""
        with patch("sys.argv", ["envrs", "mirror", "ustc"]), patch.object(px, "run") as mock_run, patch.object(
            envrs, "set_rust_mirror"
        ):
            envrs.main()
            assert mock_run.called

    def test_main_mirror_tsinghua(self) -> None:
        """main() should handle mirror tsinghua command."""
        with patch("sys.argv", ["envrs", "mirror", "tsinghua"]), patch.object(px, "run") as mock_run, patch.object(
            envrs, "set_rust_mirror"
        ):
            envrs.main()
            assert mock_run.called

    def test_main_mirror_default(self) -> None:
        """main() should use default mirror when not specified."""
        with patch("sys.argv", ["envrs", "mirror"]), patch.object(px, "run") as mock_run, patch.object(
            envrs, "set_rust_mirror"
        ):
            envrs.main()
            assert mock_run.called

    def test_main_install_stable(self) -> None:
        """main() should handle install stable command."""
        with patch("sys.argv", ["envrs", "install", "stable"]), patch.object(px, "run") as mock_run:
            envrs.main()
            assert mock_run.called

    def test_main_install_nightly(self) -> None:
        """main() should handle install nightly command."""
        with patch("sys.argv", ["envrs", "install", "nightly"]), patch.object(px, "run") as mock_run:
            envrs.main()
            assert mock_run.called

    def test_main_install_beta(self) -> None:
        """main() should handle install beta command."""
        with patch("sys.argv", ["envrs", "install", "beta"]), patch.object(px, "run") as mock_run:
            envrs.main()
            assert mock_run.called

    def test_main_install_default(self) -> None:
        """main() should use default version when not specified."""
        with patch("sys.argv", ["envrs", "install"]), patch.object(px, "run") as mock_run:
            envrs.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and return."""
        with patch("sys.argv", ["envrs"]):
            envrs.main()
            # Should print help and return

    def test_main_invalid_version_shows_error(self) -> None:
        """main() with invalid version should show error."""
        with patch("sys.argv", ["envrs", "install", "invalid"]), pytest.raises(SystemExit) as exc_info:
            envrs.main()
        assert exc_info.value.code == 2

    def test_main_invalid_mirror_shows_error(self) -> None:
        """main() with invalid mirror should show error."""
        with patch("sys.argv", ["envrs", "mirror", "invalid"]), pytest.raises(SystemExit) as exc_info:
            envrs.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_spec_with_verbose(self) -> None:
        """main() should create TaskSpec with verbose=True."""
        with patch("sys.argv", ["envrs", "mirror", "aliyun"]), patch.object(px, "run") as mock_run, patch.object(
            envrs, "set_rust_mirror"
        ):
            envrs.main()
            graph = mock_run.call_args[0][0]
            specs = graph.all_specs()
            for spec in specs.values():
                assert spec.verbose is True

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["envrs", "mirror", "aliyun"]), patch.object(px, "run") as mock_run, patch.object(
            envrs, "set_rust_mirror"
        ):
            envrs.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
