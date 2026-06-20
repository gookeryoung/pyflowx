"""TaskSpec / TaskResult 数据结构测试。"""

from __future__ import annotations

from datetime import datetime

import pytest

from pyflowx.task import TaskResult, TaskSpec, TaskStatus


def _fn() -> None:
    return None


def test_spec_empty_name_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        TaskSpec("", _fn)


def test_spec_negative_retries_rejected() -> None:
    with pytest.raises(ValueError, match="retries"):
        TaskSpec("a", _fn, retries=-1)


def test_spec_zero_timeout_rejected() -> None:
    with pytest.raises(ValueError, match="timeout"):
        TaskSpec("a", _fn, timeout=0)


def test_spec_self_dependency_rejected() -> None:
    with pytest.raises(ValueError, match="depend on itself"):
        TaskSpec("a", _fn, depends_on=("a",))


def test_task_result_duration_none_when_not_started() -> None:
    spec: TaskSpec[None] = TaskSpec("a", _fn)
    result: TaskResult[None] = TaskResult(spec=spec)
    assert result.duration is None


def test_task_result_duration_when_partial() -> None:
    spec: TaskSpec[None] = TaskSpec("a", _fn)
    result: TaskResult[None] = TaskResult(spec=spec, started_at=datetime.now())
    # started_at 已设但 finished_at 未设 -> None
    assert result.duration is None


def test_task_result_duration_computed() -> None:
    spec: TaskSpec[None] = TaskSpec("a", _fn)
    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 1, 0, 0, 5)
    result: TaskResult[None] = TaskResult(spec=spec, started_at=start, finished_at=end)
    assert result.duration == 5.0


def test_task_result_default_status() -> None:
    spec: TaskSpec[None] = TaskSpec("a", _fn)
    result: TaskResult[None] = TaskResult(spec=spec)
    assert result.status == TaskStatus.PENDING
    assert result.value is None
    assert result.error is None
    assert result.attempts == 0
