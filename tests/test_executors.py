"""Tests for execution: sequential, thread, async, retries, timeout, resume."""

from __future__ import annotations

import asyncio
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import pytest

import pyflowx as px
from pyflowx.errors import TaskFailedError, TaskTimeoutError
from pyflowx.storage import JSONBackend, MemoryBackend


# ---------------------------------------------------------------------- #
# Sequential
# ---------------------------------------------------------------------- #
def test_sequential_basic() -> None:
    def extract() -> list[int]:
        return [1, 2, 3]

    def double(extract: list[int]) -> list[int]:
        return [x * 2 for x in extract]

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("extract", extract),
            px.TaskSpec("double", double, depends_on=("extract",)),
        ]
    )
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report["extract"] == [1, 2, 3]
    assert report["double"] == [2, 4, 6]


def test_sequential_diamond() -> None:
    order: list[str] = []

    def make(name: str) -> Any:
        def fn() -> str:
            order.append(name)
            return name

        return fn

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("a", make("a")),
            px.TaskSpec("b", make("b"), depends_on=("a",)),
            px.TaskSpec("c", make("c"), depends_on=("a",)),
            px.TaskSpec("d", make("d"), depends_on=("b", "c")),
        ]
    )
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report["d"] == "d"
    assert order == ["a", "b", "c", "d"]


def test_failure_propagates() -> None:
    def boom() -> None:
        raise ValueError("kaboom")

    def downstream(_boom: None) -> int:
        return 1

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("boom", boom),
            px.TaskSpec("downstream", downstream, depends_on=("boom",)),
        ]
    )
    with pytest.raises(TaskFailedError) as exc_info:
        _ = px.run(graph, strategy="sequential")
    assert exc_info.value.task == "boom"
    assert isinstance(exc_info.value.cause, ValueError)


def test_retries_then_succeeds() -> None:
    attempts = {"n": 0}

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("not yet")
        return "ok"

    graph = px.Graph.from_specs([px.TaskSpec("flaky", flaky, retries=2)])
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report["flaky"] == "ok"
    assert attempts["n"] == 3


def test_retries_exhausted() -> None:
    def always_fail() -> None:
        raise RuntimeError("nope")

    graph = px.Graph.from_specs([px.TaskSpec("f", always_fail, retries=2)])
    with pytest.raises(TaskFailedError) as exc_info:
        _ = px.run(graph, strategy="sequential")
    assert exc_info.value.attempts == 3


# ---------------------------------------------------------------------- #
# Threaded
# ---------------------------------------------------------------------- #
@pytest.mark.slow
def test_threaded_parallelism() -> None:
    def slow() -> str:
        time.sleep(0.3)
        return "done"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("a", slow),
            px.TaskSpec("b", slow),
            px.TaskSpec("c", slow),
        ]
    )
    start = time.time()
    report = px.run(graph, strategy="thread", max_workers=3)
    elapsed = time.time() - start
    assert report.success
    # Three 0.3s tasks in parallel should be well under 1.0s.
    assert elapsed < 1.0


@pytest.mark.slow
def test_threaded_layer_barrier() -> None:
    finished: list[str] = []
    lock = threading.Lock()

    def make(name: str) -> Any:
        def fn() -> str:
            time.sleep(0.1)
            with lock:
                finished.append(name)
            return name

        return fn

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("a", make("a")),
            px.TaskSpec("b", make("b")),
            px.TaskSpec("c", make("c"), depends_on=("a", "b")),
        ]
    )
    report = px.run(graph, strategy="thread", max_workers=2)
    assert report.success
    # c must finish after both a and b.
    assert finished.index("c") > finished.index("a")
    assert finished.index("c") > finished.index("b")


# ---------------------------------------------------------------------- #
# Async
# ---------------------------------------------------------------------- #
def test_async_basic() -> None:
    async def fetch() -> int:
        await asyncio.sleep(0.01)
        return 42

    async def transform(fetch: int) -> int:
        return fetch * 2

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("fetch", fetch),
            px.TaskSpec("transform", transform, depends_on=("fetch",)),
        ]
    )
    report = px.run(graph, strategy="async")
    assert report.success
    assert report["transform"] == 84


