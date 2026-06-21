"""Git 工具模块.

提供 Git 仓库管理的常用操作封装,
支持初始化、提交、清理、推送等功能.
"""

from __future__ import annotations

from pathlib import Path

import pyflowx as px


def init_sub_dirs() -> None:
    """初始化子目录的Git仓库."""
    sub_dirs = [subdir for subdir in Path.cwd().iterdir() if subdir.is_dir()]
    for subdir in sub_dirs:
        px.run(
            px.Graph.from_specs(
                [
                    px.TaskSpec("init", cmd=["git", "init"], cwd=str(subdir)),
                    px.TaskSpec("add", cmd=["git", "add", "."], depends_on=["init"], cwd=str(subdir)),
                    px.TaskSpec(
                        "commit", cmd=["git", "commit", "-m", "init commit"], depends_on=["add"], cwd=str(subdir)
                    ),
                ]
            ),
            verbose=True,
        )


push: px.TaskSpec = px.TaskSpec("push", cmd=["git", "push"])
pull: px.TaskSpec = px.TaskSpec("pull", cmd=["git", "pull"])
kill_tgit: px.TaskSpec = px.TaskSpec("task_kill", cmd=["taskkill", "/f", "/t", "/im", "tgitcache.exe"])


def main() -> None:
    """Git工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="Gittool - Git 执行工具.",
        graphs={
            "isub": px.Graph.from_specs([px.TaskSpec("isub", fn=init_sub_dirs)]),
            "p": px.Graph.from_specs([push]),
            "pl": px.Graph.from_specs([pull]),
            "r": px.Graph.from_specs([kill_tgit]),
        },
    )
    runner.run_cli()
