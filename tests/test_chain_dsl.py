"""Tests for Graph.chain DSL."""

from __future__ import annotations

import pyflowx as px
from pyflowx.task import TaskSpec


def _fn() -> None:
    return None


def test_chain_basic_linkage() -> None:
    """chain(a, b, c) 应建立 a->b->c 依赖."""
    a = TaskSpec("a", _fn)
    b = TaskSpec("b", _fn)
    c = TaskSpec("c", _fn)

    graph = px.Graph().chain(a, b, c)

    assert graph.all_specs()["b"].depends_on == ("a",)
    assert graph.all_specs()["c"].depends_on == ("b",)
    assert graph.all_specs()["a"].depends_on == ()


def test_chain_single_spec() -> None:
    """chain(a) 应只注册 a，无依赖."""
    a = TaskSpec("a", _fn)
    graph = px.Graph().chain(a)
    assert "a" in graph
    assert graph.all_specs()["a"].depends_on == ()


def test_chain_preserves_existing_deps() -> None:
    """chain 应保留 spec 已有的 depends_on."""
    a = TaskSpec("a", _fn)
    b = TaskSpec("b", _fn)
    c = TaskSpec("c", _fn, depends_on=("b",))

    graph = px.Graph().chain(a, b, c)
    # c 已有 depends_on=('b',)，前驱是 b，已在依赖中，不重复添加
    assert graph.all_specs()["c"].depends_on == ("b",)


def test_chain_merges_existing_deps() -> None:
    """chain 应将前驱追加到已有依赖前（若不存在）."""
    a = TaskSpec("a", _fn)
    x = TaskSpec("x", _fn)
    c = TaskSpec("c", _fn, depends_on=("x",))

    graph = px.Graph().chain(a, x, c)
    # c 前驱是 x，但 c 已依赖 x，不重复
    assert graph.all_specs()["c"].depends_on == ("x",)


def test_chain_returns_self() -> None:
    """chain 返回 self 支持链式调用."""
    a = TaskSpec("a", _fn)
    graph = px.Graph()
    assert graph.chain(a) is graph


def test_chain_execution_order() -> None:
    """chain 应保证执行顺序."""
    order: list[str] = []

    def make(name: str):
        def fn() -> str:
            order.append(name)
            return name
        return fn

    a = TaskSpec("a", make("a"))
    b = TaskSpec("b", make("b"))
    c = TaskSpec("c", make("c"))

    graph = px.Graph().chain(a, b, c)
    report = px.run(graph)
    assert report.success
    assert order == ["a", "b", "c"]


def test_chain_with_decorator_specs() -> None:
    """chain 应与 @task 装饰器配合."""

    @px.task
    def extract() -> int:
        return 1

    @px.task
    def transform(extract: int) -> int:
        return extract + 10

    @px.task
    def load(transform: int) -> int:
        return transform + 100

    graph = px.Graph().chain(extract, transform, load)
    report = px.run(graph)
    assert report.success
    assert report["load"] == 111
