"""Tests for cli.packtool module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pyflowx as px
from pyflowx.cli import packtool


# ---------------------------------------------------------------------- #
# pack_source
# ---------------------------------------------------------------------- #
class TestPackSource:
    """Test pack_source function."""

    def test_pack_source_basic(self, tmp_path: Path) -> None:
        """Should pack source code."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("print('hello')")
        output_dir = tmp_path / "output"

        packtool.pack_source(project_dir, output_dir)
        assert output_dir.exists()

    def test_pack_source_with_pyproject(self, tmp_path: Path) -> None:
        """Should pack source with pyproject.toml."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
        (project_dir / "main.py").write_text("print('hello')")
        output_dir = tmp_path / "output"

        packtool.pack_source(project_dir, output_dir)
        assert output_dir.exists()


# ---------------------------------------------------------------------- #
# pack_dependencies
# ---------------------------------------------------------------------- #
class TestPackDependencies:
    """Test pack_dependencies function."""

    def test_pack_dependencies_empty(self, tmp_path: Path) -> None:
        """Should handle empty dependencies."""
        lib_dir = tmp_path / "libs"

        packtool.pack_dependencies(lib_dir, [])
        # Should print message and return

    def test_pack_dependencies_with_deps(self, tmp_path: Path) -> None:
        """Should pack dependencies."""
        lib_dir = tmp_path / "libs"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            packtool.pack_dependencies(lib_dir, ["numpy", "pandas"])
            assert mock_run.called


# ---------------------------------------------------------------------- #
# pack_wheel
# ---------------------------------------------------------------------- #
class TestPackWheel:
    """Test pack_wheel function."""

    def test_pack_wheel(self, tmp_path: Path) -> None:
        """Should pack wheel."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
        output_dir = tmp_path / "dist"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            packtool.pack_wheel(project_dir, output_dir)
            assert mock_run.called


# ---------------------------------------------------------------------- #
# install_embed_python
# ---------------------------------------------------------------------- #
class TestInstallEmbedPython:
    """Test install_embed_python function."""

    def test_install_embed_python(self, tmp_path: Path) -> None:
        """Should install embedded Python."""
        output_dir = tmp_path / "python"

        with patch("urllib.request.urlretrieve"), patch("zipfile.ZipFile") as mock_zipfile:
            mock_zip_instance = MagicMock()
            mock_zipfile.return_value.__enter__.return_value = mock_zip_instance
            packtool.install_embed_python("3.10", output_dir)
            assert mock_zip_instance.extractall.called

    def test_install_embed_python_with_cache(self, tmp_path: Path) -> None:
        """Should use cached Python."""
        output_dir = tmp_path / "python"
        cache_dir = tmp_path / ".cache" / "pypack"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "python-3.10.11-embed-amd64.zip"
        cache_file.write_bytes(b"ZIP content")

        with patch("zipfile.ZipFile") as mock_zipfile:
            mock_zip_instance = MagicMock()
            mock_zipfile.return_value.__enter__.return_value = mock_zip_instance
            packtool.install_embed_python("3.10", output_dir)
            assert mock_zip_instance.extractall.called


# ---------------------------------------------------------------------- #
# create_zip_package
# ---------------------------------------------------------------------- #
class TestCreateZipPackage:
    """Test create_zip_package function."""

    def test_create_zip_package(self, tmp_path: Path) -> None:
        """Should create ZIP package."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "test.txt").write_text("test content")
        output_file = tmp_path / "package.zip"

        packtool.create_zip_package(source_dir, output_file)
        assert output_file.exists()


# ---------------------------------------------------------------------- #
# clean_build_dir
# ---------------------------------------------------------------------- #
class TestCleanBuildDir:
    """Test clean_build_dir function."""

    def test_clean_build_dir_exists(self, tmp_path: Path) -> None:
        """Should clean existing build directory."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "test.txt").write_text("test")

        packtool.clean_build_dir(build_dir)
        assert not build_dir.exists()

    def test_clean_build_dir_not_exists(self, tmp_path: Path) -> None:
        """Should handle nonexistent build directory."""
        build_dir = tmp_path / "nonexistent"

        packtool.clean_build_dir(build_dir)
        # Should print message


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_src_command(self, tmp_path: Path) -> None:
        """main() should handle src command."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with patch("sys.argv", ["packtool", "src", "--project-dir", str(project_dir)]), patch.object(
            px, "run"
        ) as mock_run:
            packtool.main()
            assert mock_run.called

    def test_main_deps_command(self, tmp_path: Path) -> None:
        """main() should handle deps command."""
        with patch("sys.argv", ["packtool", "deps", "numpy", "pandas"]), patch.object(px, "run") as mock_run:
            packtool.main()
            assert mock_run.called

    def test_main_wheel_command(self, tmp_path: Path) -> None:
        """main() should handle wheel command."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with patch("sys.argv", ["packtool", "wheel", "--project-dir", str(project_dir)]), patch.object(
            px, "run"
        ) as mock_run:
            packtool.main()
            assert mock_run.called

    def test_main_embed_command(self, tmp_path: Path) -> None:
        """main() should handle embed command."""
        with patch("sys.argv", ["packtool", "embed", "--version", "3.10"]), patch.object(px, "run") as mock_run:
            packtool.main()
            assert mock_run.called

    def test_main_zip_command(self, tmp_path: Path) -> None:
        """main() should handle zip command."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        with patch("sys.argv", ["packtool", "zip", "--source-dir", str(source_dir)]), patch.object(
            px, "run"
        ) as mock_run:
            packtool.main()
            assert mock_run.called

    def test_main_clean_command(self) -> None:
        """main() should handle clean command."""
        with patch("sys.argv", ["packtool", "clean"]), patch.object(px, "run") as mock_run:
            packtool.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help."""
        with patch("sys.argv", ["packtool"]):
            packtool.main()
            # Should print help and return
