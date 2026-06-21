"""命令查找工具.

跨平台查找可执行命令路径, 类似 Unix 的 which 命令.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pyflowx as px
from pyflowx.conditions import Constants

# ============================================================================
# 辅助函数
# ============================================================================


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
    return Path(cmd_path) if cmd_path else None


def which_all_commands(commands: list[str]) -> dict[str, Path | None]:
    """查找多个命令路径.

    Parameters
    ----------
    commands : list[str]
        命令名称列表

    Returns
    -------
    dict[str, Path | None]
        命令路径字典
    """
    results: dict[str, Path | None] = {}
    for cmd in commands:
        results[cmd] = which_command(cmd)
    return results


def where_command_windows(command: str) -> list[Path]:
    """Windows 下使用 where 命令查找所有匹配路径.

    Parameters
    ----------
    command : str
        命令名称

    Returns
    -------
    list[Path]
        匹配的路径列表
    """
    if not Constants.IS_WINDOWS:
        return []

    try:
        result = subprocess.run(
            ["where", command],
            capture_output=True,
            text=True,
            check=True,
        )
        paths = [Path(line.strip()) for line in result.stdout.strip().split("\n") if line.strip()]
        return paths
    except subprocess.CalledProcessError:
        return []


def print_command_info(command: str) -> None:
    """打印命令信息.

    Parameters
    ----------
    command : str
        命令名称
    """
    cmd_path = which_command(command)
    if cmd_path:
        print(f"{command}: {cmd_path}")
        if Constants.IS_WINDOWS:
            all_paths = where_command_windows(command)
            if len(all_paths) > 1:
                print("所有匹配路径:")
                for path in all_paths:
                    print(f"  {path}")
    else:
        print(f"{command}: 未找到")


# ============================================================================
# TaskSpec 定义
# ============================================================================

which_python: px.TaskSpec = px.TaskSpec("which_python", fn=lambda: print_command_info("python"))
which_pip: px.TaskSpec = px.TaskSpec("which_pip", fn=lambda: print_command_info("pip"))
which_node: px.TaskSpec = px.TaskSpec("which_node", fn=lambda: print_command_info("node"))
which_npm: px.TaskSpec = px.TaskSpec("which_npm", fn=lambda: print_command_info("npm"))
which_git: px.TaskSpec = px.TaskSpec("which_git", fn=lambda: print_command_info("git"))
which_uv: px.TaskSpec = px.TaskSpec("which_uv", fn=lambda: print_command_info("uv"))
which_rustc: px.TaskSpec = px.TaskSpec("which_rustc", fn=lambda: print_command_info("rustc"))
which_cargo: px.TaskSpec = px.TaskSpec("which_cargo", fn=lambda: print_command_info("cargo"))


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """命令查找工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="Which - 命令查找工具",
        graphs={
            # 查找 python
            "py": px.Graph.from_specs([which_python]),
            # 查找 pip
            "pip": px.Graph.from_specs([which_pip]),
            # 查找 node
            "node": px.Graph.from_specs([which_node]),
            # 查找 npm
            "npm": px.Graph.from_specs([which_npm]),
            # 查找 git
            "git": px.Graph.from_specs([which_git]),
            # 查找 uv
            "uv": px.Graph.from_specs([which_uv]),
            # 查找 rustc
            "rustc": px.Graph.from_specs([which_rustc]),
            # 查找 cargo
            "cargo": px.Graph.from_specs([which_cargo]),
        },
    )
    runner.run_cli()
