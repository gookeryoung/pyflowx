"""测试上下文注入规则."""

from __future__ import annotations

from typing import Any

import pytest

import pyflowx as px
from pyflowx.context import _is_context_annotation, build_call_args, describe_injection
from pyflowx.errors import InjectionError


class TestBuildCallArgs:
    """测试 build_call_args 函数."""

    def test_inject_by_parameter_name(self) -> None:
        """参数名匹配依赖名时应注入对应结果."""

        def fn(a: int, b: str) -> str:
            return f"{a}{b}"

        spec = px.TaskSpec("c", fn, depends_on=("a", "b"))
        _args, kwargs = build_call_args(spec, {"a": 1, "b": "x"})
        assert kwargs == {"a": 1, "b": "x"}

    def test_inject_context_annotation(self) -> None:
        """标注为 Context 的参数应接收完整依赖映射."""

        def fn(ctx: px.Context) -> int:
            return len(ctx)

        spec = px.TaskSpec("agg", fn, depends_on=("a", "b"))
        _args, kwargs = build_call_args(spec, {"a": 1, "b": 2, "c": 99})
        # Only the task's own deps are passed.
        assert kwargs == {"ctx": {"a": 1, "b": 2}}

    def test_inject_var_keyword(self) -> None:
        """**kwargs 参数应以 dict 形式接收所有依赖结果."""

        def fn(**kwargs: Any) -> int:  # pyright: ignore[reportExplicitAny, reportAny]
            return sum(kwargs.values())

        spec = px.TaskSpec("agg", fn, depends_on=("a", "b"))
        _args, kwargs = build_call_args(spec, {"a": 1, "b": 2})
        assert kwargs == {"a": 1, "b": 2}

    def test_static_args_and_kwargs(self) -> None:
        """静态 args/kwargs 应正确填充非依赖参数."""

        def fn(uid: int, source: str) -> str:
            return f"{source}:{uid}"

        spec = px.TaskSpec("fetch", fn, args=(42,), kwargs={"source": "api"})
        args, kwargs = build_call_args(spec, {})
        assert args == (42,)
        assert kwargs == {"source": "api"}

    def test_default_param_not_required(self) -> None:
        """有默认值的参数无需依赖或静态值."""

        def fn(a: int, flag: bool = True) -> int:
            return a if flag else 0

        spec = px.TaskSpec("t", fn, depends_on=("a",))
        _args, kwargs = build_call_args(spec, {"a": 5})
        assert kwargs == {"a": 5}

    def test_unresolved_required_param_raises(self) -> None:
        """必需参数无法解析时应抛出 InjectionError."""

        def fn(_a: int, _: str) -> None:
            return None

        spec = px.TaskSpec("t", fn, depends_on=("a",))
        with pytest.raises(InjectionError) as exc_info:
            _ = build_call_args(spec, {"a": 1})
        assert "Cannot inject" in str(exc_info.value)

    def test_static_kwargs_collide_with_dependency(self) -> None:
        """静态 kwargs 与依赖名冲突时应抛出 InjectionError."""

        def fn(a: int) -> int:
            return a

        spec = px.TaskSpec("t", fn, depends_on=("a",), kwargs={"a": 99})
        with pytest.raises(InjectionError):
            _ = build_call_args(spec, {"a": 1})

    def test_var_positional_not_required(self) -> None:
        """*args 参数不应触发 InjectionError."""

        def fn(*args: Any) -> int:  # pyright: ignore[reportExplicitAny, reportAny]
            return len(args)

        spec = px.TaskSpec("t", fn, args=(1, 2, 3))
        args, kwargs = build_call_args(spec, {})
        assert args == (1, 2, 3)
        assert kwargs == {}

    def test_var_keyword_consumes_leftover(self) -> None:
        """**kwargs 应吞掉未被具名参数消费的依赖结果."""

        def fn(a: int, **rest: Any) -> int:  # pyright: ignore[reportExplicitAny, reportAny]
            return a + sum(rest.values())

        spec = px.TaskSpec("t", fn, depends_on=("a", "b", "c"))
        _args, kwargs = build_call_args(spec, {"a": 1, "b": 2, "c": 3})
        assert kwargs == {"a": 1, "b": 2, "c": 3}

    def test_no_var_keyword_drops_leftover(self) -> None:
        """无 **kwargs 时，未被消费的依赖结果被丢弃（不报错）."""

        def fn(a: int) -> int:
            return a

        spec = px.TaskSpec("t", fn, depends_on=("a", "b"))
        # b 是依赖但 fn 不接收它 —— 应正常工作
        _args, kwargs = build_call_args(spec, {"a": 1, "b": 2})
        assert kwargs == {"a": 1}

    def test_context_annotation_only_deps(self) -> None:
        """Context 标注只接收该任务自身 depends_on 的结果."""

        def fn(ctx: px.Context) -> int:
            return len(ctx)

        spec = px.TaskSpec("t", fn, depends_on=("a", "b"))
        _args, kwargs = build_call_args(spec, {"a": 1, "b": 2, "c": 99})
        assert kwargs == {"ctx": {"a": 1, "b": 2}}


