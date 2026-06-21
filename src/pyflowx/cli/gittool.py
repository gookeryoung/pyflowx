"""Git 工具模块.

提供 Git 仓库管理的常用操作封装,
支持初始化、提交、清理、推送等功能.
"""

from __future__ import annotations

from pathlib import Path

import pyflowx as px

EXCLUDE_DIRS = [
    # 编辑器相关目录
    ".vscode",
    ".idea",
    ".editorconfig",
    ".trae",
    ".qoder",
    # 项目相关目录
    ".venv",
    ".git",
    ".tox",
    "node_modules",
]
EXCLUDE_CMDS = [arg for d in EXCLUDE_DIRS for arg in ["-e", d]]


def init_sub_dirs() -> None:
    """初始化子目录的Git仓库."""
    sub_dirs = [subdir for subdir in Path.cwd().iterdir() if subdir.is_dir()]
    for subdir in sub_dirs:
        px.run(
            px.Graph.from_specs(
                [
                    px.TaskSpec(
                        "init",
                        cmd=["git", "init"],
                        conditions=[not_has_git_repo],
                        cwd=str(subdir),
                    ),
                    px.TaskSpec("add", cmd=["git", "add", "."], depends_on=["init"], cwd=str(subdir)),
                    px.TaskSpec(
                        "commit", cmd=["git", "commit", "-m", "init commit"], depends_on=["add"], cwd=str(subdir)
                    ),
                ]
            ),
        )


isub: px.TaskSpec = px.TaskSpec("isub", fn=init_sub_dirs)
push: px.TaskSpec = px.TaskSpec("push", cmd=["git", "push"])
pull: px.TaskSpec = px.TaskSpec("pull", cmd=["git", "pull"])
kill_tgit: px.TaskSpec = px.TaskSpec("task_kill", cmd=["taskkill", "/f", "/t", "/im", "tgitcache.exe"])


def not_has_git_repo() -> bool:
    """检查当前目录没有Git仓库."""
    return not Path.cwd().exists() or not (Path.cwd() / ".git").is_dir()


def has_files() -> bool:
    """检查当前目录是否有文件."""
    return bool(list(Path.cwd().glob("*")))


def main() -> None:
    """Git工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="Gittool - Git 执行工具.",
        graphs={
            # 添加并提交
            "a": px.Graph.from_specs(
                [
                    px.TaskSpec("add", cmd=["git", "add", "."], conditions=[has_files]),
                    px.TaskSpec("commit", cmd=["git", "commit", "-m", "chore: update"], depends_on=["add"]),
                ]
            ),
            # 清理
            "c": px.Graph.from_specs(
                [
                    px.TaskSpec("clean", cmd=["git", "clean", "-xfd", *EXCLUDE_CMDS]),
                    px.TaskSpec("status", cmd=["git", "status", "--porcelain"], depends_on=["clean"]),
                ]
            ),
            # 初始化、添加并提交
            "i": px.Graph.from_specs(
                [
                    px.TaskSpec("init", cmd=["git", "init"], conditions=[not_has_git_repo]),
                    px.TaskSpec("add", cmd=["git", "add", "."], depends_on=["init"], conditions=[has_files]),
                    px.TaskSpec(
                        "commit", cmd=["git", "commit", "-m", "init commit"], depends_on=["add"], conditions=[has_files]
                    ),
                ]
            ),
            # 初始化子目录
            "isub": px.Graph.from_specs([isub]),
            # 推送
            "p": px.Graph.from_specs([push]),
            # 拉取
            "pl": px.Graph.from_specs([pull]),
            # 重启TGit缓存
            "r": px.Graph.from_specs([kill_tgit]),
        },
    )
    runner.run_cli()
