"""进程终止工具.

跨平台进程终止工具, 支持按名称终止进程.
用法: taskkill proc_name [proc_name ...]
"""

from __future__ import annotations

import argparse

import pyflowx as px
from pyflowx.conditions import Constants


def main() -> None:
    """进程终止工具主函数."""
    parser = argparse.ArgumentParser(
        description="TaskKill - 进程终止工具",
        usage="taskkill <process_name> [process_name ...]",
    )
    parser.add_argument(
        "process_names",
        type=str,
        nargs="+",
        help="进程名称 (如: chrome.exe python node)",
    )
    args = parser.parse_args()

    if Constants.IS_WINDOWS:
        cmd = ["taskkill", "/f", "/im"]
    else:
        cmd = ["pkill", "-f"]

    graph = px.Graph.from_specs([
        px.TaskSpec(f"kill_{proc_name}", cmd=[*cmd, f"{proc_name}*"], verbose=True) for proc_name in args.process_names
    ])
    px.run(graph, strategy="thread")