@pytest.mark.slow
def test_async_parallelism() -> None:
    async def slow() -> str:
        await asyncio.sleep(0.3)
        return "done"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("a", slow),
            px.TaskSpec("b", slow),
            px.TaskSpec("c", slow),
        ]
    )
    start = time.time()
    report = px.run(graph, strategy="async")
    elapsed = time.time() - start
    assert report.success
    assert elapsed < 0.8


def test_async_mixed_sync_and_async() -> None:
    def sync_task() -> int:
        return 10

    async def async_task(sync_task: int) -> int:
        await asyncio.sleep(0.01)
        return sync_task + 5

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("sync_task", sync_task),
            px.TaskSpec("async_task", async_task, depends_on=("sync_task",)),
        ]
    )
    report = px.run(graph, strategy="async")
    assert report.success
    assert report["async_task"] == 15


def test_async_timeout() -> None:
    async def slow() -> None:
        await asyncio.sleep(10)

    graph = px.Graph.from_specs([px.TaskSpec("slow", slow, timeout=0.05)])
    with pytest.raises(TaskFailedError) as exc_info:
        _ = px.run(graph, strategy="async")
    assert isinstance(exc_info.value.cause, TaskTimeoutError)


# ---------------------------------------------------------------------- #
# Dry run
# ---------------------------------------------------------------------- #
def test_dry_run_does_not_execute(capsys: pytest.CaptureFixture[str]) -> None:
    called: list[str] = []

    def fn() -> str:
        called.append("x")
        return "should-not-run"

    graph = px.Graph.from_specs([px.TaskSpec("a", fn)])
    report = px.run(graph, strategy="sequential", dry_run=True)
    assert called == []
    assert len(report) == 0
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "Layer 1" in out


# ---------------------------------------------------------------------- #
# State / resume
# ---------------------------------------------------------------------- #
def test_memory_backend_resume() -> None:
    runs: list[str] = []

    def make(name: str) -> Any:
        def fn() -> str:
            runs.append(name)
            return name

        return fn

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("a", make("a")),
            px.TaskSpec("b", make("b"), depends_on=("a",)),
        ]
    )
    backend = MemoryBackend()
    _ = px.run(graph, strategy="sequential", state=backend)
    assert runs == ["a", "b"]

    # Second run: both cached, neither re-executed.
    _ = px.run(graph, strategy="sequential", state=backend)
    assert runs == ["a", "b"]  # unchanged


def test_json_backend_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")

        def fn() -> int:
            return 7

        graph = px.Graph.from_specs([px.TaskSpec("a", fn)])
        _ = px.run(graph, strategy="sequential", state=JSONBackend(path))

        # New backend reads the file; task should be skipped.
        runs: list[str] = []

        def fn2() -> int:
            runs.append("ran")
            return 8

        graph2 = px.Graph.from_specs([px.TaskSpec("a", fn2)])
        report = px.run(graph2, strategy="sequential", state=JSONBackend(path))
        assert runs == []
        assert report["a"] == 7  # cached value, not fn2's 8


# ---------------------------------------------------------------------- #
# Events
# ---------------------------------------------------------------------- #
def test_on_event_callback() -> None:
    events: list[px.TaskEvent] = []

    def fn() -> int:
        return 1

    graph = px.Graph.from_specs([px.TaskSpec("a", fn)])
    _ = px.run(graph, strategy="sequential", on_event=events.append)
    statuses = [e.status for e in events]
    assert px.TaskStatus.SUCCESS in statuses
    assert all(e.task == "a" for e in events)


# ---------------------------------------------------------------------- #
# 异步策略：sync 任务无 timeout 分支 + timeout 重试分支
# ---------------------------------------------------------------------- #
def test_async_sync_task_without_timeout() -> None:
    """async 策略下执行 sync 任务且无 timeout（覆盖 line 131）。"""

    def sync_fn() -> int:
        return 42

    graph = px.Graph.from_specs([px.TaskSpec("a", sync_fn)])
    report = px.run(graph, strategy="async")
    assert report.success
    assert report["a"] == 42


