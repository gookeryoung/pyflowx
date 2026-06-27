"""常用工具函数."""

__all__ = ["perf_timer"]


import functools
import logging
import time
from collections import defaultdict
from typing import Callable, ParamSpec, TypedDict

from typing_extensions import TypeVar

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
        def _() -> None:
            for name, metrics in _perf_metrics.items():
                logging.info(f"{name}: {metrics['count']} times, {metrics['total_time']:.{precision}f}{unit}")

    return decorator
