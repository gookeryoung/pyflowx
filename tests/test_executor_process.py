"""Tests for process executor (spec.executor='process')."""

from __future__ import annotations

import pytest

# pyrefly: ignore[missing-import]
from _proc_helper import add, cpu_heavy, slow_sleep, sub

import pyflowx as px
from pyflowx.errors import TaskFailedError


def test_process_executor_runs_cpu_task() -> None:
    """executor='process' 应在进程池中执行 CPU 密集型任务."""
    spec = px.TaskSpec("cpu", fn=cpu_heavy, args=(1000,), executor="process")
    graph = px.Graph.from_specs([spec])
    report = px.run(graph)
    assert report.success
    assert report["cpu"] == sum(i * i for i in range(1000))


def test_process_executor_with_dependency() -> None:
    """进程池任务应支持依赖注入."""
    spec1 = px.TaskSpec("a", fn=cpu_heavy, args=(100,), executor="process")
    spec2 = px.TaskSpec("b", fn=add, args=(3, 4), executor="process", depends_on=("a",))
    graph = px.Graph.from_specs([spec1, spec2])
    report = px.run(graph)
    assert report.success
    assert report["b"] == 7


def test_process_executor_default_is_thread() -> None:
    """TaskSpec.executor 默认应为 'thread'."""
    spec = px.TaskSpec("x", fn=lambda: None)
    assert spec.executor == "thread"


def test_inline_executor_runs_in_event_loop() -> None:
    """executor='inline' 应直接在事件循环线程调用."""
    spec = px.TaskSpec("inline", fn=add, args=(10, 20), executor="inline")
    graph = px.Graph.from_specs([spec])
    report = px.run(graph)
    assert report.success
    assert report["inline"] == 30


def test_process_executor_with_kwargs() -> None:
    """进程池任务应支持 kwargs 注入."""
    spec = px.TaskSpec("kw", fn=sub, args=(10,), kwargs={"b": 3}, executor="process")
    graph = px.Graph.from_specs([spec])
    report = px.run(graph)
    assert report.success
    assert report["kw"] == 7


def test_process_executor_timeout() -> None:
    """进程池任务超时应抛 TaskFailedError."""
    spec = px.TaskSpec("slow", fn=slow_sleep, args=(10.0,), executor="process", timeout=0.1)
    graph = px.Graph.from_specs([spec])
    with pytest.raises(TaskFailedError):
        px.run(graph)