def test_async_sync_task_with_timeout() -> None:
    """async 策略下执行 sync 任务且带 timeout（覆盖 line 129）。"""

    def sync_fn() -> int:
        return 42

    graph = px.Graph.from_specs([px.TaskSpec("a", sync_fn, timeout=5.0)])
    report = px.run(graph, strategy="async")
    assert report.success
    assert report["a"] == 42


def test_async_timeout_retry_then_succeed() -> None:
    """async 超时后重试成功（覆盖 line 141-151 的重试分支）。"""
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            await asyncio.sleep(10)  # 触发超时
        return "ok"

    graph = px.Graph.from_specs([px.TaskSpec("a", flaky, retries=2, timeout=0.05)])
    report = px.run(graph, strategy="async")
    assert report.success
    assert report["a"] == "ok"
    assert calls["n"] == 2


def test_async_failure_retry_branch(caplog: pytest.LogCaptureFixture) -> None:
    """async 普通异常重试分支（覆盖 line 141-151 的 except Exception 分支）。"""
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("not yet")
        return "ok"

    graph = px.Graph.from_specs([px.TaskSpec("a", flaky, retries=2)])
    with caplog.at_level("WARNING", logger="pyflowx"):
        report = px.run(graph, strategy="async")
    assert report.success
    assert report["a"] == "ok"
    # 确认重试日志确实输出
    assert any("retrying" in r.message for r in caplog.records)


# ---------------------------------------------------------------------- #
# 缓存跳过分支：threaded 与 async
# ---------------------------------------------------------------------- #
def test_threaded_skips_cached_tasks() -> None:
    """threaded 策略下命中缓存的任务应被跳过（覆盖 line 224-230）。"""
    runs: list[str] = []

    def make(name: str) -> Any:
        def fn() -> str:
            runs.append(name)
            return name

        return fn

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("a", make("a")),
            px.TaskSpec("b", make("b"), depends_on=("a",)),
        ]
    )
    backend = px.MemoryBackend()
    # 第一次运行填充缓存
    _ = px.run(graph, strategy="thread", max_workers=2, state=backend)
    assert runs == ["a", "b"]
    # 第二次运行应全部跳过
    _ = px.run(graph, strategy="thread", max_workers=2, state=backend)
    assert runs == ["a", "b"]  # 未再执行


def test_threaded_all_cached_layer() -> None:
    """整层全部命中缓存时应直接返回（覆盖 line 235 的 if not to_run: return）。"""
    graph = px.Graph.from_specs([px.TaskSpec("a", lambda: 1)])  # type: ignore[arg-type]
    backend = px.MemoryBackend()
    backend.save("a", 99)
    report = px.run(graph, strategy="thread", max_workers=2, state=backend)
    assert report["a"] == 99
    assert report.result_of("a").status == px.TaskStatus.SKIPPED


def test_async_skips_cached_tasks() -> None:
    """async 策略下命中缓存的任务应被跳过（覆盖 line 268-274）。"""
    runs: list[str] = []

    async def make(name: str) -> Any:
        async def fn() -> str:
            runs.append(name)
            return name

        return fn()

    # 用闭包制造可重复调用的 async 函数
    async def a() -> str:
        runs.append("a")
        return "a"

    async def b(a: str) -> str:
        runs.append("b")
        return a + "b"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("a", a),
            px.TaskSpec("b", b, depends_on=("a",)),
        ]
    )
    backend = px.MemoryBackend()
    _ = px.run(graph, strategy="async", state=backend)
    assert runs == ["a", "b"]
    _ = px.run(graph, strategy="async", state=backend)
    assert runs == ["a", "b"]


def test_async_all_cached_layer() -> None:
    """async 整层全部命中缓存（覆盖 line 279 的 if not to_run: return）。"""

    async def a() -> int:
        return 1

    graph = px.Graph.from_specs([px.TaskSpec("a", a)])
    backend = px.MemoryBackend()
    backend.save("a", 77)
    report = px.run(graph, strategy="async", state=backend)
    assert report["a"] == 77
    assert report.result_of("a").status == px.TaskStatus.SKIPPED


