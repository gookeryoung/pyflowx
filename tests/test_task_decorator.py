"""Tests for the @task decorator API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pyflowx as px
from pyflowx.task import RetryPolicy, TaskHooks, TaskSpec


def test_task_decorator_plain() -> None:
    """@task 无参数装饰：name 取函数名，返回 TaskSpec."""

    @px.task
    def extract() -> list[int]:
        return [1, 2, 3]

    assert isinstance(extract, TaskSpec)
    assert extract.name == "extract"
    assert extract.fn is not None
    assert extract.depends_on == ()


def test_task_decorator_with_params() -> None:
    """@task(...) 带参数装饰：传递依赖与重试."""

    @px.task(depends_on=("extract",), retry=RetryPolicy(max_attempts=3))
    def double(extract: list[int]) -> list[int]:
        return [x * 2 for x in extract]

    assert isinstance(double, TaskSpec)
    assert double.name == "double"
    assert double.depends_on == ("extract",)
    assert double.retry.max_attempts == 3


def test_task_decorator_explicit_name() -> None:
    """@task(name=...) 应使用显式名称而非函数名."""

    @px.task(name="custom_name")
    def my_func() -> None:
        return None

    assert my_func.name == "custom_name"


def test_task_decorator_cmd_form() -> None:
    """@task(cmd=...) 应支持命令形式."""

    spec = px.task(cmd=["ls", "-la"], name="list_files")
    assert isinstance(spec, TaskSpec)
    assert spec.name == "list_files"
    assert spec.cmd == ["ls", "-la"]


def test_task_decorator_full_options() -> None:
    """@task 应支持全部 TaskSpec 字段."""

    @px.task(
        depends_on=("a",),
        soft_depends_on=("b",),
        defaults={"b": 0},
        args=(1,),
        kwargs={"x": 2},
        retry=RetryPolicy(max_attempts=5),
        timeout=10.0,
        tags=("t1",),
        conditions=(px.BuiltinConditions.IS_WINDOWS,),  # type: ignore[arg-type]
        cwd="/tmp",
        env={"K": "v"},
        verbose=True,
        skip_if_missing=True,
        allow_upstream_skip=True,
        strategy="thread",
        priority=3,
        concurrency_key="db",
        continue_on_error=True,
    )
    def f(a: int) -> int:
        return a

    assert f.depends_on == ("a",)
    assert f.soft_depends_on == ("b",)
    assert f.defaults == {"b": 0}
    assert f.args == (1,)
    assert f.kwargs == {"x": 2}
    assert f.retry.max_attempts == 5
    assert f.timeout == 10.0
    assert f.tags == ("t1",)
    assert len(f.conditions) == 1
    assert isinstance(f.cwd, Path)
    assert f.cwd == Path("/tmp")
    assert f.env == {"K": "v"}
    assert f.verbose is True
    assert f.skip_if_missing is True
    assert f.allow_upstream_skip is True
    assert f.strategy == "thread"
    assert f.priority == 3
    assert f.concurrency_key == "db"
    assert f.continue_on_error is True


def test_task_decorator_runs_in_graph() -> None:
    """装饰器生成的 TaskSpec 应能直接构建图并运行."""

    @px.task
    def extract() -> list[int]:
        return [1, 2, 3]

    @px.task(depends_on=("extract",))
    def double(extract: list[int]) -> list[int]:
        return [x * 2 for x in extract]

    graph = px.Graph.from_specs([extract, double])
    report = px.run(graph)
    assert report.success
    assert report["double"] == [2, 4, 6]


def test_task_decorator_hooks_passthrough() -> None:
    """@task(hooks=...) 应传递 TaskHooks 实例."""

    hooks = TaskHooks(pre_run=lambda _spec: None)
    spec = px.task(fn=lambda: None, hooks=hooks, name="h")
    assert spec.hooks is hooks


def test_task_decorator_cache_key_passthrough() -> None:
    """@task(cache_key=...) 应传递缓存键函数."""

    def ck(ctx: Mapping[str, Any]) -> str:
        return "k"

    spec = px.task(fn=lambda: None, cache_key=ck, name="c")
    assert spec.cache_key is ck
