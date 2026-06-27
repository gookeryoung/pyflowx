"""系统操作任务模块.

提供常用的系统操作任务封装, 包括清屏、环境变量设置、命令查找等.
遵循实用主义原则, 仅提供核心功能, 无过度设计.
"""

from __future__ import annotations

__all__ = [
    "clr",
    "reset_icon_cache",
    "setenv",
    "setenv_group",
    "which",
    "write_file",
]

import os
import subprocess
from pathlib import Path

import pyflowx as px
from pyflowx import BuiltinConditions
from pyflowx.conditions import Constants


def clr():
    """清屏任务."""
    cmd = ["cls"] if Constants.IS_WINDOWS else ["clear"]
    return px.TaskSpec("clear_screen", fn=lambda: subprocess.run(cmd, check=False))


def reset_icon_cache() -> list[px.TaskSpec]:
    """重置图标缓存任务."""
    if not Constants.IS_WINDOWS:
        print("reset_icon_cache: 仅在 Windows 上支持")
        return []

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    icon_cache_db = Path(local_app_data) / "IconCache.db"
    explorer_cache_dir = Path(local_app_data) / "Microsoft" / "Windows" / "Explorer"

    return [
        px.TaskSpec(
            "kill_explorer",
            cmd=["taskkill", "/f", "/im", "explorer.exe"],
            conditions=(BuiltinConditions.IS_RUNNING("explorer.exe"),),
            verbose=True,
        ),
        px.TaskSpec(
            "delete_icon_cache",
            cmd=["cmd", "/c", "del", "/a", "/q", str(icon_cache_db)],
            conditions=(BuiltinConditions.DIR_EXISTS(icon_cache_db),),
            depends_on=("kill_explorer",),
            verbose=True,
        ),
        px.TaskSpec(
            "delete_icon_cache_all",
            cmd=["cmd", "/c", "del", "/a", "/q", str(explorer_cache_dir / "iconcache*")],
            conditions=(BuiltinConditions.DIR_EXISTS(explorer_cache_dir),),
            depends_on=("kill_explorer",),
            verbose=True,
        ),
        px.TaskSpec(
            "restart_explorer",
            cmd=["cmd", "/c", "start", "explorer.exe"],
            conditions=(
                BuiltinConditions.HAS_INSTALLED("explorer.exe"),
                BuiltinConditions.NOT(BuiltinConditions.IS_RUNNING("explorer.exe")),
            ),
            depends_on=("delete_icon_cache", "delete_icon_cache_all"),
            allow_upstream_skip=True,
            verbose=True,
        ),
    ]


def setenv(name: str, value: str, default: bool = False) -> px.TaskSpec:
    """设置环境变量任务."""

    def set_env():
        if default:
            os.environ.setdefault(name, value)
        else:
            os.environ[name] = value

    return px.TaskSpec(f"setenv_{name.lower()}", fn=set_env, verbose=True)


def setenv_group(envs: dict[str, str], default: bool = False) -> list[px.TaskSpec]:
    """设置环境变量组任务."""
    return [setenv(name, value, default) for name, value in envs.items()]


def which(cmd: str) -> px.TaskSpec:
    """查找命令路径任务."""
    which_cmd = "where" if Constants.IS_WINDOWS else "which"

    def find_command():
        result = subprocess.run([which_cmd, cmd], capture_output=True, text=True, check=False)

        if result.returncode == 0:
            # Windows 的 where 可能返回多行, 取第一个
            path = result.stdout.strip().split("\n")[0].strip()
            print(f"{cmd} -> {path}")
        else:
            print(f"{cmd} -> 未找到")

    return px.TaskSpec(f"which_{cmd}", fn=find_command)


def write_file(path: str, content: str, encoding: str = "utf-8") -> px.TaskSpec:
    """写入文件任务."""

    def write():
        try:
            with open(path, "w", encoding=encoding) as f:
                f.write(content)
        except Exception as e:
            print(f"写入文件 {path} 失败: {e}")

    return px.TaskSpec(f"write_file_{path}", fn=write, verbose=True)
