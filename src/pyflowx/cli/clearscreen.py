"""清屏工具.

跨平台清屏工具, 支持终端和控制台清屏.
"""

from __future__ import annotations

import pyflowx as px
from pyflowx.tasks.system import clr


def main() -> None:
    """清屏工具主函数."""
    graph = px.Graph.from_specs([clr()])
    px.run(graph, strategy="thread")
