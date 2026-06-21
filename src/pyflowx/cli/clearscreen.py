"""清屏工具.

跨平台清屏工具, 支持终端和控制台清屏.
"""

from __future__ import annotations

import os
import subprocess

import pyflowx as px
from pyflowx.conditions import Constants

# ============================================================================
# 辅助函数
# ============================================================================


def clear_screen() -> None:
    """清屏."""
    if Constants.IS_WINDOWS:
        os.system("cls")
    else:
        os.system("clear")


def clear_screen_python() -> None:
    """Python 方式清屏 (跨平台)."""
    print("\033[2J\033[H", end="")


def clear_screen_cmd() -> None:
    """使用系统命令清屏."""
    if Constants.IS_WINDOWS:
        subprocess.run(["cmd", "/c", "cls"], check=False)
    else:
        subprocess.run(["clear"], check=False)


# ============================================================================
# TaskSpec 定义
# ============================================================================

clearscreen: px.TaskSpec = px.TaskSpec("clearscreen", fn=clear_screen)
clearscreen_py: px.TaskSpec = px.TaskSpec("clearscreen_py", fn=clear_screen_python)
clearscreen_cmd: px.TaskSpec = px.TaskSpec("clearscreen_cmd", fn=clear_screen_cmd)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """清屏工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="ClearScreen - 清屏工具",
        graphs={
            # 清屏 (os.system)
            "c": px.Graph.from_specs([clearscreen]),
            # 清屏 (Python)
            "p": px.Graph.from_specs([clearscreen_py]),
            # 清屏 (cmd)
            "cmd": px.Graph.from_specs([clearscreen_cmd]),
        },
    )
    runner.run_cli()
