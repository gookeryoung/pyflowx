"""Tests for Graph construction, validation, layering and subgraphs."""

from __future__ import annotations

import pytest

import pyflowx as px
from pyflowx.compose import GraphComposer, compose
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


def test_all_deps_combines_hard_and_soft() -> None:
    """all_deps 应返回硬依赖 + 软依赖的组合。"""
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn),
        px.TaskSpec("c", _fn, depends_on=("a",), soft_depends_on=("b",)),
    ])
    all_deps = graph.all_deps("c")
    assert set(all_deps) == {"a", "b"}
    # 硬依赖在前，软依赖在后
    assert all_deps == ("a", "b")


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


# ---------------------------------------------------------------------- #
# from_specs str 类型分支测试
# ---------------------------------------------------------------------- #
def test_from_specs_with_string_ref() -> None:
    """from_specs 接受字符串引用并收集到 pending_refs."""
    # 字符串引用被收集到 _pending_refs，而非尝试打开文件
    graph = px.Graph.from_specs(["ref_cmd"])
    assert graph._pending_refs == ["ref_cmd"]


def test_from_specs_with_invalid_type() -> None:
    """from_specs 接受不支持的类型时应抛 TypeError."""
    with pytest.raises(TypeError, match="from_specs 只接受 TaskSpec 或 str"):
        _ = px.Graph.from_specs([123])  # type: ignore[list-item]


# ---------------------------------------------------------------------- #
# to_mermaid 软依赖测试
# ---------------------------------------------------------------------- #
def test_to_mermaid_soft_depends_on() -> None:
    """to_mermaid 应正确绘制软依赖为虚线."""
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn, soft_depends_on=("a",)),
    ])
    mermaid = graph.to_mermaid()
    assert "a -.-> b" in mermaid  # 软依赖用虚线


# ---------------------------------------------------------------------- #
# GraphComposer 与 compose 测试
# ---------------------------------------------------------------------- #
def test_graph_composer_resolve_all() -> None:
    """GraphComposer.resolve_all 应展开所有图的字符串引用."""
    graph_a = px.Graph.from_specs([px.TaskSpec("a1", _fn), px.TaskSpec("a2", _fn, depends_on=("a1",))])
    # 创建带 _pending_refs 的图
    graph_b = px.Graph.from_specs([px.TaskSpec("b1", _fn)])
    graph_b._pending_refs = ["cmd_a"]  # 手动设置内部属性

    composer = GraphComposer({"cmd_a": graph_a, "cmd_b": graph_b})
    resolved = composer.resolve_all()

    # graph_b 应包含 graph_a 的任务
    assert "a1" in resolved["cmd_b"]
    assert "a2" in resolved["cmd_b"]


def test_graph_composer_parse_ref_self_reference() -> None:
    """GraphComposer.parse_ref 应检测循环引用."""
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    composer = GraphComposer({"cmd": graph})
    with pytest.raises(ValueError, match="循环引用"):
        _ = composer.parse_ref("cmd", "cmd")


def test_graph_composer_parse_ref_cmd_not_found() -> None:
    """GraphComposer.parse_ref 应检测引用的命令不存在."""
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    composer = GraphComposer({"cmd": graph})
    with pytest.raises(ValueError, match="引用的命令 'missing' 不存在"):
        _ = composer.parse_ref("missing", "current")


def test_graph_composer_parse_ref_task_not_found() -> None:
    """GraphComposer.parse_ref 应检测任务不存在于引用的命令中."""
    graph_a = px.Graph.from_specs([px.TaskSpec("a1", _fn)])
    graph_b = px.Graph.from_specs([px.TaskSpec("b1", _fn)])
    composer = GraphComposer({"cmd_a": graph_a, "cmd_b": graph_b})
    with pytest.raises(ValueError, match="任务 'missing' 不存在于命令 'cmd_a' 中"):
        _ = composer.parse_ref("cmd_a.missing", "cmd_b")


def test_graph_composer_expand_refs_no_pending() -> None:
    """GraphComposer.expand_refs 无 pending_refs 时应原样返回."""
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    composer = GraphComposer({"cmd": graph})
    expanded = composer.expand_refs(graph, "cmd")
    assert expanded is graph


def test_compose_function() -> None:
    """compose() 函数应等同于 GraphComposer().resolve_all()。"""
    graph_a = px.Graph.from_specs([px.TaskSpec("a1", _fn)])
    graph_b = px.Graph.from_specs([px.TaskSpec("b1", _fn)])
    graph_b._pending_refs = ["cmd_a"]  # 手动设置内部属性

    resolved = compose({"cmd_a": graph_a, "cmd_b": graph_b})
    assert "a1" in resolved["cmd_b"]


