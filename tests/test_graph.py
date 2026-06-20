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
        px.TaskSpec("b", _fn, ("a",)),
        px.TaskSpec("c", _fn, ("a", "b")),
    ])
    assert set(graph.names) == {"a", "b", "c"}
    assert graph.dependencies("c") == ("a", "b")
    assert len(graph) == 3
    assert "a" in graph


def test_from_specs_allows_forward_references() -> None:
    # b depends on a, but a is declared after b — order should not matter.
    graph = px.Graph.from_specs([
        px.TaskSpec("b", _fn, ("a",)),
        px.TaskSpec("a", _fn),
    ])
    assert graph.layers() == [["a"], ["b"]]


def test_duplicate_task_raises() -> None:
    with pytest.raises(DuplicateTaskError):
        px.Graph.from_specs([
            px.TaskSpec("a", _fn),
            px.TaskSpec("a", _fn),
        ])


def test_missing_dependency_raises() -> None:
    with pytest.raises(MissingDependencyError) as exc_info:
        px.Graph.from_specs([px.TaskSpec("b", _fn, ("a",))])
    assert exc_info.value.task == "b"
    assert exc_info.value.dependency == "a"


def test_cycle_detection() -> None:
    with pytest.raises(CycleError):
        px.Graph.from_specs([
            px.TaskSpec("a", _fn, ("c",)),
            px.TaskSpec("b", _fn, ("a",)),
            px.TaskSpec("c", _fn, ("b",)),
        ])


def test_layers_grouping() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn),
        px.TaskSpec("c", _fn, ("a", "b")),
        px.TaskSpec("d", _fn, ("c",)),
    ])
    layers = graph.layers()
    assert layers == [["a", "b"], ["c"], ["d"]]


def test_self_dependency_rejected() -> None:
    with pytest.raises(ValueError):
        px.TaskSpec("a", _fn, ("a",))


def test_to_mermaid() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn, ("a",)),
    ])
    mermaid = graph.to_mermaid()
    assert mermaid.startswith("graph TD")
    assert 'a["a"]' in mermaid
    assert "a --> b" in mermaid


def test_to_mermaid_invalid_orientation() -> None:
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    with pytest.raises(ValueError):
        graph.to_mermaid("XX")


def test_subgraph_by_tags() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn, tags=("ingest",)),
        px.TaskSpec("b", _fn, ("a",), tags=("ingest",)),
        px.TaskSpec("c", _fn, ("b",), tags=("report",)),
    ])
    sub = graph.subgraph(["ingest"])
    assert set(sub.names) == {"a", "b"}
    # Edge to dropped task c is removed; b no longer waits for anything
    # outside the subgraph (c was never a dep of b anyway).
    assert sub.dependencies("b") == ("a",)


def test_subgraph_by_names() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn, ("a",)),
        px.TaskSpec("c", _fn, ("b",)),
    ])
    sub = graph.subgraph_by_names(["a", "b"])
    assert set(sub.names) == {"a", "b"}
    # c is dropped, so b's dep on c (none here) — but a->b edge preserved.
    assert sub.dependencies("b") == ("a",)


def test_subgraph_by_names_unknown() -> None:
    graph = px.Graph.from_specs([px.TaskSpec("a", _fn)])
    with pytest.raises(KeyError):
        graph.subgraph_by_names(["nope"])


def test_describe() -> None:
    graph = px.Graph.from_specs([
        px.TaskSpec("a", _fn),
        px.TaskSpec("b", _fn, ("a",)),
    ])
    desc = graph.describe()
    assert "Layer 1" in desc
    assert "Layer 2" in desc
