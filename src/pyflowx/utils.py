"""常用工具函数."""

from __future__ import annotations

__all__ = ["perf_timer"]

import functools
import logging
import time
from collections import defaultdict
from typing import Callable, TypedDict

try:
    from typing_extensions import ParamSpec, TypeVar
except ImportError:
    from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


class _PerformanceMetrics(TypedDict):
    """性能指标."""

    count: int
    total_time: float


_perf_metrics: defaultdict[str, _PerformanceMetrics] = defaultdict(
    lambda: _PerformanceMetrics(
        count=0,
        total_time=0.0,
    )
)


def _generate_report(unit: str, precision: int) -> str:
    """生成性能指标报告，返回报告字符串."""
    if not _perf_metrics:
        return ""

    lines: list[str] = []
    lines.append("=" * 50)
    lines.append("性能指标报告 (Performance Metrics Report)")
    lines.append("-" * 50)

    # 按总耗时排序，最耗时的函数排在前面
    sorted_metrics = sorted(_perf_metrics.items(), key=lambda x: x[1]["total_time"], reverse=True)

    for name, metrics in sorted_metrics:
        avg_time = metrics["total_time"] / metrics["count"] if metrics["count"] > 0 else 0
        lines.append(
            f"{name}: "
            f"调用次数={metrics['count']}, "
            f"总耗时={metrics['total_time']:.{precision}f}{unit}, "
            f"平均耗时={avg_time:.{precision}f}{unit}"
        )

    lines.append("=" * 50)
    report_str = "\n".join(lines)

    # 同时输出到日志
    logging.info("\n".join(lines))

    return report_str


def perf_timer(unit: str = "ms", precision: int = 4, report: bool = False):
    """性能计时器装饰器."""
    scale: dict[str, float] = {
        "s": 1.0,
        "ms": 1000.0,
        "us": 1000000.0,
    }

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()

            _perf_metrics[func.__name__]["count"] += 1
            _perf_metrics[func.__name__]["total_time"] += (end_time - start_time) * scale[unit]

            if not report:
                logging.info(
                    f"{func.__name__} {unit}: {_perf_metrics[func.__name__]['total_time']:.{precision}f}{unit}"
                )
            return result

        return wrapper

    if report:
        import atexit

        logging.basicConfig(level=logging.INFO)
        logging.info(f"Performance metrics report enabled with unit {unit} and precision {precision}")

        @atexit.register
        def _report_at_exit() -> None:
            """在程序退出时报告性能指标."""
            _generate_report(unit, precision)

        # 将报告生成逻辑提取为独立函数，便于测试

    return decorator
