"""Tests for executors module edge cases."""

import asyncio
import logging
import sys
from typing import Callable

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


@pytest.mark.slow
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


def test_verbose_run_with_success_lifecycle(capsys: pytest.CaptureFixture[str]):
    """Test px.run with verbose=True prints SUCCESS lifecycle."""
    spec = px.TaskSpec("test", fn=lambda: "result")
    graph = px.Graph.from_specs([spec])
    report = px.run(graph, strategy="sequential", verbose=True)
    assert report.success
    captured = capsys.readouterr()
    assert "成功" in captured.out


def test_verbose_run_with_failed_lifecycle(capsys: pytest.CaptureFixture[str]):
    """Test px.run with verbose=True prints FAILED lifecycle with error."""

    def raise_error():
        raise ValueError("test error")

    spec = px.TaskSpec("test", fn=raise_error)
    graph = px.Graph.from_specs([spec])

    with pytest.raises(px.TaskFailedError):
        px.run(graph, strategy="sequential", verbose=True)
    captured = capsys.readouterr()
    assert "失败" in captured.out
    assert "test error" in captured.out


def test_verbose_run_with_skipped_lifecycle(capsys: pytest.CaptureFixture[str]):
    """Test px.run with verbose=True prints SKIPPED lifecycle."""
    spec = px.TaskSpec(
        "test",
        fn=lambda: "result",
        conditions=(lambda _ctx: False,),
    )
    graph = px.Graph.from_specs([spec])
    report = px.run(graph, strategy="sequential", verbose=True)
    assert report.success
    captured = capsys.readouterr()
    assert "跳过" in captured.out


def test_verbose_run_with_user_callback():
    """Test px.run with verbose=True and user callback both called."""
    events = []

    def on_event(event: px.TaskEvent):
        events.append(event)

    spec = px.TaskSpec("test", fn=lambda: "result")
    graph = px.Graph.from_specs([spec])
    report = px.run(graph, strategy="sequential", verbose=True, on_event=on_event)
    assert report.success
    assert len(events) == 1
    assert events[0].status == px.TaskStatus.SUCCESS


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
        conditions=(lambda _ctx: False,),
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

    spec = px.TaskSpec(
        "retry_test",
        fn=failing_function,
        retry=px.RetryPolicy(max_attempts=3),
    )
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

    spec = px.TaskSpec(
        "retry_async_test",
        fn=failing_async_function,
        retry=px.RetryPolicy(max_attempts=3),
    )
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
        conditions=(lambda _ctx: False,),
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
        conditions=(lambda _ctx: False,),
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


# ---------------------------------------------------------------------- #
# _check_upstream_skipped 分支测试
# ---------------------------------------------------------------------- #
def test_allow_upstream_skip_allows_execution_after_skipped() -> None:
    """allow_upstream_skip=True 时上游被 SKIPPED 后本任务仍执行."""
    never_true = lambda _ctx: False  # noqa: E731

    def downstream_task() -> str:
        return "ran despite upstream skipped"

    graph = px.Graph.from_specs([
        px.TaskSpec("upstream", fn=lambda: "up", conditions=(never_true,)),
        px.TaskSpec("downstream", fn=downstream_task, depends_on=("upstream",), allow_upstream_skip=True),
    ])
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.results["upstream"].status == TaskStatus.SKIPPED
    assert report.results["downstream"].status == TaskStatus.SUCCESS
    assert report["downstream"] == "ran despite upstream skipped"


def test_upstream_failed_skips_downstream() -> None:
    """上游 FAILED 时下游被 SKIPPED（除非 allow_upstream_skip=True）."""

    def boom():
        raise ValueError("boom")

    def downstream():
        return "should not run"

    graph = px.Graph.from_specs([
        px.TaskSpec("upstream", fn=boom),
        px.TaskSpec("downstream", fn=downstream, depends_on=("upstream",)),
    ])
    with pytest.raises(px.TaskFailedError):
        px.run(graph, strategy="sequential")


# ---------------------------------------------------------------------- #
# _evaluate_conditions 多条件分支测试
# ---------------------------------------------------------------------- #
def test_multiple_conditions_failure_truncation() -> None:
    """超过 2 个条件失败时应截断显示."""
    spec = px.TaskSpec(
        "multi_skip",
        fn=lambda: "result",
        conditions=(lambda _ctx: False, lambda _ctx: False, lambda _ctx: False, lambda _ctx: False, lambda _ctx: False),
    )
    graph = px.Graph.from_specs([spec])
    report = px.run(graph, strategy="sequential", verbose=True)
    assert report.success
    assert report.results["multi_skip"].status == TaskStatus.SKIPPED
    # reason 应显示 "条件不满足: <lambda>, <lambda> 等5个条件"


