"""进程池测试辅助：模块级函数（须可 pickle）。"""

from __future__ import annotations

import time


def cpu_heavy(n: int) -> int:
    """CPU 密集型计算（求平方和）。"""
    return sum(i * i for i in range(n))


def add(a: int, b: int) -> int:
    """简单加法。"""
    return a + b


def sub(a: int, b: int) -> int:
    """简单减法。"""
    return a - b


def slow_sleep(seconds: float) -> int:
    """睡眠指定秒数，用于测试超时。"""
    time.sleep(seconds)
    return int(seconds)
