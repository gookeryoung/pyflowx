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


_VERSION_PATTERN = re.compile(
    r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?",
)


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

    match = _VERSION_PATTERN.search(content)
    if not match:
        print(f"文件 {file_path} 中未找到版本号模式")
        return None

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))

    # 计算新版本号
    if part == "major":
        new_major = major + 1
        new_version_str = f"{new_major}.0.0"
    elif part == "minor":
        new_minor = minor + 1
        new_version_str = f"{major}.{new_minor}.0"
    else:  # patch
        new_patch = patch + 1
        new_version_str = f"{major}.{minor}.{new_patch}"

    content = content.replace(match.group(0), new_version_str)

    try:
        file_path.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"更新文件 {file_path} 版本号时出错: {e}")
        raise

    return new_version_str


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
            "git_commit", cmd=["git", "commit", "-m", f"bump version to {new_version}"], depends_on=["git_add"]
        ),
    ])
    px.run(graph, strategy="sequential")

    # 创建 git tag
    if not args.no_tag:
        tag_name = f"v{new_version}"
        graph = px.Graph.from_specs([
            px.TaskSpec("git_tag", cmd=["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"]),
        ])
        px.run(graph, strategy="sequential")
        print(f"已创建标签: {tag_name}")
