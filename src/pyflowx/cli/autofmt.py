"""自动格式化工具模块.

提供 Python 代码自动格式化的常用功能封装,
支持 docstring 自动生成、pyproject.toml 配置同步等功能.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pyflowx as px

try:
    import tomllib  # noqa: F401

    HAS_TOMLLIB = True
except ImportError:
    HAS_TOMLLIB = False


# ============================================================================
# 配置
# ============================================================================

IGNORE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    ".venv",
    ".idea",
    ".vscode",
    "*.egg-info",
    "dist",
    "build",
    ".pytest_cache",
    ".tox",
    ".mypy_cache",
]


# ============================================================================
# 辅助函数
# ============================================================================


def format_with_ruff(target: Path, fix: bool = True) -> None:
    """使用 ruff 格式化代码.

    Parameters
    ----------
    target : Path
        目标路径
    fix : bool
        是否自动修复
    """
    cmd = ["ruff", "format", str(target)]
    if fix:
        cmd.append("--fix")

    subprocess.run(cmd, check=True)
    print(f"ruff format 完成: {target}")


def lint_with_ruff(target: Path, fix: bool = True) -> None:
    """使用 ruff 检查代码.

    Parameters
    ----------
    target : Path
        目标路径
    fix : bool
        是否自动修复
    """
    cmd = ["ruff", "check", str(target)]
    if fix:
        cmd.extend(["--fix", "--unsafe-fixes"])

    subprocess.run(cmd, check=True)
    print(f"ruff check 完成: {target}")


def add_docstring(file_path: Path, docstring: str) -> bool:
    """为文件添加 docstring.

    Parameters
    ----------
    file_path : Path
        文件路径
    docstring : str
        docstring 内容

    Returns
    -------
    bool
        是否成功添加
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        # 检查是否已有 docstring
        first_node = tree.body[0] if tree.body else None
        if first_node and isinstance(first_node, ast.Expr) and isinstance(first_node.value, ast.Constant):
            return False

        # 添加 docstring
        lines = content.splitlines()
        doc_lines = docstring.splitlines()
        doc_lines.append("")
        new_content = "\n".join(doc_lines + lines)

        file_path.write_text(new_content, encoding="utf-8")
        print(f"添加 docstring: {file_path}")
        return True

    except (OSError, UnicodeDecodeError, SyntaxError) as e:
        print(f"处理失败: {file_path} - {e}")
        return False


def generate_module_docstring(file_path: Path) -> str:
    """生成模块 docstring.

    Parameters
    ----------
    file_path : Path
        文件路径

    Returns
    -------
    str
        生成的 docstring
    """
    stem = file_path.stem
    parent = file_path.parent.name

    # 关键词匹配
    keywords = {
        "cli": f"Command-line interface for {parent}",
        "gui": f"Graphical user interface for {parent}",
        "core": f"Core functionality for {parent}",
        "util": f"Utility functions for {parent}",
        "model": f"Data models for {parent}",
        "test": f"Tests for {parent}",
    }

    for key, desc in keywords.items():
        if key in stem.lower():
            return f'"""{desc}."""'

    return f'"""{stem.replace("_", " ").title()} module."""'


def auto_add_docstrings(root_dir: Path) -> int:
    """自动为所有 Python 文件添加 docstring.

    Parameters
    ----------
    root_dir : Path
        根目录

    Returns
    -------
    int
        添加的 docstring 数量
    """
    count = 0
    for py_file in root_dir.rglob("*.py"):
        # 跳过忽略的文件
        if any(pattern in str(py_file) for pattern in IGNORE_PATTERNS):
            continue

        docstring = generate_module_docstring(py_file)
        if add_docstring(py_file, docstring):
            count += 1

    print(f"共添加 {count} 个 docstring")
    return count


def sync_pyproject_config(root_dir: Path) -> None:
    """同步 pyproject.toml 配置到子项目.

    Parameters
    ----------
    root_dir : Path
        根目录
    """
    main_toml = root_dir / "pyproject.toml"
    if not main_toml.exists():
        print(f"主项目配置文件不存在: {main_toml}")
        return

    # 查找所有子项目的 pyproject.toml
    sub_tomls = [p for p in root_dir.rglob("pyproject.toml") if p != main_toml and ".venv" not in str(p)]

    if not sub_tomls:
        print("没有找到子项目的 pyproject.toml")
        return

    print(f"找到 {len(sub_tomls)} 个子项目配置文件")

    # 对每个子项目调用 ruff format
    for sub_toml in sub_tomls:
        subprocess.run(["ruff", "format", str(sub_toml)], check=False)

    print("配置同步完成")


def format_all(root_dir: Path) -> None:
    """格式化所有 Python 文件.

    Parameters
    ----------
    root_dir : Path
        根目录
    """
    # 使用 ruff format
    subprocess.run(["ruff", "format", str(root_dir)], check=True)

    # 使用 ruff check
    subprocess.run(["ruff", "check", "--fix", "--unsafe-fixes", str(root_dir)], check=True)

    print(f"格式化完成: {root_dir}")


# ============================================================================
# TaskSpec 定义
# ============================================================================

# ruff format
ruff_format: px.TaskSpec = px.TaskSpec("ruff_format", cmd=["ruff", "format", "."])

# ruff check
ruff_check: px.TaskSpec = px.TaskSpec("ruff_check", cmd=["ruff", "check", "--fix", "--unsafe-fixes", "."])

# 自动添加 docstring
auto_docstring: px.TaskSpec = px.TaskSpec("auto_docstring", fn=lambda: auto_add_docstrings(Path()))

# 同步 pyproject.toml 配置
sync_config: px.TaskSpec = px.TaskSpec("sync_config", fn=lambda: sync_pyproject_config(Path()))

# 格式化所有文件
format_all_files: px.TaskSpec = px.TaskSpec("format_all", fn=lambda: format_all(Path()))


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """自动格式化工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="AutoFmt - 自动格式化工具",
        graphs={
            # ruff format
            "fmt": px.Graph.from_specs([ruff_format]),
            # ruff check
            "lint": px.Graph.from_specs([ruff_check]),
            # 自动添加 docstring
            "doc": px.Graph.from_specs([auto_docstring]),
            # 同步 pyproject.toml 配置
            "sync": px.Graph.from_specs([sync_config]),
            # 格式化所有文件
            "all": px.Graph.from_specs([ruff_format, ruff_check]),
        },
    )
    runner.run_cli()
