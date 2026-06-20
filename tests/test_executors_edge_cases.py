"""Tests for executors module edge cases."""

import asyncio
import sys

import pytest

import pyflowx as px
from pyflowx.task import TaskStatus

# 跨平台的 echo 命令
if sys.platform == "win32":
    ECHO_CMD = ["cmd", "/c", "echo"]
else:
    ECHO_CMD = ["echo"]


def test_execute_sync_with_timeout():
    """Test execute task with timeout correctly."""
    # Note: timeout for Python functions only works in async strategy
    # For sync functions, timeout is not enforced in sequential strategy
    # This test verifies that the task runs without timeout error
    spec = px.TaskSpec("quick", fn=lambda: "result", timeout=10)
    graph = px.Graph.from_specs([spec])

    # Should succeed without timeout error
    report = px.run(graph, strategy="sequential")
    assert report.success


def test_execute_async_with_timeout():
    """Test execute async task with timeout correctly."""

    async def slow_async_function():
        await asyncio.sleep(2)
        return "result"

    spec = px.TaskSpec("slow_async", fn=slow_async_function, timeout=0.5)
    graph = px.Graph.from_specs([spec])

    # This should timeout
    with pytest.raises(px.TaskFailedError):
        px.run(graph, strategy="async")


def test_verbose_event_callback_running():
    """Test verbose event callback for RUNNING status."""
    # Create a graph with verbose callback
    spec = px.TaskSpec("test", fn=lambda: "result", verbose=True)
    graph = px.Graph.from_specs([spec])
    report = px.run(graph, strategy="sequential")
    # Should print without error
    assert report.success


def test_verbose_event_callback_success():
    """Test verbose event callback for SUCCESS status."""
    # Create a graph with verbose callback
    spec = px.TaskSpec("test", fn=lambda: "result", verbose=True)
    graph = px.Graph.from_specs([spec])
    report = px.run(graph, strategy="sequential")
    # Should print without error
    assert report.success


def test_verbose_event_callback_failed():
    """Test verbose event callback for FAILED status."""
    # Create a graph with verbose callback and failing task

    def raise_error():
        raise ValueError("test error")

    spec = px.TaskSpec("test", fn=raise_error, verbose=True)
    graph = px.Graph.from_specs([spec])

    # Should print without error
    with pytest.raises(px.TaskFailedError):
        px.run(graph, strategy="sequential")


def test_verbose_event_callback_skipped():
    """Test verbose event callback for SKIPPED status."""
    # Create a graph with verbose callback and skipped task
    spec = px.TaskSpec(
        "test",
        fn=lambda: "result",
        conditions=(lambda: False,),
        verbose=True,
    )
    graph = px.Graph.from_specs([spec])
    report = px.run(graph, strategy="sequential")
    # Should print without error
    assert report.success


def test_execute_sync_with_retries():
    """Test execute task with retries."""

    call_count = 0

    def failing_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("temporary error")
        return "success"

    spec = px.TaskSpec("retry_test", fn=failing_function, retries=3)
    graph = px.Graph.from_specs([spec])

    # Should succeed after retries
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.results["retry_test"].attempts == 3


def test_execute_async_with_retries():
    """Test execute async task with retries."""

    call_count = 0

    async def failing_async_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("temporary error")
        return "success"

    spec = px.TaskSpec("retry_async_test", fn=failing_async_function, retries=3)
    graph = px.Graph.from_specs([spec])

    # Should succeed after retries
    report = px.run(graph, strategy="async")
    assert report.success
    assert report.results["retry_async_test"].attempts == 3


def test_execute_sync_skip_on_condition():
    """Test execute task skips task when condition is false."""
    spec = px.TaskSpec(
        "skip_test",
        fn=lambda: "result",
        conditions=(lambda: False,),
    )
    graph = px.Graph.from_specs([spec])

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.results["skip_test"].status == TaskStatus.SKIPPED


def test_execute_async_skip_on_condition():
    """Test execute async task skips task when condition is false."""
    spec = px.TaskSpec(
        "skip_async_test",
        fn=lambda: "result",
        conditions=(lambda: False,),
    )
    graph = px.Graph.from_specs([spec])

    report = px.run(graph, strategy="async")
    assert report.success
    assert report.results["skip_async_test"].status == TaskStatus.SKIPPED


def test_execute_sync_with_error():
    """Test execute task handles errors correctly."""

    def error_function():
        raise ValueError("test error")

    spec = px.TaskSpec("error_test", fn=error_function)
    graph = px.Graph.from_specs([spec])

    with pytest.raises(px.TaskFailedError):
        px.run(graph, strategy="sequential")


def test_execute_async_with_error():
    """Test execute async task handles errors correctly."""

    async def error_async_function():
        raise ValueError("test error")

    spec = px.TaskSpec("error_async_test", fn=error_async_function)
    graph = px.Graph.from_specs([spec])

    with pytest.raises(px.TaskFailedError):
        px.run(graph, strategy="async")
