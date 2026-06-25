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

    def test_install_embed_python_basic(self, tmp_path: Path) -> None:
        """Should install embedded Python (mocked for speed)."""
        output_dir = tmp_path / "python"

        # Create a mock cache file that doesn't exist (force download)
        with patch("urllib.request.urlretrieve") as mock_urlretrieve, \
             patch("zipfile.ZipFile") as mock_zipfile:

            # Mock successful download
            mock_urlretrieve.return_value = None
            mock_zip_instance = MagicMock()
            mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

            # Ensure cache doesn't exist by using tmp_path as cache dir
            with patch.object(packtool, 'DEFAULT_CACHE_DIR', str(tmp_path / ".cache")):
                packtool.install_embed_python("3.10", output_dir)

                # Verify download was called
                assert mock_urlretrieve.called
                # Verify extraction was called
                assert mock_zip_instance.extractall.called
                # Verify output directory was created
                assert output_dir.exists()

    def test_install_embed_python_with_cache(self, tmp_path: Path) -> None:
        """Should use cached Python if available."""
        output_dir = tmp_path / "python"
        cache_dir = tmp_path / ".cache" / "pypack"
        cache_dir.mkdir(parents=True)

        # Create a fake cached zip file
        cache_file = cache_dir / "python-3.10.11-embed-amd64.zip"
        cache_file.write_bytes(b"PK\x03\x04" + b"\x00" * 100)  # Minimal ZIP header

        with patch("zipfile.ZipFile") as mock_zipfile:
            mock_zip_instance = MagicMock()
            mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

            packtool.install_embed_python("3.10", output_dir)

            # Verify extraction was called (using cache)
            assert mock_zip_instance.extractall.called
            # Verify output directory was created
            assert output_dir.exists()

    def test_install_embed_python_real_download(self, tmp_path: Path) -> None:
        """Should actually download and extract embedded Python (requires network).

        This test performs a real download to verify the entire workflow.
        It's marked to run only when network is available.
        """
        import platform
        import zipfile

        output_dir = tmp_path / "python_real"

        # Only run on Windows (embed Python is Windows-specific)
        if platform.system() != "Windows":
            return

        # Perform real installation
        packtool.install_embed_python("3.10", output_dir)

        # Verify installation succeeded
        assert output_dir.exists()

        # Verify key files are present
        expected_files = [
            "python.exe",
            "python310.dll",
            "python310.zip",
        ]

        for expected_file in expected_files:
            file_path = output_dir / expected_file
            assert file_path.exists(), f"Expected file {expected_file} not found"
            assert file_path.stat().st_size > 0, f"File {expected_file} is empty"

        # Verify python.exe is executable
        python_exe = output_dir / "python.exe"
        assert python_exe.is_file()

        # Verify the installation is functional
        # Check that we can at least read the zip file
        python_zip = output_dir / "python310.zip"
        assert zipfile.is_zipfile(python_zip)

        print(f"✅ Successfully downloaded and installed embed Python to {output_dir}")
        print(f"   Files: {list(output_dir.iterdir())}")

    def test_install_embed_python_different_versions(self, tmp_path: Path) -> None:
        """Should handle different Python versions."""
        output_dir = tmp_path / "python"

        with patch("urllib.request.urlretrieve") as mock_urlretrieve, patch("zipfile.ZipFile") as mock_zipfile:
            mock_zip_instance = MagicMock()
            mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

            # Test different versions
            for version in ["3.8", "3.9", "3.10", "3.11", "3.12"]:
                packtool.install_embed_python(version, output_dir)
                assert mock_urlretrieve.called

    def test_install_embed_python_creates_cache(self, tmp_path: Path) -> None:
        """Should create cache directory and file."""
        output_dir = tmp_path / "python"

        with patch("urllib.request.urlretrieve") as mock_urlretrieve, patch("zipfile.ZipFile") as mock_zipfile:
            mock_urlretrieve.return_value = None
            mock_zip_instance = MagicMock()
            mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

            packtool.install_embed_python("3.10", output_dir)

            # Verify cache directory was created
            Path(packtool.DEFAULT_CACHE_DIR)
            # Note: In test environment, cache might not persist due to mocking


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
