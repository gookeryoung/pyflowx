"""清屏工具.

跨平台清屏工具, 支持终端和控制台清屏.
"""

from __future__ import annotations

import pyflowx as px
from pyflowx.conditions import Constants


def main() -> None:
    """清屏工具主函数."""
    graph = px.Graph.from_specs([
        px.TaskSpec("cls_win", cmd=["cmd", "/c", "cls"], conditions=(lambda: Constants.IS_WINDOWS,)),
        px.TaskSpec("cls_unix", cmd=["clear"], conditions=(lambda: not Constants.IS_WINDOWS,)),
        px.TaskSpec("cls_ascii", fn=lambda: print("\033[2J\033[H", end="")),
    ])
    px.run(graph, strategy="thread")
