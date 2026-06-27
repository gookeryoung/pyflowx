"""覆盖 PyFlowX 任务流优化的全部新特性。

特性清单
--------
1. RetryPolicy：max_attempts / delay / backoff / jitter / retry_on
2. TaskHooks：pre_run / post_run / on_failure 钩子
3. GraphDefaults：图级默认值回退
4. 软依赖 soft_depends_on
5. 依赖驱动调度 strategy="dependency"（无层屏障）
6. 并发限制 concurrency_key + concurrency_limits
7. 任务优先级 priority
8. continue_on_error 容错
9. 每任务执行策略 strategy（spec 级）
10. fan-out / map 工厂
11. compose 图组合
12. task_template 模板工厂
13. cache_key 缓存键
14. env / cwd 运行时隔离
15. 上下文感知条件 DEP_EQUALS / DEP_MATCHES / DEP_PRESENT / DEP_TRUTHY
16. 动态分支：基于上游结果选择下游
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

import pyflowx as px
from pyflowx.conditions import BuiltinConditions
from pyflowx.storage import MemoryBackend
from pyflowx.task import RetryPolicy, TaskHooks, TaskStatus


# ---------------------------------------------------------------------- #
# RetryPolicy
# ---------------------------------------------------------------------- #
class TestRetryPolicy:
    """测试 RetryPolicy 数据结构与重试行为。"""

    def test_retry_policy_defaults(self) -> None:
        policy = RetryPolicy()
        assert policy.max_attempts == 1
        assert policy.delay == 0.0
        assert policy.backoff == 1.0
        assert policy.jitter == 0.0
        assert policy.retry_on == (Exception,)

    def test_retry_policy_custom(self) -> None:
        policy = RetryPolicy(
            max_attempts=5,
            delay=0.1,
            backoff=2.0,
            jitter=0.05,
            retry_on=(ValueError, KeyError),
        )
        assert policy.max_attempts == 5
        assert policy.delay == 0.1
        assert policy.backoff == 2.0
        assert policy.jitter == 0.05
        assert policy.retry_on == (ValueError, KeyError)

    def test_retry_policy_rejects_zero_attempts(self) -> None:
        with pytest.raises(ValueError, match="max_attempts"):
            RetryPolicy(max_attempts=0)

    def test_retry_policy_rejects_negative_backoff(self) -> None:
        with pytest.raises(ValueError, match="backoff"):
            RetryPolicy(backoff=-1.0)

    def test_retry_succeeds_after_failures(self) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("not yet")
            return "ok"

        graph = px.Graph.from_specs([
            px.TaskSpec("flaky", flaky, retry=RetryPolicy(max_attempts=3)),
        ])
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert report["flaky"] == "ok"
        assert calls["n"] == 3
        assert report.result_of("flaky").attempts == 3

    def test_retry_exhausted_raises(self) -> None:
        def always_fail() -> None:
            raise RuntimeError("nope")

        graph = px.Graph.from_specs([
            px.TaskSpec("f", always_fail, retry=RetryPolicy(max_attempts=3)),
        ])
        with pytest.raises(px.TaskFailedError) as exc_info:
            px.run(graph, strategy="sequential")
        assert exc_info.value.attempts == 3

    def test_retry_on_specific_exception_only(self) -> None:
        """retry_on 限制只对指定异常重试。"""
        calls = {"n": 0}

        def fail_with_keyerror() -> None:
            calls["n"] += 1
            raise KeyError("not retried")

        # retry_on=(ValueError,) -> KeyError 不应被重试
        graph = px.Graph.from_specs([
            px.TaskSpec(
                "f",
                fail_with_keyerror,
                retry=RetryPolicy(max_attempts=3, retry_on=(ValueError,)),
            ),
        ])
        with pytest.raises(px.TaskFailedError) as exc_info:
            px.run(graph, strategy="sequential")
        # KeyError 不在 retry_on 中，应只尝试 1 次
        assert exc_info.value.attempts == 1
        assert calls["n"] == 1

    def test_retry_with_backoff_delay(self) -> None:
        """backoff 应使每次重试间隔翻倍。"""
        # pyrefly: ignore [implicit-any-empty-container]
        calls = {"n": 0, "times": []}

        def flaky() -> str:
            calls["n"] += 1
            calls["times"].append(time.monotonic())
            if calls["n"] < 3:
                raise RuntimeError("not yet")
            return "ok"

        graph = px.Graph.from_specs([
            px.TaskSpec(
                "flaky",
                flaky,
                retry=RetryPolicy(max_attempts=3, delay=0.05, backoff=2.0),
            ),
        ])
        report = px.run(graph, strategy="sequential")
        assert report.success
        # 第 2 次重试应在 delay=0.05 后，第 3 次应在 0.05*2=0.10 后
        gap1 = calls["times"][1] - calls["times"][0]
        gap2 = calls["times"][2] - calls["times"][1]
        assert gap1 >= 0.04
        assert gap2 >= 0.08
        assert gap2 > gap1

    def test_retry_async_strategy(self) -> None:
        calls = {"n": 0}

        async def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("not yet")
            return "ok"

        graph = px.Graph.from_specs([
            px.TaskSpec("flaky", flaky, retry=RetryPolicy(max_attempts=3)),
        ])
        report = px.run(graph, strategy="async")
        assert report.success
        assert report["flaky"] == "ok"
        assert calls["n"] == 3


# ---------------------------------------------------------------------- #
# TaskHooks
# ---------------------------------------------------------------------- #
class TestTaskHooks:
    """测试任务生命周期钩子。"""

    def test_pre_run_hook_called(self) -> None:
        events: list[str] = []

        def pre_run(spec: px.TaskSpec[Any]) -> None:
            events.append(f"pre:{spec.name}")

        def fn() -> str:
            events.append("run")
            return "ok"

        hooks = TaskHooks(pre_run=pre_run)
        graph = px.Graph.from_specs([
            px.TaskSpec("t", fn, hooks=hooks),
        ])
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert events == ["pre:t", "run"]

    def test_post_run_hook_called_with_result(self) -> None:
        captured: dict[str, Any] = {}

        def post_run(spec: px.TaskSpec[Any], result: Any) -> None:
            captured["name"] = spec.name
            captured["result"] = result

        def fn() -> int:
            return 42

        hooks = TaskHooks(post_run=post_run)
        graph = px.Graph.from_specs([
            px.TaskSpec("t", fn, hooks=hooks),
        ])
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert captured == {"name": "t", "result": 42}

    def test_on_failure_hook_called(self) -> None:
        captured: dict[str, Any] = {}

        def on_failure(spec: px.TaskSpec[Any], exc: BaseException) -> None:
            captured["name"] = spec.name
            captured["exc"] = exc

        def fn() -> None:
            raise ValueError("boom")

        hooks = TaskHooks(on_failure=on_failure)
        graph = px.Graph.from_specs([
            px.TaskSpec("t", fn, hooks=hooks, continue_on_error=True),
        ])
        report = px.run(graph, strategy="sequential")
        # continue_on_error=True -> 报告成功但任务失败
        assert report.success
        assert captured["name"] == "t"
        assert isinstance(captured["exc"], ValueError)

    def test_hooks_not_called_on_skip(self) -> None:
        events: list[str] = []

        def pre_run(spec: px.TaskSpec[Any]) -> None:
            events.append("pre")

        def post_run(spec: px.TaskSpec[Any], result: Any) -> None:
            events.append("post")

        hooks = TaskHooks(pre_run=pre_run, post_run=post_run)
        graph = px.Graph.from_specs([
            px.TaskSpec(
                "t",
                fn=lambda: "ok",
                hooks=hooks,
                conditions=(lambda _ctx: False,),
            ),
        ])
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert report.result_of("t").status == TaskStatus.SKIPPED
        assert events == []

    def test_hooks_with_async_strategy(self) -> None:
        events: list[str] = []

        def pre_run(spec: px.TaskSpec[Any]) -> None:
            events.append(f"pre:{spec.name}")

        async def fn() -> str:
            events.append("run")
            return "ok"

        hooks = TaskHooks(pre_run=pre_run)
        graph = px.Graph.from_specs([
            px.TaskSpec("t", fn, hooks=hooks),
        ])
        report = px.run(graph, strategy="async")
        assert report.success
        assert events == ["pre:t", "run"]


# ---------------------------------------------------------------------- #
# GraphDefaults
# ---------------------------------------------------------------------- #
class TestGraphDefaults:
    """测试图级默认值回退。"""

    def test_defaults_applied_to_specs(self) -> None:
        defaults = px.GraphDefaults(
            retry=RetryPolicy(max_attempts=5),
            timeout=10.0,
            tags=("default-tag",),
            priority=3,
        )
        graph = px.Graph(defaults=defaults)
        graph.add(px.TaskSpec("a", lambda: "ok"))
        resolved = graph.resolved_spec("a")
        assert resolved.retry.max_attempts == 5
        assert resolved.timeout == 10.0
        assert resolved.priority == 3

    def test_spec_overrides_defaults(self) -> None:
        defaults = px.GraphDefaults(
            retry=RetryPolicy(max_attempts=5),
            timeout=10.0,
        )
        graph = px.Graph(defaults=defaults)
        graph.add(
            px.TaskSpec(
                "a",
                lambda: "ok",
                retry=RetryPolicy(max_attempts=2),
                timeout=1.0,
            )
        )
        resolved = graph.resolved_spec("a")
        assert resolved.retry.max_attempts == 2
        assert resolved.timeout == 1.0

    def test_defaults_empty_when_not_set(self) -> None:
        graph = px.Graph()
        graph.add(px.TaskSpec("a", lambda: "ok"))
        resolved = graph.resolved_spec("a")
        # 无默认值时回退到 spec 自身的 retry（默认 max_attempts=1）
        assert resolved.retry.max_attempts == 1
        assert resolved.timeout is None

    def test_defaults_with_run(self) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("not yet")
            return "ok"

        defaults = px.GraphDefaults(retry=RetryPolicy(max_attempts=3))
        graph = px.Graph.from_specs(
            [px.TaskSpec("flaky", flaky)],
            defaults=defaults,
        )
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert calls["n"] == 3


# ---------------------------------------------------------------------- #
# 软依赖 soft_depends_on
# ---------------------------------------------------------------------- #
class TestSoftDependencies:
    """测试软依赖：等待完成但不传播失败。"""

    def test_soft_dependency_waits_for_completion(self) -> None:
        order: list[str] = []

        def slow() -> str:
            time.sleep(0.05)
            order.append("slow")
            return "slow"

        def fast(slow: str) -> str:
            order.append("fast")
            return f"after-{slow}"

        graph = px.Graph.from_specs([
            px.TaskSpec("slow", slow),
            px.TaskSpec("fast", fast, soft_depends_on=("slow",)),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        # soft 依赖应等待 slow 完成后再执行 fast
        assert order == ["slow", "fast"]
        assert report["fast"] == "after-slow"

    def test_soft_dependency_does_not_propagate_failure(self) -> None:
        """软依赖上游失败时，下游仍应执行（硬依赖会跳过）。"""

        def fail() -> None:
            raise RuntimeError("upstream failed")

        def downstream(fail: str = "default") -> str:
            return f"got:{fail}"

        graph = px.Graph.from_specs([
            px.TaskSpec("fail", fail, continue_on_error=True),
            px.TaskSpec(
                "downstream",
                downstream,
                soft_depends_on=("fail",),
                continue_on_error=True,
            ),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        # fail 失败但下游仍执行（使用默认值）
        assert report.result_of("fail").status == TaskStatus.FAILED
        assert report.result_of("downstream").status == TaskStatus.SUCCESS

    def test_soft_dependency_validation_unknown_dep(self) -> None:
        with pytest.raises(px.MissingDependencyError):
            px.Graph.from_specs([
                px.TaskSpec("a", lambda: "ok", soft_depends_on=("missing",)),
            ])

    def test_soft_and_hard_dependency_combined(self) -> None:
        order: list[str] = []

        def a() -> str:
            order.append("a")
            return "a"

        def b(a: str) -> str:
            order.append("b")
            return f"b-{a}"

        def c(b: str) -> str:
            order.append("c")
            return f"c-{b}"

        graph = px.Graph.from_specs([
            px.TaskSpec("a", a),
            px.TaskSpec("b", b, depends_on=("a",)),
            px.TaskSpec("c", c, depends_on=("b",), soft_depends_on=("a",)),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert order == ["a", "b", "c"]


# ---------------------------------------------------------------------- #
# 依赖驱动调度 strategy="dependency"
# ---------------------------------------------------------------------- #
class TestDependencyDrivenScheduling:
    """测试依赖驱动调度：任务在依赖完成后立即启动，无层屏障。"""

    def test_dependency_strategy_basic(self) -> None:
        def a() -> int:
            return 1

        def b(a: int) -> int:
            return a + 1

        def c(b: int) -> int:
            return b + 1

        graph = px.Graph.from_specs([
            px.TaskSpec("a", a),
            px.TaskSpec("b", b, depends_on=("a",)),
            px.TaskSpec("c", c, depends_on=("b",)),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report["a"] == 1
        assert report["b"] == 2
        assert report["c"] == 3

    def test_dependency_strategy_with_async_fn(self) -> None:
        async def a() -> str:
            await asyncio.sleep(0.01)
            return "a"

        async def b(a: str) -> str:
            return f"b-{a}"

        graph = px.Graph.from_specs([
            px.TaskSpec("a", a),
            px.TaskSpec("b", b, depends_on=("a",)),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report["b"] == "b-a"

    def test_dependency_strategy_diamond(self) -> None:
        """菱形依赖：a -> b,c -> d。"""

        def a() -> int:
            return 10

        def b(a: int) -> int:
            return a * 2

        def c(a: int) -> int:
            return a + 5

        def d(b: int, c: int) -> int:
            return b + c

        graph = px.Graph.from_specs([
            px.TaskSpec("a", a),
            px.TaskSpec("b", b, depends_on=("a",)),
            px.TaskSpec("c", c, depends_on=("a",)),
            px.TaskSpec("d", d, depends_on=("b", "c")),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report["a"] == 10
        assert report["b"] == 20
        assert report["c"] == 15
        assert report["d"] == 35


# ---------------------------------------------------------------------- #
# 并发限制 concurrency_key + concurrency_limits
# ---------------------------------------------------------------------- #
class TestConcurrencyLimits:
    """测试并发限制：相同 concurrency_key 的任务串行执行。"""

    @pytest.mark.slow
    def test_concurrency_key_serializes_tasks(self) -> None:
        """相同 key 的任务不应并发执行。"""
        running: list[int] = []
        max_concurrent = {"n": 0}

        def make_fn(idx: int) -> Any:
            def fn() -> int:
                running.append(idx)
                cur = len(running)
                max_concurrent["n"] = max(max_concurrent["n"], cur)
                time.sleep(0.05)
                running.remove(idx)
                return idx

            return fn

        graph = px.Graph.from_specs([
            px.TaskSpec("a", make_fn(1), concurrency_key="db"),
            px.TaskSpec("b", make_fn(2), concurrency_key="db"),
            px.TaskSpec("c", make_fn(3), concurrency_key="db"),
        ])
        report = px.run(
            graph,
            strategy="dependency",
            concurrency_limits={"db": 1},
        )
        assert report.success
        # 最多同时运行 1 个
        assert max_concurrent["n"] == 1

    def test_concurrency_key_allows_parallel_different_keys(self) -> None:
        """不同 key 的任务可并发执行。"""
        running: list[str] = []
        max_concurrent = {"n": 0}

        def make_fn(name: str) -> Any:
            def fn() -> str:
                running.append(name)
                cur = len(running)
                max_concurrent["n"] = max(max_concurrent["n"], cur)
                time.sleep(0.05)
                running.remove(name)
                return name

            return fn

        graph = px.Graph.from_specs([
            px.TaskSpec("a", make_fn("a"), concurrency_key="db1"),
            px.TaskSpec("b", make_fn("b"), concurrency_key="db2"),
        ])
        report = px.run(
            graph,
            strategy="dependency",
            concurrency_limits={"db1": 1, "db2": 1},
        )
        assert report.success
        # 不同 key 可并发
        assert max_concurrent["n"] == 2

    def test_concurrency_limit_greater_than_one(self) -> None:
        """limit=2 允许 2 个并发。"""
        running: list[int] = []
        max_concurrent = {"n": 0}

        def make_fn(idx: int) -> Any:
            def fn() -> int:
                running.append(idx)
                cur = len(running)
                max_concurrent["n"] = max(max_concurrent["n"], cur)
                time.sleep(0.05)
                running.remove(idx)
                return idx

            return fn

        graph = px.Graph.from_specs([
            px.TaskSpec("a", make_fn(1), concurrency_key="pool"),
            px.TaskSpec("b", make_fn(2), concurrency_key="pool"),
            px.TaskSpec("c", make_fn(3), concurrency_key="pool"),
            px.TaskSpec("d", make_fn(4), concurrency_key="pool"),
        ])
        report = px.run(
            graph,
            strategy="dependency",
            concurrency_limits={"pool": 2},
        )
        assert report.success
        assert max_concurrent["n"] <= 2
        assert max_concurrent["n"] == 2


# ---------------------------------------------------------------------- #
# 任务优先级 priority
# ---------------------------------------------------------------------- #
class TestPriority:
    """测试任务优先级：高优先级任务优先调度。"""

    def test_priority_orders_independent_tasks(self) -> None:
        """无依赖任务按优先级降序执行。"""
        order: list[str] = []

        def make_fn(name: str) -> Any:
            def fn() -> str:
                order.append(name)
                return name

            return fn

        graph = px.Graph.from_specs([
            px.TaskSpec("low", make_fn("low"), priority=1),
            px.TaskSpec("high", make_fn("high"), priority=10),
            px.TaskSpec("mid", make_fn("mid"), priority=5),
        ])
        report = px.run(graph, strategy="sequential")
        assert report.success
        # 高优先级先执行
        assert order == ["high", "mid", "low"]

    def test_priority_default_zero(self) -> None:
        spec = px.TaskSpec("a", lambda: "ok")
        assert spec.priority == 0


# ---------------------------------------------------------------------- #
# continue_on_error 容错
# ---------------------------------------------------------------------- #
class TestContinueOnError:
    """测试 continue_on_error：任务失败不中断整体流程。"""

    def test_continue_on_error_allows_downstream(self) -> None:
        """continue_on_error 使失败任务不中断流程；硬依赖下游被跳过。"""

        def fail() -> None:
            raise RuntimeError("boom")

        def downstream() -> str:
            return "ran"

        graph = px.Graph.from_specs([
            px.TaskSpec("fail", fail, continue_on_error=True),
            px.TaskSpec("downstream", downstream, depends_on=("fail",)),
        ])
        report = px.run(graph, strategy="sequential")
        # continue_on_error 使整体报告成功（不抛异常）
        assert report.success
        assert report.result_of("fail").status == TaskStatus.FAILED
        # 硬依赖下游被跳过（上游失败传播）
        assert report.result_of("downstream").status == TaskStatus.SKIPPED

    def test_continue_on_error_with_soft_dep_executes_downstream(self) -> None:
        """软依赖 + continue_on_error：下游仍执行（软依赖不传播失败）。"""

        def fail() -> None:
            raise RuntimeError("boom")

        def downstream() -> str:
            return "ran"

        graph = px.Graph.from_specs([
            px.TaskSpec("fail", fail, continue_on_error=True),
            px.TaskSpec("downstream", downstream, soft_depends_on=("fail",)),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report.result_of("fail").status == TaskStatus.FAILED
        # 软依赖下游仍执行
        assert report.result_of("downstream").status == TaskStatus.SUCCESS
        assert report["downstream"] == "ran"

    def test_continue_on_error_with_dependency_strategy(self) -> None:
        def fail() -> None:
            raise RuntimeError("boom")

        def other() -> str:
            return "ok"

        graph = px.Graph.from_specs([
            px.TaskSpec("fail", fail, continue_on_error=True),
            px.TaskSpec("other", other),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report.result_of("fail").status == TaskStatus.FAILED
        assert report.result_of("other").status == TaskStatus.SUCCESS

    def test_without_continue_on_error_raises(self) -> None:
        def fail() -> None:
            raise RuntimeError("boom")

        def other() -> str:
            return "ok"

        graph = px.Graph.from_specs([
            px.TaskSpec("fail", fail),
            px.TaskSpec("other", other),
        ])
        with pytest.raises(px.TaskFailedError):
            px.run(graph, strategy="sequential")

    def test_continue_on_error_graph_defaults(self) -> None:
        def fail() -> None:
            raise RuntimeError("boom")

        defaults = px.GraphDefaults(continue_on_error=True)
        graph = px.Graph.from_specs([px.TaskSpec("fail", fail)], defaults=defaults)
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert report.result_of("fail").status == TaskStatus.FAILED


# ---------------------------------------------------------------------- #
# fan-out / map 工厂
# ---------------------------------------------------------------------- #
class TestMapFactory:
    """测试 Graph.map 工厂：为每个 item 生成 TaskSpec。"""

    def test_map_generates_tasks_per_item(self) -> None:
        def process(item: int) -> int:
            return item * 2

        template = px.TaskSpec("template", process)
        graph = px.Graph()
        specs = graph.map(
            name_fn=lambda i: f"task_{i}",
            spec=template,
            items=[1, 2, 3],
        )
        assert len(specs) == 3
        assert [s.name for s in specs] == ["task_0", "task_1", "task_2"]
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert report["task_0"] == 2
        assert report["task_1"] == 4
        assert report["task_2"] == 6

    def test_map_with_arg_factory(self) -> None:
        def process(a: int, b: int) -> int:
            return a + b

        template = px.TaskSpec("template", process)
        graph = px.Graph()
        graph.map(
            name_fn=lambda i: f"sum_{i}",
            spec=template,
            items=[(1, 10), (2, 20), (3, 30)],
            arg_factory=lambda item: (item[0], item[1]),
        )
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert report["sum_0"] == 11
        assert report["sum_1"] == 22
        assert report["sum_2"] == 33

    def test_map_with_per_item_dependencies(self) -> None:
        def source() -> list[int]:
            return [1, 2, 3]

        def process(item: int) -> int:
            return item * 10

        graph = px.Graph()
        graph.add(px.TaskSpec("source", source))
        graph.map(
            name_fn=lambda i: f"proc_{i}",
            spec=px.TaskSpec("template", process),
            items=[1, 2, 3],
            depends_on_per=lambda _i: ("source",),
        )
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report["proc_0"] == 10
        assert report["proc_1"] == 20
        assert report["proc_2"] == 30


# ---------------------------------------------------------------------- #
# compose 图组合
# ---------------------------------------------------------------------- #
class TestCompose:
    """测试 compose / GraphComposer 图组合函数。

    compose 接收 ``{name: Graph}`` 映射，解析图间的字符串引用，
    返回展开后的新映射。
    """

    def test_compose_resolves_string_references(self) -> None:
        def extract() -> list[int]:
            return [1, 2, 3]

        def transform(extract: list[int]) -> list[int]:
            return [x * 2 for x in extract]

        # extract 图
        g_extract = px.Graph.from_specs([px.TaskSpec("extract", extract)])
        # transform 图：通过 _pending_refs 引用 "extract" 命令
        # transform 自身不声明 depends_on，由 compose 展开时自动连接
        g_transform = px.Graph.from_specs([
            px.TaskSpec("transform", transform),
        ])
        g_transform._pending_refs = ["extract"]

        resolved = px.compose({"extract": g_extract, "transform": g_transform})
        assert set(resolved.keys()) == {"extract", "transform"}
        # transform 图应被展开，包含 extract 任务
        expanded = resolved["transform"]
        assert "extract" in expanded.all_specs()
        assert "transform" in expanded.all_specs()
        report = px.run(expanded, strategy="dependency")
        assert report.success
        assert report["transform"] == [2, 4, 6]

    def test_compose_no_refs_returns_unchanged(self) -> None:
        def a() -> str:
            return "a"

        g = px.Graph.from_specs([px.TaskSpec("a", a)])
        resolved = px.compose({"cmd": g})
        assert set(resolved.keys()) == {"cmd"}
        report = px.run(resolved["cmd"], strategy="sequential")
        assert report.success
        assert report["a"] == "a"

    def test_graphcomposer_class_equivalent(self) -> None:
        def a() -> str:
            return "a"

        g = px.Graph.from_specs([px.TaskSpec("a", a)])
        composer = px.GraphComposer({"cmd": g})
        resolved = composer.resolve_all()
        assert "a" in resolved["cmd"].all_specs()


# ---------------------------------------------------------------------- #
# task_template 模板工厂
# ---------------------------------------------------------------------- #
class TestTaskTemplate:
    """测试 task_template 批量生成 TaskSpec。"""

    def test_task_template_generates_specs(self) -> None:
        def process(item: int) -> int:
            return item**2

        template = px.task_template(
            fn=process,
            retry=RetryPolicy(max_attempts=2),
            tags=("compute",),
        )
        specs = [template(f"task_{i}", args=(i,)) for i in range(3)]
        graph = px.Graph.from_specs(specs)
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert report["task_0"] == 0
        assert report["task_1"] == 1
        assert report["task_2"] == 4
        # 模板属性应继承
        assert all(s.retry.max_attempts == 2 for s in specs)
        assert all(s.tags == ("compute",) for s in specs)


# ---------------------------------------------------------------------- #
# cache_key 缓存
# ---------------------------------------------------------------------- #
class TestCacheKey:
    """测试 cache_key 自定义缓存键。

    cache_key 签名为 ``Callable[[Context], str]``，仅接收上下文。
    通过闭包捕获 args 来生成输入相关的键。
    """

    def test_cache_key_hits_on_same_input(self) -> None:
        calls = {"n": 0}

        def expensive(x: int) -> int:
            calls["n"] += 1
            return x * 2

        backend = MemoryBackend()

        # 通过闭包捕获 args 生成缓存键
        def make_cache_key(arg: int) -> Any:
            def key(ctx: Any) -> str:
                return f"cache::t::{arg}"

            return key

        graph1 = px.Graph.from_specs([
            px.TaskSpec("t", expensive, args=(5,), cache_key=make_cache_key(5)),
        ])
        report1 = px.run(graph1, strategy="sequential", state=backend)
        assert report1.success
        assert report1["t"] == 10
        assert calls["n"] == 1

        # 第二次运行相同输入应命中缓存
        graph2 = px.Graph.from_specs([
            px.TaskSpec("t", expensive, args=(5,), cache_key=make_cache_key(5)),
        ])
        report2 = px.run(graph2, strategy="sequential", state=backend)
        assert report2.success
        assert report2["t"] == 10
        # 不应再次调用 fn
        assert calls["n"] == 1

    def test_cache_key_miss_on_different_input(self) -> None:
        calls = {"n": 0}

        def expensive(x: int) -> int:
            calls["n"] += 1
            return x * 2

        backend = MemoryBackend()

        def make_cache_key(arg: int) -> Any:
            def key(ctx: Any) -> str:
                return f"cache::t::{arg}"

            return key

        graph1 = px.Graph.from_specs([
            px.TaskSpec("t", expensive, args=(5,), cache_key=make_cache_key(5)),
        ])
        px.run(graph1, strategy="sequential", state=backend)
        assert calls["n"] == 1

        # 不同输入应 miss
        graph2 = px.Graph.from_specs([
            px.TaskSpec("t", expensive, args=(7,), cache_key=make_cache_key(7)),
        ])
        px.run(graph2, strategy="sequential", state=backend)
        assert calls["n"] == 2


# ---------------------------------------------------------------------- #
# env / cwd 运行时隔离
# ---------------------------------------------------------------------- #
class TestEnvAndCwd:
    """测试环境变量与工作目录隔离。"""

    def test_env_override_for_cmd(self) -> None:
        graph = px.Graph.from_specs([
            px.TaskSpec(
                "print_var",
                cmd=[sys.executable, "-c", "import os; print(os.environ.get('PYFLOWX_TEST_VAR', 'unset'))"],
                env={"PYFLOWX_TEST_VAR": "isolated"},
            ),
        ])
        report = px.run(graph, strategy="sequential")
        assert report.success

    def test_cwd_for_cmd(self, tmp_path: Path) -> None:
        # 在 tmp_path 下创建标记文件
        marker = tmp_path / "marker.txt"
        marker.write_text("found")
        graph = px.Graph.from_specs([
            px.TaskSpec(
                "check_cwd",
                cmd=["ls", "marker.txt"],
                cwd=tmp_path,
            ),
        ])
        report = px.run(graph, strategy="sequential")
        assert report.success

    def test_env_does_not_leak_to_outer(self) -> None:
        os.environ.pop("PYFLOWX_LEAK_TEST", None)

        def check_env() -> str:
            return os.environ.get("PYFLOWX_LEAK_TEST", "not-set")

        graph = px.Graph.from_specs([
            px.TaskSpec(
                "t",
                check_env,
                env={"PYFLOWX_LEAK_TEST": "leaked"},
            ),
        ])
        # fn 任务的环境变量隔离仅在 cmd 任务生效，fn 共享进程环境
        # 这里验证 fn 任务不修改外层环境
        report = px.run(graph, strategy="sequential")
        assert report.success
        assert os.environ.get("PYFLOWX_LEAK_TEST") is None


# ---------------------------------------------------------------------- #
# 上下文感知条件
# ---------------------------------------------------------------------- #
class TestContextAwareConditions:
    """测试基于上游结果的上下文感知条件。"""

    def test_dep_equals_selects_branch(self) -> None:
        """根据上游结果选择不同下游分支。"""

        def decide() -> str:
            return "path_b"

        def path_a(decide: str = "") -> str:
            return f"ran-a:{decide}"

        def path_b(decide: str = "") -> str:
            return f"ran-b:{decide}"

        graph = px.Graph.from_specs([
            px.TaskSpec("decide", decide),
            px.TaskSpec(
                "path_a",
                path_a,
                depends_on=("decide",),
                conditions=(BuiltinConditions.DEP_EQUALS("decide", "path_a"),),
            ),
            px.TaskSpec(
                "path_b",
                path_b,
                depends_on=("decide",),
                conditions=(BuiltinConditions.DEP_EQUALS("decide", "path_b"),),
            ),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report.result_of("path_a").status == TaskStatus.SKIPPED
        assert report.result_of("path_b").status == TaskStatus.SUCCESS
        assert report["path_b"] == "ran-b:path_b"

    def test_dep_truthy_conditional_downstream(self) -> None:
        def source() -> list[int]:
            return [1, 2, 3]

        def only_if_nonempty(source: list[int]) -> str:
            return f"has-{len(source)}"

        graph = px.Graph.from_specs([
            px.TaskSpec("source", source),
            px.TaskSpec(
                "only_if_nonempty",
                only_if_nonempty,
                depends_on=("source",),
                conditions=(BuiltinConditions.DEP_TRUTHY("source"),),
            ),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report["only_if_nonempty"] == "has-3"

    def test_dep_truthy_skips_when_empty(self) -> None:
        def source() -> list[int]:
            return []

        def only_if_nonempty(source: list[int]) -> str:
            return "should-not-run"

        graph = px.Graph.from_specs([
            px.TaskSpec("source", source),
            px.TaskSpec(
                "only_if_nonempty",
                only_if_nonempty,
                depends_on=("source",),
                conditions=(BuiltinConditions.DEP_TRUTHY("source"),),
            ),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report.result_of("only_if_nonempty").status == TaskStatus.SKIPPED

    def test_dep_matches_complex_predicate(self) -> None:
        def source() -> int:
            return 42

        def downstream(source: int) -> str:
            return f"got-{source}"

        graph = px.Graph.from_specs([
            px.TaskSpec("source", source),
            px.TaskSpec(
                "downstream",
                downstream,
                depends_on=("source",),
                conditions=(BuiltinConditions.DEP_MATCHES("source", lambda v: v > 10),),
            ),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report["downstream"] == "got-42"


# ---------------------------------------------------------------------- #
# 每任务执行策略 spec.strategy
# ---------------------------------------------------------------------- #
class TestPerTaskStrategy:
    """测试每任务执行策略字段（spec 级）。"""

    def test_strategy_field_stored(self) -> None:
        spec = px.TaskSpec("a", lambda: "ok", strategy="async")
        assert spec.strategy == "async"

    def test_strategy_field_default_none(self) -> None:
        spec = px.TaskSpec("a", lambda: "ok")
        assert spec.strategy is None

    def test_mixed_sync_async_in_dependency_strategy(self) -> None:
        """dependency 策略可混合 sync/async 任务。"""

        def sync_fn() -> str:
            return "sync"

        async def async_fn(sync: str) -> str:
            await asyncio.sleep(0.01)
            return f"async-{sync}"

        graph = px.Graph.from_specs([
            px.TaskSpec("sync", sync_fn),
            px.TaskSpec("async", async_fn, depends_on=("sync",)),
        ])
        report = px.run(graph, strategy="dependency")
        assert report.success
        assert report["async"] == "async-sync"


# ---------------------------------------------------------------------- #
# 综合场景：map-reduce
# ---------------------------------------------------------------------- #
class TestMapReduceScenario:
    """测试 map-reduce 模式：fan-out 计算 + 汇总。"""

    def test_map_reduce_pattern(self) -> None:
        def source() -> list[int]:
            return [1, 2, 3, 4, 5]

        def worker(item: int) -> int:
            return item**2

        def reduce(**kwargs: int) -> int:
            # **kwargs 自动注入所有依赖（worker_0, worker_1, ...）
            return sum(v for v in kwargs.values() if isinstance(v, int))

        graph = px.Graph()
        graph.add(px.TaskSpec("source", source))
        workers = graph.map(
            name_fn=lambda i: f"worker_{i}",
            spec=px.TaskSpec("worker_tmpl", worker),
            items=[1, 2, 3, 4, 5],
            depends_on_per=lambda _i: ("source",),
        )
        # reduce 依赖所有 worker
        graph.add(
            px.TaskSpec(
                "reduce",
                reduce,
                depends_on=tuple(w.name for w in workers),
            )
        )
        report = px.run(graph, strategy="dependency")
        assert report.success
        # 1+4+9+16+25 = 55
        assert report["reduce"] == 55

    def test_map_reduce_with_concurrency_limit(self) -> None:
        """map-reduce 配合并发限制：worker 限制为 2 并发。"""
        running: list[int] = []
        max_concurrent = {"n": 0}

        def worker(item: int) -> int:
            running.append(item)
            cur = len(running)
            max_concurrent["n"] = max(max_concurrent["n"], cur)
            time.sleep(0.02)
            running.remove(item)
            return item**2

        def reduce(**kwargs: int) -> int:
            return sum(v for v in kwargs.values() if isinstance(v, int))

        graph = px.Graph()
        workers = graph.map(
            name_fn=lambda i: f"worker_{i}",
            spec=px.TaskSpec("worker_tmpl", worker, concurrency_key="pool"),
            items=[1, 2, 3, 4, 5],
        )
        graph.add(
            px.TaskSpec(
                "reduce",
                reduce,
                depends_on=tuple(w.name for w in workers),
            )
        )
        report = px.run(
            graph,
            strategy="dependency",
            concurrency_limits={"pool": 2},
        )
        assert report.success
        assert report["reduce"] == 55
        assert max_concurrent["n"] <= 2