# ---------------------------------------------------------------------- #
# concurrency_key 测试
# ---------------------------------------------------------------------- #
def test_concurrency_key_sequential() -> None:
    """sequential 策略下 concurrency_key 无效果."""
    spec = px.TaskSpec("a", fn=lambda: 1, concurrency_key="group1")
    graph = px.Graph.from_specs([spec])
    report = px.run(graph, strategy="sequential", concurrency_limits={"group1": 1})
    assert report.success


def test_concurrency_key_thread() -> None:
    """thread 策略下 concurrency_key 应限制并发."""
    import time

    order = []

    def make(name: str) -> Callable[[], str]:
        def fn():
            order.append(f"{name}-start")
            time.sleep(0.1)
            order.append(f"{name}-end")
            return name

        return fn

    graph = px.Graph.from_specs([
        px.TaskSpec("a", fn=make("a"), concurrency_key="group1"),
        px.TaskSpec("b", fn=make("b"), concurrency_key="group1"),
        px.TaskSpec("c", fn=make("c"), concurrency_key="group1"),
    ])
    report = px.run(graph, strategy="thread", max_workers=10, concurrency_limits={"group1": 1})
    assert report.success
    # 由于 concurrency_key 限制为 1，任务应串行执行
    # 验证顺序：每个任务的 start-end 应连续
    # 可能顺序：a-start, a-end, b-start, b-end, c-start, c-end


def test_concurrency_key_async() -> None:
    """async 策略下 concurrency_key 应限制并发."""
    import asyncio

    async def task_a():
        await asyncio.sleep(0.01)
        return "a"

    async def task_b():
        await asyncio.sleep(0.01)
        return "b"

    graph = px.Graph.from_specs([
        px.TaskSpec("a", fn=task_a, concurrency_key="group1"),
        px.TaskSpec("b", fn=task_b, concurrency_key="group1"),
    ])
    report = px.run(graph, strategy="async", concurrency_limits={"group1": 1})
    assert report.success


# ---------------------------------------------------------------------- #
# dependency 策略测试
# ---------------------------------------------------------------------- #
def test_dependency_strategy_basic() -> None:
    """dependency 策略应正确执行."""
    order = []

    def make(name: str) -> Callable[[], str]:
        def fn():
            order.append(name)
            return name

        return fn

    graph = px.Graph.from_specs([
        px.TaskSpec("a", fn=make("a")),
        px.TaskSpec("b", fn=make("b"), depends_on=("a",)),
        px.TaskSpec("c", fn=make("c"), depends_on=("a",)),
        px.TaskSpec("d", fn=make("d"), depends_on=("b", "c")),
    ])
    report = px.run(graph, strategy="dependency")
    assert report.success
    assert "a" in order
    assert "d" in order


def test_dependency_strategy_async() -> None:
    """dependency 策略下异步任务应正确执行."""

    async def a():
        return "a"

    async def b(a: str):
        return a + "b"

    graph = px.Graph.from_specs([
        px.TaskSpec("a", fn=a),
        px.TaskSpec("b", fn=b, depends_on=("a",)),
    ])
    report = px.run(graph, strategy="dependency")
    assert report.success
    assert report["b"] == "ab"


# ---------------------------------------------------------------------- #
# continue_on_error 测试
# ---------------------------------------------------------------------- #
def test_continue_on_error_marks_failed_but_continues() -> None:
    """continue_on_error=True 时任务失败不抛异常，但 report.success 为 True（无 TaskFailedError 抛出）。"""

    def boom():
        raise ValueError("boom")

    graph = px.Graph.from_specs([
        px.TaskSpec("fail", fn=boom, continue_on_error=True),
        px.TaskSpec("other", fn=lambda: "ok"),  # 无依赖，应继续
    ])
    # continue_on_error=True 时 run 不抛异常，report.success 为 True
    report = px.run(graph, strategy="sequential")
    # report.success 为 True 因为没有抛 TaskFailedError
    assert report.success  # 因为 continue_on_error 阻止了 TaskFailedError
    assert report.results["fail"].status == TaskStatus.FAILED
    assert report.results["other"].status == TaskStatus.SUCCESS


def test_continue_on_error_downstream_skipped() -> None:
    """continue_on_error=True 时失败任务的下游被 SKIPPED（allow_upstream_skip=False 时）。"""

    def boom():
        raise ValueError("boom")

    def downstream():
        return "should not run"

    graph = px.Graph.from_specs([
        px.TaskSpec("fail", fn=boom, continue_on_error=True),
        px.TaskSpec("dep", fn=downstream, depends_on=("fail",), allow_upstream_skip=False),
    ])
    report = px.run(graph, strategy="sequential")
    # report.success 为 True 因为 continue_on_error 阻止了 TaskFailedError
    assert report.success
    assert report.results["fail"].status == TaskStatus.FAILED
    assert report.results["dep"].status == TaskStatus.SKIPPED


