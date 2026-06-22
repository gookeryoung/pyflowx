"""清屏工具.

跨平台清屏工具, 支持终端和控制台清屏.
"""

from __future__ import annotations

import subprocess

import pyflowx as px
from pyflowx.conditions import Constants

# ============================================================================
# 辅助函数
# ============================================================================


def clear_screen() -> None:
    """使用系统命令清屏."""
    if Constants.IS_WINDOWS:
        subprocess.run(["cmd", "/c", "cls"], check=False)
    else:
        subprocess.run(["clear"], check=False)

    print("\033[2J\033[H", end="")
    print("ClearScreen - 清屏工具")


def main() -> None:
    """清屏工具主函数."""
    graph = px.Graph.from_specs([px.TaskSpec("clearscreen", fn=clear_screen)])
    px.run(graph, strategy="thread")
