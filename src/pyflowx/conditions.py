"""条件判断模块.

所有条件均为 ``Callable[[Context], bool]``，接收依赖上下文映射（可能为空）。
这使得条件可基于上游任务的运行时返回值做决策，实现动态分支。

内置条件分两类：
1. *静态条件* —— 不依赖上下文（平台/环境变量/安装检查），通过 ``_static``
   包装忽略传入的 context，便于作为模块级常量使用。
2. *上下文条件* —— 基于上游结果判断，如 :meth:`BuiltinConditions.DEP_EQUALS`。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .task import Condition, Context

logger = logging.getLogger(__name__)

__all__ = ["BuiltinConditions", "Condition", "Constants"]


class Constants:
    """常量定义."""

    IS_WINDOWS: bool = sys.platform == "win32"
    IS_LINUX: bool = sys.platform == "linux"
    IS_MACOS: bool = sys.platform == "darwin"
    IS_POSIX: bool = sys.platform != "win32"


def _static(predicate: Callable[[], bool], name: str) -> Condition:
    """将无参谓词包装为忽略上下文的 :class:`Condition`。"""

    def _cond(_ctx: Context) -> bool:
        return predicate()

    _cond.__name__ = name
    return _cond


def _cond_name(cond: Condition) -> str:
    """获取条件的可读名称。"""
    return getattr(cond, "__name__", repr(cond))


# ---------------------------------------------------------------------- #
# 模块级静态条件常量
# ---------------------------------------------------------------------- #
IS_WINDOWS: Condition = _static(lambda: Constants.IS_WINDOWS, "IS_WINDOWS")
IS_LINUX: Condition = _static(lambda: Constants.IS_LINUX, "IS_LINUX")
IS_MACOS: Condition = _static(lambda: Constants.IS_MACOS, "IS_MACOS")
IS_POSIX: Condition = _static(lambda: Constants.IS_POSIX, "IS_POSIX")


class BuiltinConditions:
    """内置条件判断函数集合.

    静态条件工厂返回忽略上下文的 :class:`Condition`；上下文条件工厂返回
    会读取依赖结果的 :class:`Condition`。
    """

    # ------------------------------------------------------------------ #
    # 静态条件
    # ------------------------------------------------------------------ #
    @staticmethod
    def IS_WINDOWS() -> Condition:
        """检查是否为 Windows 平台."""
        return IS_WINDOWS

    @staticmethod
    def IS_LINUX() -> Condition:
        """检查是否为 Linux 平台."""
        return IS_LINUX

    @staticmethod
    def IS_MACOS() -> Condition:
        """检查是否为 macOS 平台."""
        return IS_MACOS

    @staticmethod
    def IS_POSIX() -> Condition:
        """检查是否为 POSIX 平台."""
        return IS_POSIX

    @staticmethod
    def PYTHON_VERSION(major: int, minor: int | None = None) -> Condition:
        """检查 Python 版本是否匹配."""
        if minor is None:
            return _static(lambda: sys.version_info.major == major, f"PYTHON_VERSION({major})")
        return _static(
            lambda: sys.version_info.major == major and sys.version_info.minor == minor,
            f"PYTHON_VERSION({major},{minor})",
        )

    @staticmethod
    def PYTHON_VERSION_AT_LEAST(major: int, minor: int = 0) -> Condition:
        """检查 Python 版本是否 >= 指定版本."""
        return _static(lambda: sys.version_info >= (major, minor), f"PYTHON_VERSION_AT_LEAST({major},{minor})")

    @staticmethod
    def IS_RUNNING(app_name: str) -> Condition:
        """检查指定应用是否正在运行."""

        def _check() -> bool:
            if Constants.IS_WINDOWS:
                result = subprocess.run(
                    ["tasklist", "/nh", "/fi", f"imagename eq {app_name}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return app_name.lower() in result.stdout.lower()
            else:
                result = subprocess.run(["pgrep", "-x", app_name], capture_output=True, check=False)
                return result.returncode == 0

        return _static(_check, f"IS_RUNNING({app_name!r})")

    @staticmethod
    def HAS_INSTALLED(app_name: str) -> Condition:
        """检查指定应用是否已安装."""
        return _static(lambda: shutil.which(app_name) is not None, f"HAS_INSTALLED({app_name!r})")

    @staticmethod
    def DIR_EXISTS(path: Path) -> Condition:
        """路径是否存在."""
        return _static(path.exists, f"DIR_EXISTS({path!r})")

    @staticmethod
    def ENV_VAR_EXISTS(var_name: str) -> Condition:
        """检查环境变量是否存在."""
        return _static(lambda: var_name in os.environ, f"ENV_VAR_EXISTS({var_name!r})")

    @staticmethod
    def ENV_VAR_EQUALS(var_name: str, value: str) -> Condition:
        """检查环境变量是否等于指定值."""
        return _static(
            lambda: os.environ.get(var_name) == value,
            f"ENV_VAR_EQUALS({var_name!r},{value!r})",
        )

    @staticmethod
    def FILE_CONTENT_EXISTS(path: Path | str, content: str) -> Condition:
        """检查文件是否包含指定内容."""

        def _check() -> bool:
            p = Path(path)
            if not p.exists():
                return False
            try:
                return content in p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return False

        return _static(_check, f"FILE_CONTENT_EXISTS({path!r},{content!r})")

    # ------------------------------------------------------------------ #
    # 上下文条件：基于上游依赖结果
    # ------------------------------------------------------------------ #
    @staticmethod
    def DEP_EQUALS(dep_name: str, value: Any) -> Condition:
        """上游任务 ``dep_name`` 的返回值等于 ``value`` 时为真。

        若依赖未在上下文中（被跳过或未执行），返回 ``False``。
        """

        def _cond(ctx: Context) -> bool:
            return dep_name in ctx and ctx[dep_name] == value

        _cond.__name__ = f"DEP_EQUALS({dep_name!r},{value!r})"
        return _cond

    @staticmethod
    def DEP_MATCHES(dep_name: str, predicate: Callable[[Any], bool]) -> Condition:
        """上游任务 ``dep_name`` 的返回值满足 ``predicate`` 时为真。

        依赖不存在时返回 ``False``。
        """

        def _cond(ctx: Context) -> bool:
            if dep_name not in ctx:
                return False
            try:
                return predicate(ctx[dep_name])
            except Exception as exc:
                logger.warning("DEP_MATCHES predicate %r raised: %r", dep_name, exc)
                return False

        _cond.__name__ = f"DEP_MATCHES({dep_name!r},{getattr(predicate, '__name__', 'pred')})"
        return _cond

    @staticmethod
    def DEP_PRESENT(dep_name: str) -> Condition:
        """上游任务 ``dep_name`` 存在于上下文（即已成功执行）时为真。"""

        def _cond(ctx: Context) -> bool:
            return dep_name in ctx and ctx[dep_name] is not None

        _cond.__name__ = f"DEP_PRESENT({dep_name!r})"
        return _cond

    @staticmethod
    def DEP_TRUTHY(dep_name: str) -> Condition:
        """上游任务 ``dep_name`` 的返回值为真值时为真。"""

        def _cond(ctx: Context) -> bool:
            return bool(ctx.get(dep_name))

        _cond.__name__ = f"DEP_TRUTHY({dep_name!r})"
        return _cond

    # ------------------------------------------------------------------ #
    # 逻辑组合
    # ------------------------------------------------------------------ #
    @staticmethod
    def NOT(condition: Condition) -> Condition:
        """对条件取反."""

        def _cond(ctx: Context) -> bool:
            return not condition(ctx)

        _cond.__name__ = f"NOT({_cond_name(condition)})"
        return _cond

    @staticmethod
    def AND(*conditions: Condition) -> Condition:
        """多个条件的逻辑与."""

        def _cond(ctx: Context) -> bool:
            return all(c(ctx) for c in conditions)

        _cond.__name__ = f"AND({', '.join(_cond_name(c) for c in conditions)})"
        return _cond

    @staticmethod
    def OR(*conditions: Condition) -> Condition:
        """多个条件的逻辑或."""

        def _cond(ctx: Context) -> bool:
            return any(c(ctx) for c in conditions)

        _cond.__name__ = f"OR({', '.join(_cond_name(c) for c in conditions)})"
        return _cond