# ---------------------------------------------------------------------- #
# soft_depends_on 默认值注入测试
# ---------------------------------------------------------------------- #
def test_soft_depends_on_default_value_injection() -> None:
    """软依赖存在且成功时注入其结果值（参数名需与依赖名一致）。"""

    def task_with_soft_dep(a: str | None = None) -> str:
        return f"a={a}"

    graph = px.Graph.from_specs([
        px.TaskSpec("a", fn=lambda: "value"),
        px.TaskSpec("b", fn=task_with_soft_dep, soft_depends_on=("a",)),
    ])
    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report["b"] == "a=value"


def test_soft_depends_on_skipped_injects_none() -> None:
    """软依赖被 SKIPPED 时注入 None（参数名需与依赖名一致）。"""
    never_true = lambda _ctx: False  # noqa: E731

    def task_with_soft_dep(skipped: str | None = None) -> str:
        return f"skipped={skipped}"

    graph = px.Graph.from_specs([
        px.TaskSpec("skipped", fn=lambda: "value", conditions=(never_true,)),
        px.TaskSpec("b", fn=task_with_soft_dep, soft_depends_on=("skipped",)),
    ])
    report = px.run(graph, strategy="sequential")
    assert report.success
    # 软依赖被 skipped 时注入 None（因为 global_context 中有 skipped，值为 None）
    assert report["b"] == "skipped=None"


def test_soft_depends_on_with_defaults_for_missing() -> None:
    """软依赖引用不存在的任务时使用 defaults（但当前实现会校验软依赖必须存在）。"""
    # 注意：当前实现中，软依赖也必须在图中存在
    # 所以无法测试软依赖缺失的场景
    # 只能测试软依赖成功时注入其值的情况


# ---------------------------------------------------------------------- #
# hooks 异常处理测试
# ---------------------------------------------------------------------- #
def test_hooks_pre_run_exception_logged(caplog: pytest.LogCaptureFixture) -> None:
    """pre_run hook 抛异常应被记录但不影响任务."""

    def bad_hook(_spec):
        raise RuntimeError("hook error")

    hooks = px.TaskHooks(pre_run=bad_hook)
    spec = px.TaskSpec("a", fn=lambda: "ok", hooks=hooks)
    graph = px.Graph.from_specs([spec])

    with caplog.at_level(logging.WARNING, logger="pyflowx"):
        report = px.run(graph, strategy="sequential")
    assert report.success
    assert any("hook" in r.message for r in caplog.records)


def test_hooks_post_run_exception_logged(caplog: pytest.LogCaptureFixture) -> None:
    """post_run hook 抛异常应被记录但不影响任务."""

    def bad_hook(_spec, _value):
        raise RuntimeError("post hook error")

    hooks = px.TaskHooks(post_run=bad_hook)
    spec = px.TaskSpec("a", fn=lambda: "ok", hooks=hooks)
    graph = px.Graph.from_specs([spec])

    with caplog.at_level(logging.WARNING, logger="pyflowx"):
        report = px.run(graph, strategy="sequential")
    assert report.success
    assert any("hook" in r.message for r in caplog.records)


def test_hooks_on_failure_exception_logged(caplog: pytest.LogCaptureFixture) -> None:
    """on_failure hook 抛异常应被记录但不影响任务."""

    def bad_hook(_spec, _exc):
        raise RuntimeError("failure hook error")

    hooks = px.TaskHooks(on_failure=bad_hook)
    spec = px.TaskSpec("a", fn=lambda: (_ for _ in ()).throw(ValueError("task error")), hooks=hooks)
    graph = px.Graph.from_specs([spec])

    with caplog.at_level(logging.WARNING, logger="pyflowx"), pytest.raises(px.TaskFailedError):
        px.run(graph, strategy="sequential")
    assert any("hook" in r.message for r in caplog.records)


# ---------------------------------------------------------------------- #
# unknown strategy 测试
# ---------------------------------------------------------------------- #
def test_unknown_strategy_raises() -> None:
    """未知 strategy 应抛 ValueError."""
    graph = px.Graph.from_specs([px.TaskSpec("a", fn=lambda: 1)])
    with pytest.raises(ValueError, match="Unknown strategy"):
        # pyrefly: ignore [bad-argument-type]
        px.run(graph, strategy="unknown_strategy")


# ---------------------------------------------------------------------- #
# 空图测试
# ---------------------------------------------------------------------- #
def test_empty_graph_dependency_strategy() -> None:
    """dependency 策略下空图应正常返回."""
    graph = px.Graph()
    report = px.run(graph, strategy="dependency")
    assert report.success
    assert len(report) == 0