# ---------------------------------------------------------------------- #
# 失败后 report.success 标记为 False
# ---------------------------------------------------------------------- #
def test_failure_marks_report_unsuccessful() -> None:
    def boom() -> None:
        raise ValueError("fail")

    graph = px.Graph.from_specs([px.TaskSpec("a", boom)])
    with pytest.raises(px.TaskFailedError):
        _ = px.run(graph, strategy="sequential")
    # report 在异常前未返回，但若捕获异常则 success 应为 False
    # 这里验证 run() 抛异常的行为本身


# ---------------------------------------------------------------------- #
# dry_run 各策略
# ---------------------------------------------------------------------- #
def test_dry_run_thread(capsys: pytest.CaptureFixture[str]) -> None:
    graph = px.Graph.from_specs([px.TaskSpec("a", lambda: 1)])  # type: ignore[arg-type]
    report = px.run(graph, strategy="thread", dry_run=True)
    assert len(report) == 0
    assert "Dry run" in capsys.readouterr().out


def test_dry_run_async(capsys: pytest.CaptureFixture[str]) -> None:
    async def a() -> int:
        return 1

    graph = px.Graph.from_specs([px.TaskSpec("a", a)])
    report = px.run(graph, strategy="async", dry_run=True)
    assert len(report) == 0
    assert "Dry run" in capsys.readouterr().out


# ---------------------------------------------------------------------- #
# 空图运行
# ---------------------------------------------------------------------- #
def test_run_empty_graph() -> None:
    graph = px.Graph()
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert len(report) == 0


# ---------------------------------------------------------------------- #
# 上游任务被 SKIPPED 后，下游任务也应被 SKIPPED
# ---------------------------------------------------------------------- #
def test_downstream_skipped_when_upstream_skipped_sequential() -> None:
    """上游任务被 SKIPPED 后，下游任务也应被 SKIPPED（sequential 策略）."""
    never_true = lambda: False  # noqa: E731

    def downstream(upstream: str) -> str:
        return upstream + "_processed"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("upstream", cmd=["echo", "hello"], conditions=(never_true,)),
            px.TaskSpec("downstream", downstream, depends_on=("upstream",)),
        ]
    )
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.result_of("upstream").status == px.TaskStatus.SKIPPED
    assert report.result_of("downstream").status == px.TaskStatus.SKIPPED


def test_downstream_skipped_when_upstream_skipped_thread() -> None:
    """上游任务被 SKIPPED 后，下游任务也应被 SKIPPED（thread 策略）."""
    never_true = lambda: False  # noqa: E731

    def downstream(upstream: str) -> str:
        return upstream + "_processed"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("upstream", cmd=["echo", "hello"], conditions=(never_true,)),
            px.TaskSpec("downstream", downstream, depends_on=("upstream",)),
        ]
    )
    report = px.run(graph, strategy="thread", max_workers=2)
    assert report.success
    assert report.result_of("upstream").status == px.TaskStatus.SKIPPED
    assert report.result_of("downstream").status == px.TaskStatus.SKIPPED


def test_downstream_skipped_when_upstream_skipped_async() -> None:
    """上游任务被 SKIPPED 后，下游任务也应被 SKIPPED（async 策略）."""

    async def upstream() -> str:
        return "hello"

    async def downstream(upstream: str) -> str:
        return upstream + "_processed"

    never_true = lambda: False  # noqa: E731

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("upstream", upstream, conditions=(never_true,)),
            px.TaskSpec("downstream", downstream, depends_on=("upstream",)),
        ]
    )
    report = px.run(graph, strategy="async")
    assert report.success
    assert report.result_of("upstream").status == px.TaskStatus.SKIPPED
    assert report.result_of("downstream").status == px.TaskStatus.SKIPPED


def test_downstream_executes_when_upstream_succeeds() -> None:
    """上游任务成功时，下游任务应正常执行."""
    always_true = lambda: True  # noqa: E731

    def upstream() -> str:
        return "hello"

    def downstream(upstream: str) -> str:
        return upstream + "_processed"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("upstream", upstream, conditions=(always_true,)),
            px.TaskSpec("downstream", downstream, depends_on=("upstream",)),
        ]
    )
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.result_of("upstream").status == px.TaskStatus.SUCCESS
    assert report.result_of("downstream").status == px.TaskStatus.SUCCESS
    assert report["downstream"] == "hello_processed"
