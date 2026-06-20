"""RunReport 测试。"""

from __future__ import annotations

from datetime import datetime

import pyflowx as px
from pyflowx.task import TaskResult, TaskSpec, TaskStatus


def _fn() -> int:
    return 1


def _make_result(
    name: str = "a",
    status: TaskStatus = TaskStatus.SUCCESS,
    value: object = 42,
    error: object = None,
    duration: float = 0.5,
    attempts: int = 1,
) -> TaskResult[object]:
    spec: TaskSpec[object] = TaskSpec(name, _fn)  # type: ignore[arg-type]
    start = datetime(2024, 1, 1, 0, 0, 0)
    # 用 timedelta 精确表达秒数，避免 int() 截断小数
    from datetime import timedelta

    end = start + timedelta(seconds=duration) if duration else None
    return TaskResult(
        spec=spec,
        status=status,
        value=value,  # type: ignore[arg-type]
        error=error,  # type: ignore[arg-type]
        attempts=attempts,
        started_at=start,
        finished_at=end,
    )


def test_getitem_returns_value() -> None:
    report = px.RunReport()
    report.results["a"] = _make_result("a", value=7)
    assert report["a"] == 7


def test_result_of_returns_full_result() -> None:
    report = px.RunReport()
    r = _make_result("a")
    report.results["a"] = r
    assert report.result_of("a") is r


def test_contains() -> None:
    report = px.RunReport()
    report.results["a"] = _make_result("a")
    assert "a" in report
    assert "b" not in report


def test_iter_and_len() -> None:
    report = px.RunReport()
    report.results["a"] = _make_result("a")
    report.results["b"] = _make_result("b")
    assert list(report) == ["a", "b"]
    assert len(report) == 2


def test_summary_success() -> None:
    report = px.RunReport()
    report.results["a"] = _make_result("a", status=TaskStatus.SUCCESS, duration=1.0)
    report.results["b"] = _make_result("b", status=TaskStatus.SKIPPED, duration=0.0)
    s = report.summary()
    assert s["success"] is True
    assert s["total_tasks"] == 2
    assert s["by_status"] == {"success": 1, "skipped": 1}
    assert s["total_duration_seconds"] == 1.0


def test_summary_with_none_duration() -> None:
    """未开始/未结束的任务 duration 为 None，不应计入总时长。"""
    report = px.RunReport()
    spec: TaskSpec[object] = TaskSpec("a", _fn)  # type: ignore[arg-type]
    report.results["a"] = TaskResult(spec=spec, status=TaskStatus.FAILED)
    s = report.summary()
    assert s["total_duration_seconds"] == 0.0


def test_failed_tasks() -> None:
    report = px.RunReport()
    report.results["a"] = _make_result("a", status=TaskStatus.SUCCESS)
    report.results["b"] = _make_result(
        "b", status=TaskStatus.FAILED, error=ValueError("x")
    )
    assert report.failed_tasks() == ["b"]


def test_describe_success() -> None:
    report = px.RunReport()
    report.results["a"] = _make_result("a", status=TaskStatus.SUCCESS, duration=0.5)
    desc = report.describe()
    assert "RunReport(success=True)" in desc
    assert "a: success" in desc
    assert "0.500s" in desc


def test_describe_with_error() -> None:
    report = px.RunReport(success=False)
    report.results["a"] = _make_result(
        "a", status=TaskStatus.FAILED, error=ValueError("boom"), duration=0.1
    )
    desc = report.describe()
    assert "success=False" in desc
    assert "error=ValueError" in desc


def test_describe_no_duration() -> None:
    report = px.RunReport()
    spec: TaskSpec[object] = TaskSpec("a", _fn)  # type: ignore[arg-type]
    report.results["a"] = TaskResult(spec=spec, status=TaskStatus.PENDING)
    desc = report.describe()
    assert "-" in desc  # duration 显示为 "-"
