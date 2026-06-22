"""Tests for cli.packtool module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pyflowx as px
from pyflowx.cli import packtool


# ---------------------------------------------------------------------- #
# pack_source
# ---------------------------------------------------------------------- #
class TestPackSource:
    """Test pack_source function."""

    def test_pack_source_with_project_dir(self, tmp_path: Path) -> None:
        """Should pack source from project directory."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("shutil.make_archive") as mock_archive:
            packtool.pack_source(project_dir, output_dir)
            assert mock_archive.called

    def test_pack_source_creates_output_dir(self, tmp_path: Path) -> None:
        """Should create output directory if it doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        with patch("shutil.make_archive"):
            packtool.pack_source(project_dir, output_dir)
            assert output_dir.exists()


# ---------------------------------------------------------------------- #
# pack_dependencies
# ---------------------------------------------------------------------- #
class TestPackDependencies:
    """Test pack_dependencies function."""

    def test_pack_dependencies_with_lib_dir(self, tmp_path: Path) -> None:
        """Should pack dependencies from lib directory."""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        dependencies = ["numpy", "pandas"]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            packtool.pack_dependencies(lib_dir, dependencies)
            assert mock_run.called

    def test_pack_dependencies_empty_list(self, tmp_path: Path) -> None:
        """Should handle empty dependency list."""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            packtool.pack_dependencies(lib_dir, [])
            # Should still work with empty list


# ---------------------------------------------------------------------- #
# pack_wheel
# ---------------------------------------------------------------------- #
class TestPackWheel:
    """Test pack_wheel function."""

    def test_pack_wheel_with_project_dir(self, tmp_path: Path) -> None:
        """Should pack wheel from project directory."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            packtool.pack_wheel(project_dir, output_dir)
            assert mock_run.called

    def test_pack_wheel_creates_output_dir(self, tmp_path: Path) -> None:
        """Should create output directory if it doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            packtool.pack_wheel(project_dir, output_dir)
            assert output_dir.exists()


# ---------------------------------------------------------------------- #
# install_embed_python
# ---------------------------------------------------------------------- #
class TestInstallEmbedPython:
    """Test install_embed_python function."""

    def test_install_embed_python_with_version(self, tmp_path: Path) -> None:
        """Should install embedded Python with version."""
        output_dir = tmp_path / "python"

        with patch("subprocess.run") as mock_run, patch.object(Path, "exists", return_value=False):
            mock_run.return_value = MagicMock(returncode=0)
            packtool.install_embed_python("3.10", output_dir)
            assert mock_run.called

    def test_install_embed_python_creates_output_dir(self, tmp_path: Path) -> None:
        """Should create output directory if it doesn't exist."""
        output_dir = tmp_path / "python"

        with patch("subprocess.run") as mock_run, patch.object(Path, "exists", return_value=False):
            mock_run.return_value = MagicMock(returncode=0)
            packtool.install_embed_python("3.10", output_dir)
            assert output_dir.exists()


# ---------------------------------------------------------------------- #
# create_zip_package
# ---------------------------------------------------------------------- #
class TestCreateZipPackage:
    """Test create_zip_package function."""

    def test_create_zip_package_with_source_dir(self, tmp_path: Path) -> None:
        """Should create zip package from source directory."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        output_file = tmp_path / "package.zip"

        with patch("zipfile.ZipFile") as mock_zip:
            packtool.create_zip_package(source_dir, output_file)
            assert mock_zip.called

    def test_create_zip_package_with_files(self, tmp_path: Path) -> None:
        """Should create zip package with files."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_file = source_dir / "test.txt"
        test_file.write_text("test content")
        output_file = tmp_path / "package.zip"

        with patch("zipfile.ZipFile") as mock_zip:
            packtool.create_zip_package(source_dir, output_file)
            assert mock_zip.called


