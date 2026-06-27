"""Tests for Graph construction, validation, layering and subgraphs."""

from __future__ import annotations

import pytest

import pyflowx as px
from pyflowx.errors import CycleError, DuplicateTaskError, MissingDependencyError


def _fn() -> None:
    return None


def test_from_specs_builds_graph() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn, depends_on=("a",)),
        px.TaskSpec("c", _fn, depends_on=("a", "b")),
    ])
    assert set(graph.names) == {"a", "b", "c"}
    assert graph.dependencies("c") == ("a", "b")
    assert len(graph) == 3
    assert "a" in graph


def test_from_specs_allows_forward_references() -> None:
    # b depends on a, but a is declared after b — order should not matter.
    graph = px.Graph.from_specs([
        px.TaskSpec("b", _fn, depends_on=("a",)),
        px.TaskSpec("a", _fn),
    ])
    assert graph.layers() == [["a"], ["b"]]


def test_duplicate_task_raises() -> None:
    with pytest.raises(DuplicateTaskError):
        _ = px.Graph.from_specs([
            px.TaskSpec("a", _fn),
            px.TaskSpec("a", _fn),
        ])


def test_missing_dependency_raises() -> None:
    with pytest.raises(MissingDependencyError) as exc_info:
        _ = px.Graph.from_specs([px.TaskSpec("b", _fn, depends_on=("a",))])

    assert exc_info.value.task == "b"
    assert exc_info.value.dependency == "a"


def test_cycle_detection() -> None:
    with pytest.raises(CycleError):
        _ = px.Graph.from_specs([
            px.TaskSpec("a", _fn, depends_on=("c",)),
            px.TaskSpec("b", _fn, depends_on=("a",)),
            px.TaskSpec("c", _fn, depends_on=("b",)),
        ])


def test_layers_grouping() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn),
        px.TaskSpec("c", _fn, depends_on=("a", "b")),
        px.TaskSpec("d", _fn, depends_on=("c",)),
    ])
    layers = graph.layers()
    assert layers == [["a", "b"], ["c"], ["d"]]


def test_self_dependency_rejected() -> None:
    with pytest.raises(ValueError):
        _ = px.TaskSpec("a", _fn, depends_on=("a",))


def test_to_mermaid() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn, depends_on=("a",)),
    ])
    mermaid = graph.to_mermaid()
    assert mermaid.startswith("graph TD")
    assert 'a["a"]' in mermaid
    assert "a --> b" in mermaid


def test_to_mermaid_invalid_orientation() -> None:
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    with pytest.raises(ValueError):
        _ = graph.to_mermaid("XX")


def test_subgraph_by_tags() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn, tags=("ingest",)),
        px.TaskSpec("b", _fn, depends_on=("a",), tags=("ingest",)),
        px.TaskSpec("c", _fn, depends_on=("b",), tags=("report",)),
    ])
    sub = graph.subgraph(["ingest"])
    assert set(sub.names) == {"a", "b"}
    # Edge to dropped task c is removed; b no longer waits for anything
    # outside the subgraph (c was never a dep of b anyway).
    assert sub.dependencies("b") == ("a",)


def test_subgraph_by_names() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn, depends_on=("a",)),
        px.TaskSpec("c", _fn, depends_on=("b",)),
    ])
    sub = graph.subgraph_by_names(["a", "b"])
    assert set(sub.names) == {"a", "b"}
    # c is dropped, so b's dep on c (none here) — but a->b edge preserved.
    assert sub.dependencies("b") == ("a",)


def test_subgraph_by_names_unknown() -> None:
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    with pytest.raises(KeyError):
        _ = graph.subgraph_by_names(["nope"])


def test_describe() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn, depends_on=("a",)),
    ])
    desc = graph.describe()
    assert "Layer 1" in desc
    assert "Layer 2" in desc


# ---------------------------------------------------------------------- #
# 增量 add API 与其他访问器
# ---------------------------------------------------------------------- #
def test_add_chains_and_validates() -> None:
    """add() 应返回 self 以支持链式调用，并即时校验。"""
    graph = px.Graph()
    ret = graph.add(px.TaskSpec("a", _fn))
    assert ret is graph
    assert "a" in graph
    # 缺失依赖应即时报错
    with pytest.raises(MissingDependencyError):
        _ = graph.add(px.TaskSpec("b", _fn, depends_on=("missing",)))


def test_add_duplicate_raises() -> None:
    graph = px.Graph()
    _ = graph.add(px.TaskSpec("a", _fn))
    with pytest.raises(DuplicateTaskError):
        _ = graph.add(px.TaskSpec("a", _fn))


def test_all_specs_returns_view() -> None:
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    view = graph.all_specs()
    assert set(view.keys()) == {"a"}
    # 返回的是只读视图，修改不影响内部
    assert view is graph.all_specs() or view == graph.all_specs()


def test_spec_accessor() -> None:
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    assert graph.spec("a").name == "a"
    with pytest.raises(KeyError):
        _ = graph.spec("missing")


def test_dependencies_accessor() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn, depends_on=("a",)),
    ])
    assert graph.dependencies("a") == ()
    assert graph.dependencies("b") == ("a",)


def test_repr() -> None:
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    assert repr(graph) == "Graph(tasks=1)"


def test_empty_graph_layers() -> None:
    """空图的 layers() 应返回空列表。"""
    graph = px.Graph()
    assert graph.layers() == []
    assert graph.to_mermaid() == "graph TD\n"


def test_subgraph_preserves_metadata() -> None:
    """子图应保留原任务的 retry/timeout/tags 等元数据。"""
    graph = px.Graph.from_specs([
        px.TaskSpec(
            "a",
            _fn,
            tags=("x",),
            retry=px.RetryPolicy(max_attempts=3),
            timeout=5.0,
        ),
        px.TaskSpec("b", _fn, depends_on=("a",), tags=("y",)),
    ])
    sub = graph.subgraph(["x"])
    spec = sub.spec("a")
    assert spec.retry.max_attempts == 3
    assert spec.timeout == 5.0
    assert spec.tags == ("x",)


def test_subgraph_by_tags_no_match() -> None:
    """无匹配 tag 时返回空图。"""
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn, tags=("x",))])
    sub = graph.subgraph(["z"])
    assert len(sub) == 0
