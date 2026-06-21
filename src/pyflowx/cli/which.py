"""命令查找工具.

跨平台查找可执行命令路径, 类似 Unix 的 which 命令.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pyflowx as px


def which_command(command: str) -> Path | None:
    """查找命令路径.

    Parameters
    ----------
    command : str
        命令名称

    Returns
    -------
    Path | None
        命令路径, 如果未找到则返回 None
    """
    cmd_path = shutil.which(command)
    if cmd_path:
        print(f"匹配路径: - {cmd_path}")
        return Path(cmd_path)
    else:
        print(f"{command}: 未找到")
        return None


def main() -> None:
    """命令查找工具主函数."""
    parser = argparse.ArgumentParser(
        description="Which - 命令查找工具",
        usage="which <command> [command ...]",
    )
    parser.add_argument(
        "commands",
        type=str,
        nargs="+",
        help="要查找的命令名称 (如: python pip node npm git uv rustc cargo)",
    )
    args = parser.parse_args()
    graph = px.Graph.from_specs([px.TaskSpec(f"which_{cmd}", fn=which_command, args=(cmd,)) for cmd in args.commands])
    px.run(graph, strategy="thread")