# ---------------------------------------------------------------------- #
# clean_build_dir
# ---------------------------------------------------------------------- #
class TestCleanBuildDir:
    """Test clean_build_dir function."""

    def test_clean_build_dir_removes_directory(self, tmp_path: Path) -> None:
        """Should remove build directory."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()

        with patch("shutil.rmtree") as mock_rmtree:
            packtool.clean_build_dir(build_dir)
            assert mock_rmtree.called

    def test_clean_build_dir_nonexistent(self, tmp_path: Path) -> None:
        """Should handle nonexistent build directory."""
        build_dir = tmp_path / "build"

        with patch.object(Path, "exists", return_value=False):
            packtool.clean_build_dir(build_dir)
            # Should not raise error


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_src_default_dirs(self) -> None:
        """main() should handle src command with default dirs."""
        with patch("sys.argv", ["packtool", "src"]), patch.object(px, "run") as mock_run, patch.object(
            packtool, "pack_source"
        ):
            packtool.main()
            assert mock_run.called

    def test_main_src_custom_dirs(self) -> None:
        """main() should handle src command with custom dirs."""
        with patch("sys.argv", ["packtool", "src", "--project-dir", "project", "--output-dir", "output"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(packtool, "pack_source"):
            packtool.main()
            assert mock_run.called

    def test_main_deps_default_dir(self) -> None:
        """main() should handle deps command with default dir."""
        with patch("sys.argv", ["packtool", "deps"]), patch.object(px, "run") as mock_run, patch.object(
            packtool, "pack_dependencies"
        ):
            packtool.main()
            assert mock_run.called

    def test_main_deps_with_dependencies(self) -> None:
        """main() should handle deps command with dependencies."""
        with patch("sys.argv", ["packtool", "deps", "--lib-dir", "lib", "numpy", "pandas"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(packtool, "pack_dependencies"):
            packtool.main()
            assert mock_run.called

    def test_main_wheel_default_dirs(self) -> None:
        """main() should handle wheel command with default dirs."""
        with patch("sys.argv", ["packtool", "wheel"]), patch.object(px, "run") as mock_run, patch.object(
            packtool, "pack_wheel"
        ):
            packtool.main()
            assert mock_run.called

    def test_main_wheel_custom_dirs(self) -> None:
        """main() should handle wheel command with custom dirs."""
        with patch(
            "sys.argv", ["packtool", "wheel", "--project-dir", "project", "--output-dir", "output"]
        ), patch.object(px, "run") as mock_run, patch.object(packtool, "pack_wheel"):
            packtool.main()
            assert mock_run.called

    def test_main_embed_default_version(self) -> None:
        """main() should handle embed command with default version."""
        with patch("sys.argv", ["packtool", "embed"]), patch.object(px, "run") as mock_run, patch.object(
            packtool, "install_embed_python"
        ):
            packtool.main()
            assert mock_run.called

    def test_main_embed_custom_version(self) -> None:
        """main() should handle embed command with custom version."""
        with patch("sys.argv", ["packtool", "embed", "--version", "3.11", "--output-dir", "python"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(packtool, "install_embed_python"):
            packtool.main()
            assert mock_run.called

    def test_main_zip_default_params(self) -> None:
        """main() should handle zip command with default params."""
        with patch("sys.argv", ["packtool", "zip"]), patch.object(px, "run") as mock_run, patch.object(
            packtool, "create_zip_package"
        ):
            packtool.main()
            assert mock_run.called

    def test_main_zip_custom_params(self) -> None:
        """main() should handle zip command with custom params."""
        with patch(
            "sys.argv", ["packtool", "zip", "--source-dir", "source", "--output-file", "package.zip"]
        ), patch.object(px, "run") as mock_run, patch.object(packtool, "create_zip_package"):
            packtool.main()
            assert mock_run.called

    def test_main_clean(self) -> None:
        """main() should handle clean command."""
        with patch("sys.argv", ["packtool", "clean"]), patch.object(px, "run") as mock_run, patch.object(
            packtool, "clean_build_dir"
        ):
            packtool.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["packtool"]), pytest.raises(SystemExit) as exc_info:
            packtool.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_spec_with_correct_name(self) -> None:
        """main() should create TaskSpec with correct name."""
        with patch("sys.argv", ["packtool", "src"]), patch.object(px, "run") as mock_run, patch.object(
            packtool, "pack_source"
        ):
            packtool.main()
            graph = mock_run.call_args[0][0]
            task_names = list(graph.all_specs().keys())
            assert "pack_source" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["packtool", "src"]), patch.object(px, "run") as mock_run, patch.object(
            packtool, "pack_source"
        ):
            packtool.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
