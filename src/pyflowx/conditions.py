"""条件判断模块.

提供平台条件、应用安装条件等预定义条件判断函数,
用于 TaskSpec 的条件执行功能.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Callable

# 条件判断函数类型
Condition = Callable[[], bool]


class Constants:
    """常量定义."""

    IS_WINDOWS: bool = sys.platform == "win32"
    IS_LINUX: bool = sys.platform == "linux"
    IS_MACOS: bool = sys.platform == "darwin"
    IS_POSIX: bool = sys.platform != "win32"


class BuiltinConditions:
    """内置条件判断函数集合."""

    @staticmethod
    def PYTHON_VERSION(major: int, minor: int | None = None) -> bool:
        """检查 Python 版本是否匹配.

        Parameters
        ----------
        major : int
            主版本号.
        minor : int | None
            次版本号, 若为 None 则仅检查主版本.

        Returns
        -------
        bool
            版本是否匹配.
        """
        if minor is None:
            return sys.version_info.major == major
        return sys.version_info.major == major and sys.version_info.minor == minor

    @staticmethod
    def PYTHON_VERSION_AT_LEAST(major: int, minor: int = 0) -> bool:
        """检查 Python 版本是否 >= 指定版本.

        Parameters
        ----------
        major : int
            主版本号.
        minor : int
            次版本号.

        Returns
        -------
        bool
            当前版本是否 >= 指定版本.
        """
        return sys.version_info >= (major, minor)

    @staticmethod
    def HAS_INSTALLED(app_name: str) -> Condition:
        """检查指定应用是否已安装.

        Parameters
        ----------
        app_name : str
            应用名称 (如 "git", "python", "pytest").

        Returns
        -------
        Condition
            条件判断函数.
        """

        def _check() -> bool:
            return shutil.which(app_name) is not None

        _check.__name__ = f"HAS_INSTALLED({app_name!r})"
        return _check

    @staticmethod
    def ENV_VAR_EXISTS(var_name: str) -> Condition:
        """检查环境变量是否存在.

        Parameters
        ----------
        var_name : str
            环境变量名.

        Returns
        -------
        Condition
            条件判断函数.
        """

        def _check() -> bool:
            return var_name in os.environ

        _check.__name__ = f"ENV_VAR_EXISTS({var_name!r})"
        return _check

    @staticmethod
    def ENV_VAR_EQUALS(var_name: str, value: str) -> Condition:
        """检查环境变量是否等于指定值.

        Parameters
        ----------
        var_name : str
            环境变量名.
        value : str
            期望的值.

        Returns
        -------
        Condition
            条件判断函数.
        """

        def _check() -> bool:
            return os.environ.get(var_name) == value

        _check.__name__ = f"ENV_VAR_EQUALS({var_name!r}, {value!r})"
        return _check

    @staticmethod
    def NOT(condition: Condition) -> Condition:
        """对条件取反.

        Parameters
        ----------
        condition : Condition
            原始条件.

        Returns
        -------
        Condition
            取反后的条件.
        """

        def _check() -> bool:
            return not condition()

        _check.__name__ = f"NOT({getattr(condition, '__name__', repr(condition))})"
        return _check

    @staticmethod
    def AND(*conditions: Condition) -> Condition:
        """多个条件的逻辑与.

        Parameters
        ----------
        *conditions : Condition
            条件列表.

        Returns
        -------
        Condition
            组合条件.
        """

        def _check() -> bool:
            return all(c() for c in conditions)

        names = [getattr(c, "__name__", repr(c)) for c in conditions]
        _check.__name__ = f"AND({', '.join(names)})"
        return _check

    @staticmethod
    def OR(*conditions: Condition) -> Condition:
        """多个条件的逻辑或.

        Parameters
        ----------
        *conditions : Condition
            条件列表.

        Returns
        -------
        Condition
            组合条件.
        """

        def _check() -> bool:
            return any(c() for c in conditions)

        names = [getattr(c, "__name__", repr(c)) for c in conditions]
        _check.__name__ = f"OR({', '.join(names)})"
        return _check
