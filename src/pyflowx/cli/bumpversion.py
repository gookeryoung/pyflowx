"""版本号自动管理工具.

使用 TaskSpec 模式实现, 支持语义化版本管理和多文件格式的版本号更新.
"""

from __future__ import annotations

import subprocess

import pyflowx as px

# ============================================================================
# 辅助函数
# ============================================================================


def bump_version(part: str = "patch", tag: bool = False, commit: bool = False) -> None:
    """递增版本号.

    Parameters
    ----------
    part : str
        版本部分: patch, minor, major
    tag : bool
        是否创建 Git 标签
    commit : bool
        是否提交更改
    """
    try:
        subprocess.run(["bumpversion", part], check=True)
        if commit:
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", f"bump version {part}"], check=True)
        if tag:
            # 获取当前版本号
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                check=True,
                capture_output=True,
                text=True,
            )
            version = result.stdout.strip() if result.returncode == 0 else f"v{part}"
            subprocess.run(
                ["git", "tag", "-a", version, "-m", f"version {part}"],
                check=True,
            )
    except FileNotFoundError:
        print("未找到 bumpversion 工具，请先安装: pip install bumpversion")
        raise


def bump_version_alpha(part: str = "patch") -> None:
    """递增版本号并添加 alpha 预发布标识."""
    try:
        subprocess.run(["bumpversion", part, "--new-version", f"{part}-alpha"], check=True)
    except FileNotFoundError:
        print("未找到 bumpversion 工具，请先安装: pip install bumpversion")
        raise


# ============================================================================
# TaskSpec 定义
# ============================================================================

bump_patch: px.TaskSpec = px.TaskSpec("bump_patch", fn=lambda: bump_version("patch"))
bump_minor: px.TaskSpec = px.TaskSpec("bump_minor", fn=lambda: bump_version("minor"))
bump_major: px.TaskSpec = px.TaskSpec("bump_major", fn=lambda: bump_version("major"))
bump_patch_tag: px.TaskSpec = px.TaskSpec("bump_patch_tag", fn=lambda: bump_version("patch", tag=True))
bump_minor_tag: px.TaskSpec = px.TaskSpec("bump_minor_tag", fn=lambda: bump_version("minor", tag=True))
bump_major_tag: px.TaskSpec = px.TaskSpec("bump_major_tag", fn=lambda: bump_version("major", tag=True))
bump_patch_alpha: px.TaskSpec = px.TaskSpec("bump_patch_alpha", fn=lambda: bump_version_alpha("patch"))


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """版本号管理工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="BumpVersion - 版本号自动管理工具",
        graphs={
            # 递增补丁号 (1.0.0 -> 1.0.1)
            "p": px.Graph.from_specs([bump_patch]),
            # 递增次版本号 (1.0.0 -> 1.1.0)
            "m": px.Graph.from_specs([bump_minor]),
            # 递增主版本号 (1.0.0 -> 2.0.0)
            "M": px.Graph.from_specs([bump_major]),
            # 递增补丁号并创建标签
            "pt": px.Graph.from_specs([bump_patch_tag]),
            # 递增次版本号并创建标签
            "mt": px.Graph.from_specs([bump_minor_tag]),
            # 递增主版本号并创建标签
            "Mt": px.Graph.from_specs([bump_major_tag]),
            # 递增补丁号并添加 alpha 预发布标识
            "pa": px.Graph.from_specs([bump_patch_alpha]),
        },
    )
    runner.run_cli()
