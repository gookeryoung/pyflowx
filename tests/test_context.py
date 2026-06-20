"""Tests for context injection rules."""

from __future__ import annotations

from typing import Any

import pytest

import pyflowx as px
from pyflowx.context import _is_context_annotation, build_call_args, describe_injection
from pyflowx.errors import InjectionError


def test_inject_by_parameter_name() -> None:
    def fn(a: int, b: str) -> str:
        return f"{a}{b}"

    spec = px.TaskSpec("c", fn, depends_on=("a", "b"))
    args, kwargs = build_call_args(spec, {"a": 1, "b": "x"})
    assert args == ()
    assert kwargs == {"a": 1, "b": "x"}


def test_inject_context_annotation() -> None:
    def fn(ctx: px.Context) -> int:
        return len(ctx)

    spec = px.TaskSpec("agg", fn, depends_on=("a", "b"))
    args, kwargs = build_call_args(spec, {"a": 1, "b": 2, "c": 99})
    # Only the task's own deps are passed.
    assert kwargs == {"ctx": {"a": 1, "b": 2}}


def test_inject_var_keyword() -> None:
    def fn(**kwargs: Any) -> int:
        return sum(kwargs.values())

    spec = px.TaskSpec("agg", fn, depends_on=("a", "b"))
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

    spec = px.TaskSpec("t", fn, depends_on=("a",))
    args, kwargs = build_call_args(spec, {"a": 5})
    assert kwargs == {"a": 5}


def test_unresolved_required_param_raises() -> None:
    def fn(a: int, missing: str) -> None:
        return None

    spec = px.TaskSpec("t", fn, depends_on=("a",))
    with pytest.raises(InjectionError) as exc_info:
        build_call_args(spec, {"a": 1})
    assert "missing" in str(exc_info.value)


def test_static_kwargs_collide_with_dependency() -> None:
    def fn(a: int) -> int:
        return a

    spec = px.TaskSpec("t", fn, depends_on=("a",), kwargs={"a": 99})
    with pytest.raises(InjectionError):
        build_call_args(spec, {"a": 1})


def test_describe_injection() -> None:
    def fn(a: int, ctx: px.Context, flag: bool = False) -> None:
        return None

    spec = px.TaskSpec("t", fn, depends_on=("a",))
    desc = describe_injection(spec)
    assert "a=<result:a>" in desc
    assert "ctx=<Context>" in desc
    assert "flag=<default>" in desc


# ---------------------------------------------------------------------- #
# _is_context_annotation 各分支
# ---------------------------------------------------------------------- #
def test_is_context_annotation_direct_object() -> None:
    """直接传入 Context 别名对象应返回 True。"""
    assert _is_context_annotation(px.Context) is True


def test_is_context_annotation_string() -> None:
    """字符串形式的注解应被识别。"""
    assert _is_context_annotation("Context") is True
    assert _is_context_annotation("px.Context") is True
    assert _is_context_annotation("pyflowx.Context") is True
    assert _is_context_annotation("NotContext") is False
    assert _is_context_annotation("int") is False


def test_is_context_annotation_typing_alias() -> None:
    """具有 __name__/_name 为 Context/Mapping 的 typing 别名应返回 True。"""

    class FakeAlias:
        __name__ = "Context"

    assert _is_context_annotation(FakeAlias()) is True

    class FakeMapping:
        __name__ = "Mapping"

    assert _is_context_annotation(FakeMapping()) is True


def test_is_context_annotation_other() -> None:
    """其他类型注解应返回 False。"""
    assert _is_context_annotation(int) is False
    assert _is_context_annotation(str) is False
    assert _is_context_annotation(None) is False


# ---------------------------------------------------------------------- #
# describe_injection 其余分支
# ---------------------------------------------------------------------- #
def test_describe_injection_var_positional() -> None:
    """*args 参数应显示为 *args。"""

    def fn(*args: Any) -> None:
        return None

    spec = px.TaskSpec("t", fn)
    desc = describe_injection(spec)
    assert "*args" in desc


def test_describe_injection_var_keyword() -> None:
    """**kwargs 参数应显示为 **kwargs=<all-deps>。"""

    def fn(**kwargs: Any) -> None:
        return None

    spec = px.TaskSpec("t", fn, depends_on=("a",))
    desc = describe_injection(spec)
    assert "**kwargs=<all-deps>" in desc


def test_describe_injection_unresolved() -> None:
    """无依赖、无静态值、无默认的参数应显示为 <UNRESOLVED>。"""

    def fn(missing: int) -> None:
        return None

    spec = px.TaskSpec("t", fn)
    desc = describe_injection(spec)
    assert "missing=<UNRESOLVED>" in desc


def test_describe_injection_static_kwargs() -> None:
    """静态 kwargs 应显示具体值。"""

    def fn(flag: bool = False) -> None:
        return None

    spec = px.TaskSpec("t", fn, kwargs={"flag": True})
    desc = describe_injection(spec)
    assert "flag=True" in desc


def test_describe_injection_positional_args_filled() -> None:
    """spec.args 填充的位置参数应显示具体值（覆盖 args_filled 分支）。"""

    def fn(a: int, b: str) -> None:
        return None

    spec = px.TaskSpec("t", fn, args=(1, "x"))
    desc = describe_injection(spec)
    assert "a=1" in desc
    assert "b='x'" in desc


# ---------------------------------------------------------------------- #
# build_call_args 边界
# ---------------------------------------------------------------------- #
def test_build_call_args_var_positional_not_required() -> None:
    """*args 参数不应触发 InjectionError。"""

    def fn(*args: Any) -> int:
        return len(args)

    spec = px.TaskSpec("t", fn, args=(1, 2, 3))
    args, kwargs = build_call_args(spec, {})
    assert args == (1, 2, 3)
    assert kwargs == {}


def test_build_call_args_var_keyword_consumes_leftover() -> None:
    """**kwargs 应吞掉未被具名参数消费的依赖结果。"""

    def fn(a: int, **rest: Any) -> int:
        return a + sum(rest.values())

    spec = px.TaskSpec("t", fn, depends_on=("a", "b", "c"))
    args, kwargs = build_call_args(spec, {"a": 1, "b": 2, "c": 3})
    assert kwargs == {"a": 1, "b": 2, "c": 3}


def test_build_call_args_no_var_keyword_drops_leftover() -> None:
    """无 **kwargs 时，未被消费的依赖结果被丢弃（不报错）。"""

    def fn(a: int) -> int:
        return a

    spec = px.TaskSpec("t", fn, depends_on=("a", "b"))
    # b 是依赖但 fn 不接收它 —— 应正常工作
    args, kwargs = build_call_args(spec, {"a": 1, "b": 2})
    assert kwargs == {"a": 1}


def test_build_call_args_context_annotation_only_deps() -> None:
    """Context 标注只接收该任务自身 depends_on 的结果。"""

    def fn(ctx: px.Context) -> int:
        return len(ctx)

    spec = px.TaskSpec("t", fn, depends_on=("a", "b"))
    args, kwargs = build_call_args(spec, {"a": 1, "b": 2, "c": 99})
    assert kwargs == {"ctx": {"a": 1, "b": 2}}
