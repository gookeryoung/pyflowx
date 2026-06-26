"""版本号自动管理工具.

使用 TaskSpec 模式实现, 支持语义化版本管理和多文件格式的版本号更新.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Literal, get_args

import pyflowx as px

BumpVersionType = Literal["patch", "minor", "major"]

# 针对不同文件类型的版本号匹配模式
# pyproject.toml: version = "X.Y.Z" 或 version = 'X.Y.Z'
_PYPROJECT_VERSION_PATTERN = re.compile(
    r'(?:^|\n)\s*version\s*=\s*["\']'
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    r'["\']',
    re.MULTILINE,
)

# __init__.py: __version__ = "X.Y.Z" 或 __version__ = 'X.Y.Z'
_INIT_VERSION_PATTERN = re.compile(
    r'(?:^|\n)\s*__version__\s*=\s*["\']'
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    r'["\']',
    re.MULTILINE,
)


def _get_pattern_for_file(file_name: str) -> re.Pattern[str] | None:
    """根据文件类型获取对应的正则表达式.

    Parameters
    ----------
    file_name : str
        文件名

    Returns
    -------
    re.Pattern[str] | None
        对应的正则表达式，如果无法确定则返回 None
    """
    if file_name == "pyproject.toml":
        return _PYPROJECT_VERSION_PATTERN
    if file_name == "__init__.py":
        return _INIT_VERSION_PATTERN
    return None


def _calculate_new_version(major: int, minor: int, patch: int, part: BumpVersionType) -> str:
    """计算新版本号.

    Parameters
    ----------
    major : int
        当前主版本号
    minor : int
        当前次版本号
    patch : int
        当前补丁版本号
    part : BumpVersionType
        要更新的部分

    Returns
    -------
    str
        新版本号
    """
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _build_replacement_string(original_match: str, new_version: str, file_name: str) -> str:
    """构建替换字符串，保留原始格式.

    Parameters
    ----------
    original_match : str
        原始匹配的字符串
    new_version : str
        新版本号
    file_name : str
        文件名

    Returns
    -------
    str
        替换字符串
    """
    quote_char = '"' if '"' in original_match else "'"

    if file_name == "pyproject.toml":
        prefix_match = re.match(r'(\s*version\s*=\s*)["\']', original_match)
        prefix = prefix_match.group(1) if prefix_match else "version = "
        return f"{prefix}{quote_char}{new_version}{quote_char}"

    if file_name == "__init__.py":
        prefix_match = re.match(r'(\s*__version__\s*=\s*)["\']', original_match)
        prefix = prefix_match.group(1) if prefix_match else "__version__ = "
        return f"{prefix}{quote_char}{new_version}{quote_char}"

    return new_version


def bump_file_version(file_path: Path, part: BumpVersionType = "patch") -> str | None:
    """更新文件中的版本号.

    Parameters
    ----------
    file_path : Path
        要更新的文件路径
    part : BumpVersionType
        版本部分: patch, minor, major

    Returns
    -------
    str | None
        更新后的新版本号，如果文件中未找到版本号则返回 None
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"读取文件 {file_path} 时出错: {e}")
        raise

    # 获取文件对应的正则表达式
    pattern = _get_pattern_for_file(file_path.name)

    # 对于未知文件类型，尝试两种模式
    if pattern:
        match = pattern.search(content)
    else:
        match = _PYPROJECT_VERSION_PATTERN.search(content) or _INIT_VERSION_PATTERN.search(content)

    if not match:
        print(f"文件 {file_path} 中未找到版本号模式")
        return None

    # 提取当前版本号
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))

    # 计算新版本号
    new_version = _calculate_new_version(major, minor, patch, part)

    # 构建替换字符串
    original_match = match.group(0)
    replacement = _build_replacement_string(original_match, new_version, file_path.name)

    # 更新文件内容
    content = content.replace(original_match, replacement)

    try:
        file_path.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"更新文件 {file_path} 版本号时出错: {e}")
        raise

    return new_version


def main() -> None:
    """版本号管理工具主函数."""
    parser = argparse.ArgumentParser(description="BumpVersion - 版本号自动管理工具")
    parser.add_argument(
        "part",
        type=str,
        nargs="?",
        default="patch",
        choices=get_args(BumpVersionType),
        help=f"版本部分: {get_args(BumpVersionType)}",
    )
    parser.add_argument(
        "--no-tag",
        action="store_true",
        help="提交后不创建 git tag",
    )

    args = parser.parse_args()
    part = args.part

    # 搜索文件，排除常见的虚拟环境和缓存目录
    ignore_dirs = {".venv", "venv", ".git", "__pycache__", ".tox", "node_modules", "build", "dist", ".eggs"}
    all_files = set()

    for pattern in ["__init__.py", "pyproject.toml"]:
        for file in Path.cwd().rglob(pattern):
            # 检查路径中是否包含需要忽略的目录
            if not any(ignore_dir in file.parts for ignore_dir in ignore_dirs):
                all_files.add(file)

    if not all_files:
        print("未找到包含版本号的文件")
        return

    print(f"找到 {len(all_files)} 个文件需要更新版本号")
    for file in sorted(all_files):
        print(f"  - {file.relative_to(Path.cwd())}")

    # 更新所有文件的版本号（使用顺序执行避免竞争条件）
    # 使用相对于 cwd 的路径作为任务名，确保唯一性
    graph = px.Graph.from_specs([
        px.TaskSpec(
            f"bump_{file.relative_to(Path.cwd())}".replace("\\", "_").replace("/", "_").replace(".", "_"),
            fn=bump_file_version,
            args=(file, part),
        )
        for file in all_files
    ])
    report = px.run(graph, strategy="sequential")

    # 收集新版本号（取第一个成功的结果）
    new_version = None
    for task_name in report:
        result = report[task_name]
        if result is not None:
            new_version = result
            break

    if not new_version:
        print("未能获取新版本号")
        return

    print(f"版本号已更新为: {new_version}")

    # 提交修改
    graph = px.Graph.from_specs([
        px.TaskSpec("git_add", cmd=["git", "add", "."]),
        px.TaskSpec(
            "git_commit",
            cmd=["git", "commit", "-m", f"bump version to {new_version}"],
            depends_on=("git_add",),
        ),
    ])
    px.run(graph, strategy="sequential")

    # 创建 git tag
    if not args.no_tag:
        tag_name = f"v{new_version}"
        graph = px.Graph.from_specs([
            px.TaskSpec(
                "git_tag",
                cmd=["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"],
                depends_on=("git_commit",),
            ),
        ])
        px.run(graph, strategy="sequential")
        print(f"已创建标签: {tag_name}")
