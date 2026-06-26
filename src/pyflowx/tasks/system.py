"""系统操作任务模块.

提供常用的系统操作任务封装, 包括清屏、环境变量设置、命令查找等.
"""

from __future__ import annotations

import os
import subprocess
from typing import Literal

import pyflowx as px
from pyflowx.conditions import Constants


def CLR() -> px.TaskSpec[None]:
    """清屏任务.

    跨平台清屏操作, Windows 使用 cls, Unix 使用 clear.
    任务名称: 'clear_screen'

    Returns
    -------
    px.TaskSpec[None]
        清屏任务规格.
    """
    cmd = ["cls"] if Constants.IS_WINDOWS else ["clear"]
    return px.TaskSpec("clear_screen", fn=lambda: subprocess.run(cmd, check=True))


def SETENV(name: str, value: str, *, mode: Literal["set", "default"] = "set") -> px.TaskSpec[str | None]:
    """设置环境变量任务.

    支持两种模式:
    - 'set': 强制设置环境变量 (默认)
    - 'default': 仅在不存在时设置 (setdefault)

    任务名称: 'set_env_{name}'

    Parameters
    ----------
    name : str
        环境变量名称.
    value : str
        环境变量值.
    mode : Literal["set", "default"]
        设置模式, 默认为 'set'.

    Returns
    -------
    px.TaskSpec[str | None]
        环境变量设置任务规格.
        'set' 模式返回 None, 'default' 模式返回原有值或 None.

    Examples
    --------
    强制设置::

        SETENV("PATH", "/usr/local/bin", mode="set")

    仅在不存在时设置::

        SETENV("EDITOR", "vim", mode="default")
    """

    def set_environment() -> str | None:
        """执行环境变量设置."""
        if mode == "set":
            os.environ[name] = value
            return None
        else:
            return os.environ.setdefault(name, value)

    return px.TaskSpec(f"set_env_{name}", fn=set_environment)


def WHICH(cmd: str) -> px.TaskSpec[str | None]:
    """查找命令路径任务.

    跨平台命令查找, Windows 使用 where, Unix 使用 which.
    找到命令时打印路径并返回, 找不到时打印提示并返回 None.

    任务名称: 'which_{cmd}'

    Parameters
    ----------
    cmd : str
        要查找的命令名称.

    Returns
    -------
    px.TaskSpec[str | None]
        命令查找任务规格, 返回命令路径或 None.

    Examples
    --------
    查找 python::

        WHICH("python")  # 返回路径如 "/usr/bin/python"

    找不到的命令::

        WHICH("nonexistent")  # 打印提示并返回 None
    """
    # 跨平台命令选择
    which_cmd = "where" if Constants.IS_WINDOWS else "which"

    def find_command() -> str | None:
        """执行命令查找."""
        result = subprocess.run(
            [which_cmd, cmd],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            # Windows 的 where 可能返回多行, 取第一行
            path = result.stdout.strip().split("\n")[0].strip()
            # 动态计算对齐宽度
            align_width = max(len(cmd), 8)
            print(f"{cmd:<{align_width}} -> {path}")
            return path

        # 找不到命令
        align_width = max(len(cmd), 8)
        print(f"{cmd:<{align_width}} -> 未找到")
        return None

    return px.TaskSpec(f"which_{cmd}", fn=find_command)


# 导出所有任务函数
__all__ = ["CLR", "SETENV", "WHICH"]