def test_graph_composer_expand_refs_multiple_refs_chain() -> None:
    """expand_refs 多个 ref 应串联依赖：后一个 ref 首任务依赖前一个 ref 末任务."""
    graph_a = px.Graph.from_specs([px.TaskSpec("a1", _fn)])
    graph_c = px.Graph.from_specs([px.TaskSpec("c1", _fn)])
    graph_b = px.Graph.from_specs([px.TaskSpec("b1", _fn)])
    graph_b._pending_refs = ["cmd_a", "cmd_c"]

    composer = GraphComposer({"cmd_a": graph_a, "cmd_c": graph_c, "cmd_b": graph_b})
    resolved = composer.resolve_all()

    # c1 应依赖 a1（后 ref 首任务依赖前 ref 末任务）
    assert "a1" in resolved["cmd_b"]
    assert "c1" in resolved["cmd_b"]
    assert "b1" in resolved["cmd_b"]
    c1_spec = resolved["cmd_b"].all_specs()["c1"]
    assert "a1" in c1_spec.depends_on


def test_graph_composer_expand_refs_ref_returns_empty() -> None:
    """expand_refs 引用空图时，previous_ref_last_task 保持 None，original_specs 走 else 分支."""
    graph_empty = px.Graph.from_specs([])
    graph_b = px.Graph.from_specs([px.TaskSpec("b1", _fn)])
    graph_b._pending_refs = ["empty_cmd"]

    composer = GraphComposer({"empty_cmd": graph_empty, "cmd_b": graph_b})
    resolved = composer.resolve_all()

    # b1 保留，无额外依赖
    assert "b1" in resolved["cmd_b"]
    b1_spec = resolved["cmd_b"].all_specs()["b1"]
    assert b1_spec.depends_on == ()


def test_graph_composer_expand_refs_multiple_original_specs_serialized() -> None:
    """expand_refs 多个 original_specs 应串行依赖，且首个依赖 ref 末任务."""
    graph_a = px.Graph.from_specs([px.TaskSpec("a1", _fn)])
    graph_b = px.Graph.from_specs([
        px.TaskSpec("b1", _fn),
        px.TaskSpec("b2", _fn),
        px.TaskSpec("b3", _fn),
    ])
    graph_b._pending_refs = ["cmd_a"]

    composer = GraphComposer({"cmd_a": graph_a, "cmd_b": graph_b})
    resolved = composer.resolve_all()

    specs = resolved["cmd_b"].all_specs()
    # b1 依赖 a1（ref 末任务）
    assert "a1" in specs["b1"].depends_on
    # b2 依赖 b1，b3 依赖 b2（串行）
    assert "b1" in specs["b2"].depends_on
    assert "b2" in specs["b3"].depends_on


def test_graph_composer_parse_ref_dot_notation_success() -> None:
    """parse_ref 'cmd.task' 形式应返回对应单个 TaskSpec."""
    graph_a = px.Graph.from_specs([px.TaskSpec("a1", _fn), px.TaskSpec("a2", _fn)])
    composer = GraphComposer({"cmd_a": graph_a})

    result = composer.parse_ref("cmd_a.a2", "cmd_b")
    assert len(result) == 1
    assert result[0].name == "a2"


def test_graph_composer_parse_ref_dot_notation_cmd_not_found() -> None:
    """parse_ref 'missing.task' 形式应检测命令不存在."""
    graph_a = px.Graph.from_specs([px.TaskSpec("a1", _fn)])
    composer = GraphComposer({"cmd_a": graph_a})

    with pytest.raises(ValueError, match="引用的命令 'missing' 不存在"):
        _ = composer.parse_ref("missing.task", "cmd_b")


# ---------------------------------------------------------------------- #
# resolved_spec defaults 测试
# ---------------------------------------------------------------------- #
def test_resolved_spec_applies_defaults() -> None:
    """resolved_spec 应应用 Graph.defaults。"""
    defaults = px.GraphDefaults(timeout=10.0, retry=px.RetryPolicy(max_attempts=2))
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)], defaults=defaults)

    resolved = graph.resolved_spec("a")
    assert resolved.timeout == 10.0
    assert resolved.retry.max_attempts == 2


def test_resolved_spec_no_override() -> None:
    """resolved_spec 不应覆盖任务已有的设置。"""
    defaults = px.GraphDefaults(timeout=10.0)
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn, timeout=5.0)], defaults=defaults)

    resolved = graph.resolved_spec("a")
    assert resolved.timeout == 5.0  # 保持原值，不被 defaults 覆盖