class TestDescribeInjection:
    """测试 describe_injection 函数."""

    def test_describe_injection(self) -> None:
        """应正确描述依赖注入、Context 标注和默认值."""

        def fn(a: int, ctx: px.Context, flag: bool = False) -> None:
            return None

        spec = px.TaskSpec("t", fn, depends_on=("a",))
        desc = describe_injection(spec)
        assert "a=<result:a>" in desc
        assert "ctx=<Context>" in desc
        assert "flag=<default>" in desc

    def test_var_positional(self) -> None:
        """*args 参数应显示为 *args."""

        def fn(*args: Any) -> None:
            return None

        spec = px.TaskSpec("t", fn)
        desc = describe_injection(spec)
        assert "*args" in desc

    def test_var_keyword(self) -> None:
        """**kwargs 参数应显示为 **kwargs=<all-deps>."""

        def fn(**kwargs: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
            return None

        spec = px.TaskSpec("t", fn, depends_on=("a",))
        desc = describe_injection(spec)
        assert "**kwargs=<all-deps>" in desc

    def test_unresolved(self) -> None:
        """无依赖、无静态值、无默认的参数应显示为 <UNRESOLVED>."""

        def fn(missing: int) -> None:
            return None

        spec = px.TaskSpec("t", fn)
        desc = describe_injection(spec)
        assert "missing=<UNRESOLVED>" in desc

    def test_static_kwargs(self) -> None:
        """静态 kwargs 应显示具体值."""

        def fn(flag: bool = False) -> None:
            return None

        spec = px.TaskSpec("t", fn, kwargs={"flag": True})
        desc = describe_injection(spec)
        assert "flag=True" in desc

    def test_positional_args_filled(self) -> None:
        """spec.args 填充的位置参数应显示具体值（覆盖 args_filled 分支）."""

        def fn(a: int, b: str) -> None:
            return None

        spec = px.TaskSpec("t", fn, args=(1, "x"))
        desc = describe_injection(spec)
        assert "a=1" in desc
        assert "b='x'" in desc


class TestIsContextAnnotation:
    """测试 _is_context_annotation 函数."""

    def test_direct_object(self) -> None:
        """直接传入 Context 别名对象应返回 True."""
        assert _is_context_annotation(px.Context) is True

    def test_string(self) -> None:
        """字符串形式的注解应被识别."""
        assert _is_context_annotation("Context") is True
        assert _is_context_annotation("px.Context") is True
        assert _is_context_annotation("pyflowx.Context") is True
        assert _is_context_annotation("NotContext") is False
        assert _is_context_annotation("int") is False

    def test_typing_alias(self) -> None:
        """具有 __name__/_name 为 Context/Mapping 的 typing 别名应返回 True."""

        class FakeAlias:
            __name__ = "Context"

        assert _is_context_annotation(FakeAlias()) is True

        class FakeMapping:
            __name__ = "Mapping"

        assert _is_context_annotation(FakeMapping()) is True

    def test_other(self) -> None:
        """其他类型注解应返回 False."""
        assert _is_context_annotation(int) is False
        assert _is_context_annotation(str) is False
        assert _is_context_annotation(None) is False
