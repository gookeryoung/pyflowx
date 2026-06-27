"""系统操作任务模块.

提供常用的系统操作任务封装, 包括清屏、环境变量设置、命令查找等.
遵循实用主义原则, 仅提供核心功能, 无过度设计.
"""

from __future__ import annotations

import os
import subprocess

import pyflowx as px
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

    return [
        px.TaskSpec(
            "kill_explorer",
            fn=lambda: subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], check=False),
            verbose=True,
        ),
        px.TaskSpec(
            "delete_icon_cache",
            fn=lambda: subprocess.run(["del", "/a", "/q", r"%localappdata%\IconCache.db"], check=False),
            verbose=True,
        ),
        px.TaskSpec(
            "delete_icon_cache_all",
            fn=lambda: subprocess.run(
                ["del", "/a", "/q", r"%localappdata%\Microsoft\Windows\Explorer\iconcache*"], check=False
            ),
            verbose=True,
        ),
        px.TaskSpec(
            "restart_explorer",
            fn=lambda: subprocess.run(["cmd", "/c", "start", "explorer.exe"], check=False),
            verbose=True,
        ),
    ]


def setenv(name: str, value: str, default: bool = False):
    """设置环境变量任务."""

    def set_env():
        if default:
            os.environ.setdefault(name, value)
        else:
            os.environ[name] = value

    return px.TaskSpec(f"setenv_{name.lower()}", fn=set_env, verbose=True)


def which(cmd: str):
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


__all__ = ["clr", "setenv", "which"]
