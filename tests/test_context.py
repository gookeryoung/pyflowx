"""Tests for context injection rules."""

from __future__ import annotations

from typing import Any

import pytest

import pyflowx as px
from pyflowx.context import build_call_args, describe_injection
from pyflowx.errors import InjectionError


def test_inject_by_parameter_name() -> None:
    def fn(a: int, b: str) -> str:
        return f"{a}{b}"

    spec = px.TaskSpec("c", fn, ("a", "b"))
    args, kwargs = build_call_args(spec, {"a": 1, "b": "x"})
    assert args == ()
    assert kwargs == {"a": 1, "b": "x"}


def test_inject_context_annotation() -> None:
    def fn(ctx: px.Context) -> int:
        return len(ctx)

    spec = px.TaskSpec("agg", fn, ("a", "b"))
    args, kwargs = build_call_args(spec, {"a": 1, "b": 2, "c": 99})
    # Only the task's own deps are passed.
    assert kwargs == {"ctx": {"a": 1, "b": 2}}


def test_inject_var_keyword() -> None:
    def fn(**kwargs: Any) -> int:
        return sum(kwargs.values())

    spec = px.TaskSpec("agg", fn, ("a", "b"))
    args, kwargs = build_call_args(spec, {"a": 1, "b": 2})
    assert kwargs == {"a": 1, "b": 2}


def test_static_args_and_kwargs() -> None:
    def fn(uid: int, source: str) -> str:
        return f"{source}:{uid}"

    spec = px.TaskSpec("fetch", fn, args=(42,), kwargs={"source": "api"})
    args, kwargs = build_call_args(spec, {})
    assert args == (42,)
    assert kwargs == {"source": "api"}


def test_default_param_not_required() -> None:
    def fn(a: int, flag: bool = True) -> int:
        return a if flag else 0

    spec = px.TaskSpec("t", fn, ("a",))
    args, kwargs = build_call_args(spec, {"a": 5})
    assert kwargs == {"a": 5}


def test_unresolved_required_param_raises() -> None:
    def fn(a: int, missing: str) -> None:
        return None

    spec = px.TaskSpec("t", fn, ("a",))
    with pytest.raises(InjectionError) as exc_info:
        build_call_args(spec, {"a": 1})
    assert "missing" in str(exc_info.value)


def test_static_kwargs_collide_with_dependency() -> None:
    def fn(a: int) -> int:
        return a

    spec = px.TaskSpec("t", fn, ("a",), kwargs={"a": 99})
    with pytest.raises(InjectionError):
        build_call_args(spec, {"a": 1})


def test_describe_injection() -> None:
    def fn(a: int, ctx: px.Context, flag: bool = False) -> None:
        return None

    spec = px.TaskSpec("t", fn, ("a",))
    desc = describe_injection(spec)
    assert "a=<result:a>" in desc
    assert "ctx=<Context>" in desc
    assert "flag=<default>" in desc
