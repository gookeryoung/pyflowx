"""Tests for execution: sequential, thread, async, retries, timeout, resume."""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time
from typing import Any, List

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
            px.TaskSpec("double", double, ("extract",)),
        ]
    )
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report["extract"] == [1, 2, 3]
    assert report["double"] == [2, 4, 6]


def test_sequential_diamond() -> None:
    order: List[str] = []

    def make(name: str) -> Any:
        def fn() -> str:
            order.append(name)
            return name

        return fn

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("a", make("a")),
            px.TaskSpec("b", make("b"), ("a",)),
            px.TaskSpec("c", make("c"), ("a",)),
            px.TaskSpec("d", make("d"), ("b", "c")),
        ]
    )
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report["d"] == "d"
    assert order == ["a", "b", "c", "d"]


def test_failure_propagates() -> None:
    def boom() -> None:
        raise ValueError("kaboom")

    def downstream(boom: None) -> int:
        return 1

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("boom", boom),
            px.TaskSpec("downstream", downstream, ("boom",)),
        ]
    )
    with pytest.raises(TaskFailedError) as exc_info:
        px.run(graph, strategy="sequential")
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
        px.run(graph, strategy="sequential")
    assert exc_info.value.attempts == 3


# ---------------------------------------------------------------------- #
# Threaded
# ---------------------------------------------------------------------- #
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
    # Three 0.3s tasks in parallel should be well under 0.8s.
    assert elapsed < 0.8


def test_threaded_layer_barrier() -> None:
    finished: List[str] = []
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
            px.TaskSpec("c", make("c"), ("a", "b")),
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
            px.TaskSpec("transform", transform, ("fetch",)),
        ]
    )
    report = px.run(graph, strategy="async")
    assert report.success
    assert report["transform"] == 84


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
            px.TaskSpec("async_task", async_task, ("sync_task",)),
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
        px.run(graph, strategy="async")
    assert isinstance(exc_info.value.cause, TaskTimeoutError)


# ---------------------------------------------------------------------- #
# Dry run
# ---------------------------------------------------------------------- #
def test_dry_run_does_not_execute(capsys: pytest.CaptureFixture[str]) -> None:
    called: List[str] = []

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
    runs: List[str] = []

    def make(name: str) -> Any:
        def fn() -> str:
            runs.append(name)
            return name

        return fn

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("a", make("a")),
            px.TaskSpec("b", make("b"), ("a",)),
        ]
    )
    backend = MemoryBackend()
    px.run(graph, strategy="sequential", state=backend)
    assert runs == ["a", "b"]

    # Second run: both cached, neither re-executed.
    px.run(graph, strategy="sequential", state=backend)
    assert runs == ["a", "b"]  # unchanged


def test_json_backend_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")

        def fn() -> int:
            return 7

        graph = px.Graph.from_specs([px.TaskSpec("a", fn)])
        px.run(graph, strategy="sequential", state=JSONBackend(path))

        # New backend reads the file; task should be skipped.
        runs: List[str] = []

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
    events: List[px.TaskEvent] = []

    def fn() -> int:
        return 1

    graph = px.Graph.from_specs([px.TaskSpec("a", fn)])
    px.run(graph, strategy="sequential", on_event=events.append)
    statuses = [e.status for e in events]
    assert px.TaskStatus.SUCCESS in statuses
    assert all(e.task == "a" for e in events)


# ---------------------------------------------------------------------- #
# Invalid strategy
# ---------------------------------------------------------------------- #
def test_invalid_strategy() -> None:
    graph = px.Graph.from_specs([px.TaskSpec("a", lambda: None)])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        px.run(graph, strategy="bogus")  # type: ignore[arg-type]
