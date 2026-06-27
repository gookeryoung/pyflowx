"""命令查找工具.

跨平台查找可执行命令路径, 类似 Unix 的 which 命令.
"""

from __future__ import annotations

import argparse

import pyflowx as px
from pyflowx.tasks.system import which


def main() -> None:
    """命令查找工具主函数."""
    parser = argparse.ArgumentParser(description="Which - 命令查找工具")
    parser.add_argument("commands", nargs="+", help="要查找的命令名称, 如: python ls ps gcc...")
    args = parser.parse_args()

    graph = px.Graph.from_specs([which(cmd) for cmd in args.commands])
    px.run(graph, strategy="thread")
