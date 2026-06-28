"""Tests for Graph namespace and add_subgraph."""

from __future__ import annotations

import pytest

import pyflowx as px


def _fn() -> None:
    return None


def test_graph_namespace_field_default_none() -> None:
    """Graph 默认 namespace 为 None."""
    graph = px.Graph()
    assert graph.namespace is None


def test_graph_from_specs_with_namespace() -> None:
    """from_specs(namespace=...) 应设置 graph.namespace."""
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)], namespace="ns1")
    assert graph.namespace == "ns1"


def test_add_subgraph_prefixes_task_names() -> None:
    """add_subgraph 应给子图任务名加命名空间前缀."""
    sub = px.Graph.from_specs(
        [px.TaskSpec("extract", _fn), px.TaskSpec("build", _fn, depends_on=("extract",))],
        namespace="build",
    )
    main = px.Graph.from_specs([px.TaskSpec("start", _fn)])
    main.add_subgraph(sub)

    assert "start" in main
    assert "build:extract" in main
    assert "build:build" in main


def test_add_subgraph_renames_internal_deps() -> None:
    """add_subgraph 应给子图内部依赖名加前缀."""
    sub = px.Graph.from_specs(
        [px.TaskSpec("a", _fn), px.TaskSpec("b", _fn, depends_on=("a",))],
        namespace="ns",
    )
    main = px.Graph()
    main.add_subgraph(sub)

    b_spec = main.all_specs()["ns:b"]
    assert b_spec.depends_on == ("ns:a",)


def test_add_subgraph_all_internal_deps_prefixed() -> None:
    """add_subgraph 子图内所有任务（含被依赖的）都加前缀."""
    sub = px.Graph.from_specs(
        [px.TaskSpec("ext", _fn), px.TaskSpec("b", _fn, depends_on=("ext",))],
        namespace="ns",
    )
    main = px.Graph()
    main.add_subgraph(sub)

    b_spec = main.all_specs()["ns:b"]
    assert b_spec.depends_on == ("ns:ext",)
    assert "ns:ext" in main


def test_add_subgraph_requires_namespace() -> None:
    """add_subgraph 无 namespace 时应抛 ValueError."""
    sub = px.Graph.from_specs([px.TaskSpec("a", _fn)])  # 无 namespace
    main = px.Graph()
    with pytest.raises(ValueError, match="namespace"):
        main.add_subgraph(sub)


def test_add_subgraph_explicit_namespace_overrides() -> None:
    """add_subgraph(namespace=...) 应覆盖子图自带 namespace."""
    sub = px.Graph.from_specs([px.TaskSpec("a", _fn)], namespace="original")
    main = px.Graph()
    main.add_subgraph(sub, namespace="override")

    assert "override:a" in main
    assert "original:a" not in main


def test_add_subgraph_internal_injection_works() -> None:
    """子图内部依赖注入应通过 wrapper 正常工作."""
    sub = px.Graph.from_specs(
        [
            px.TaskSpec("extract", lambda: [1, 2, 3]),
            px.TaskSpec("build", lambda extract: [x * 2 for x in extract], depends_on=("extract",)),
        ],
        namespace="build",
    )
    main = px.Graph()
    main.add_subgraph(sub)

    report = px.run(main)
    assert report.success
    assert report["build:build"] == [2, 4, 6]


def test_add_subgraph_cross_namespace_ref_via_context() -> None:
    """跨命名空间引用应通过 Context 标注接收."""

    def consumer(ctx: px.Context) -> str:
        return f"got {ctx['ns:data']}"

    sub = px.Graph.from_specs(
        [px.TaskSpec("data", lambda: "data_value")],
        namespace="ns",
    )
    main = px.Graph()
    main.add_subgraph(sub)

    main.add(px.TaskSpec("consumer", consumer, depends_on=("ns:data",)))

    report = px.run(main)
    assert report.success
    assert report["consumer"] == "got data_value"


def test_add_subgraph_context_annotation_in_subgraph() -> None:
    """子图内部任务用 Context 标注时，wrapper 应正确传递."""

    def sink(ctx: px.Context) -> int:
        return ctx["src"]

    sub = px.Graph.from_specs(
        [
            px.TaskSpec("src", lambda: 42),
            px.TaskSpec("sink", sink, depends_on=("src",)),
        ],
        namespace="ns",
    )
    main = px.Graph()
    main.add_subgraph(sub)

    report = px.run(main)
    assert report.success
    assert report["ns:sink"] == 42


def test_add_subgraph_chained() -> None:
    """多个子图可链式合并到主图."""
    sub_a = px.Graph.from_specs([px.TaskSpec("a", _fn)], namespace="nsA")
    sub_b = px.Graph.from_specs([px.TaskSpec("b", _fn)], namespace="nsB")

    main = px.Graph()
    main.add_subgraph(sub_a).add_subgraph(sub_b)

    assert "nsA:a" in main
    assert "nsB:b" in main
