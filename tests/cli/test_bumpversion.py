"""Tests for cli.bumpversion module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pyflowx.cli import bumpversion


@pytest.fixture(autouse=True)
def auto_use_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """自动使用临时路径."""
    monkeypatch.chdir(tmp_path)


# ---------------------------------------------------------------------- #
# bump_file_version
# ---------------------------------------------------------------------- #
class TestBumpFileVersion:
    """Test bump_file_version function."""

    def test_bump_patch_version(self, tmp_path: Path) -> None:
        """Should bump patch version correctly."""
        test_file = tmp_path / "pyproject.toml"
        test_file.write_text('version = "1.2.3"', encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result == "1.2.4"
        assert test_file.read_text(encoding="utf-8") == 'version = "1.2.4"'

    def test_bump_minor_version(self, tmp_path: Path) -> None:
        """Should bump minor version correctly."""
        test_file = tmp_path / "pyproject.toml"
        test_file.write_text('version = "1.2.3"', encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "minor")

        assert result == "1.3.0"
        assert test_file.read_text(encoding="utf-8") == 'version = "1.3.0"'

    def test_bump_major_version(self, tmp_path: Path) -> None:
        """Should bump major version correctly."""
        test_file = tmp_path / "pyproject.toml"
        test_file.write_text('version = "1.2.3"', encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "major")

        assert result == "2.0.0"
        assert test_file.read_text(encoding="utf-8") == 'version = "2.0.0"'

    def test_version_pattern_with_prerelease(self, tmp_path: Path) -> None:
        """Should handle version with prerelease suffix."""
        test_file = tmp_path / "pyproject.toml"
        test_file.write_text('version = "1.2.3-alpha.1"', encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result == "1.2.4"
        # 预发布版本应该被清除
        content = test_file.read_text(encoding="utf-8")
        assert "alpha" not in content

    def test_version_pattern_with_build_metadata(self, tmp_path: Path) -> None:
        """Should handle version with build metadata."""
        test_file = tmp_path / "pyproject.toml"
        test_file.write_text('version = "1.2.3+build.123"', encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result == "1.2.4"
        # 构建元数据应该被清除
        content = test_file.read_text(encoding="utf-8")
        assert "build" not in content

    def test_no_version_found(self, tmp_path: Path, capsys) -> None:
        """Should return None when no version pattern found."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("no version here", encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result is None
        captured = capsys.readouterr()
        assert "未找到版本号模式" in captured.out

    def test_utf8_encoding(self, tmp_path: Path) -> None:
        """Should handle UTF-8 encoded files correctly."""
        test_file = tmp_path / "__init__.py"
        test_file.write_text('__version__ = "1.2.3"', encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result == "1.2.4"
        assert test_file.read_text(encoding="utf-8") == '__version__ = "1.2.4"'

    def test_pyproject_toml_format(self, tmp_path: Path) -> None:
        """Should handle pyproject.toml format correctly."""
        test_file = tmp_path / "pyproject.toml"
        content = """
[project]
name = "test"
version = "0.1.0"
description = "Test project"
"""
        test_file.write_text(content, encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "minor")

        assert result == "0.2.0"
        updated = test_file.read_text(encoding="utf-8")
        assert 'version = "0.2.0"' in updated
        assert 'name = "test"' in updated

    def test_init_py_format(self, tmp_path: Path) -> None:
        """Should handle __init__.py format correctly."""
        test_file = tmp_path / "__init__.py"
        content = '''"""Package info."""

__version__ = "1.0.0"
'''
        test_file.write_text(content, encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "major")

        assert result == "2.0.0"
        updated = test_file.read_text(encoding="utf-8")
        assert '__version__ = "2.0.0"' in updated

    def test_multiple_versions_in_file(self, tmp_path: Path) -> None:
        """Should only bump the project version, not dependencies."""
        test_file = tmp_path / "pyproject.toml"
        content = """
[project]
version = "1.0.0"
dependencies = ["lib >= 2.0.0", "other >= 3.0.0"]
"""
        test_file.write_text(content, encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result == "1.0.1"
        updated = test_file.read_text(encoding="utf-8")
        assert 'version = "1.0.1"' in updated
        # 确保 dependencies 中的版本没有被更新
        assert "lib >= 2.0.0" in updated
        assert "other >= 3.0.0" in updated

    def test_file_read_error(self, tmp_path: Path, capsys) -> None:
        """Should handle file read errors."""
        # 创建一个目录而不是文件
        test_file = tmp_path / "test_dir"
        test_file.mkdir()

        with pytest.raises(Exception):  # noqa: B017
            bumpversion.bump_file_version(test_file, "patch")

    def test_file_write_error(self, tmp_path: Path, capsys) -> None:
        """Should handle file write errors."""
        # 在只读目录中创建文件（这个测试在某些系统上可能不适用）
        test_file = tmp_path / "readonly.toml"
        test_file.write_text('version = "1.0.0"', encoding="utf-8")
        # 设置为只读
        test_file.chmod(0o444)

        try:
            with pytest.raises(Exception):  # noqa: B017
                bumpversion.bump_file_version(test_file, "patch")
        finally:
            # 恢复权限以便清理
            test_file.chmod(0o644)


# ---------------------------------------------------------------------- #
# Version pattern tests
# ---------------------------------------------------------------------- #
class TestVersionPattern:
    """Test version pattern matching."""

    def test_simple_version(self, tmp_path: Path) -> None:
        """Should match simple version."""
        test_file = tmp_path / "__init__.py"
        test_file.write_text('__version__ = "1.0.0"', encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result == "1.0.1"

    def test_version_with_zeros(self, tmp_path: Path) -> None:
        """Should handle versions with zeros correctly."""
        test_file = tmp_path / "__init__.py"
        test_file.write_text('__version__ = "0.0.0"', encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result == "0.0.1"

    def test_large_version_numbers(self, tmp_path: Path) -> None:
        """Should handle large version numbers."""
        test_file = tmp_path / "__init__.py"
        test_file.write_text('__version__ = "10.20.30"', encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "minor")

        assert result == "10.21.0"

    def test_version_in_url(self, tmp_path: Path) -> None:
        """Should not match version in URL or other contexts."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("https://example.com/v1.2.3/download", encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        # 不应该匹配 URL 中的版本号
        assert result is None


# ---------------------------------------------------------------------- #
# Edge cases
# ---------------------------------------------------------------------- #
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file(self, tmp_path: Path, capsys) -> None:
        """Should handle empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("", encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result is None
        captured = capsys.readouterr()
        assert "未找到版本号模式" in captured.out

    def test_file_with_special_chars(self, tmp_path: Path) -> None:
        """Should handle file with special characters."""
        test_file = tmp_path / "__init__.py"
        content = '# 中文注释\n__version__ = "1.0.0"\n# 特殊字符: @#$%'
        test_file.write_text(content, encoding="utf-8")

        result = bumpversion.bump_file_version(test_file, "patch")

        assert result == "1.0.1"
        updated = test_file.read_text(encoding="utf-8")
        assert "# 中文注释" in updated
        assert "# 特殊字符: @#$%" in updated

    def test_consecutive_bumps(self, tmp_path: Path) -> None:
        """Should handle consecutive version bumps correctly."""
        test_file = tmp_path / "__init__.py"
        test_file.write_text('__version__ = "1.0.0"', encoding="utf-8")

        # 第一次 bump
        result1 = bumpversion.bump_file_version(test_file, "patch")
        assert result1 == "1.0.1"

        # 第二次 bump
        result2 = bumpversion.bump_file_version(test_file, "minor")
        assert result2 == "1.1.0"

        # 第三次 bump
        result3 = bumpversion.bump_file_version(test_file, "major")
        assert result3 == "2.0.0"

        # 验证最终结果
        assert test_file.read_text(encoding="utf-8") == '__version__ = "2.0.0"'


class TestBumpVersionCli:
    """Test bumpversion CLI."""

    def test_minor(self, tmp_path: Path) -> None:
        """Should handle minor version bump."""
        test_file = tmp_path / "__init__.py"
        test_file.write_text('__version__ = "1.0.0"', encoding="utf-8")

        # Mock px.run: 只真正执行第一次调用(版本更新),其余返回空 dict
        with patch("sys.argv", ["bumpversion", "minor", "--no-tag"]), patch("pyflowx.run") as mock_run:

            def run_side_effect(graph, strategy=None):
                # 执行实际版本更新任务
                results = {}
                for spec in graph.specs.values():
                    if spec.fn is not None and spec.args:
                        results[spec.name] = spec.fn(*spec.args)
                return results

            mock_run.side_effect = run_side_effect
            bumpversion.main()

        # 验证版本号已更新
        assert test_file.read_text(encoding="utf-8") == '__version__ = "1.1.0"'

    def test_no_valid_files(self, tmp_path: Path, capsys) -> None:
        """Should handle no valid files."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("这是一个测试文件", encoding="utf-8")

        with patch("sys.argv", ["bumpversion", "minor", "--no-tag"]), patch("pyflowx.run") as mock_run:

            def run_side_effect(graph, strategy=None):
                # 执行实际版本更新任务
                results = {}
                for spec in graph.specs.values():
                    if spec.fn is not None and spec.args:
                        results[spec.name] = spec.fn(*spec.args)
                return results

            mock_run.side_effect = run_side_effect
            bumpversion.main()

        # 验证未更新任何文件
        assert test_file.read_text(encoding="utf-8") == "这是一个测试文件"
        assert "未找到包含版本号的文件" in capsys.readouterr().out
