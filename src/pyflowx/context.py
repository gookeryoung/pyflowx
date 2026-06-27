"""上下文注入：把上游结果转换为函数参数。

本机制让用户可以编写普通函数，其参数名*就是*依赖声明，从而消除其他
DAG 库中泛滥的样板包装器。

注入规则（按顺序求值）
----------------------
1. **标注为** :class:`Context` 的参数接收完整结果映射（含硬依赖与软依赖）。
2. **名称匹配某个依赖**（硬或软）的参数接收该依赖的结果。
3. ``**kwargs`` 参数以 dict 形式接收*所有*依赖结果。
4. ``TaskSpec.args`` / ``TaskSpec.kwargs`` 为*非依赖*参数提供静态值。

若某参数无法解析且无默认值，则抛出 :class:`~pyflowx.errors.InjectionError`。
"""

from __future__ import annotations

import inspect
from typing import Any, Mapping

from .errors import InjectionError
from .task import Context, TaskSpec

__all__ = ["Context", "_is_context_annotation", "build_call_args", "describe_injection"]


def _is_context_annotation(annotation: Any) -> bool:
    """判断参数标注是否为（或指向）``Context``。"""
    if annotation is Context:
        return True
    if isinstance(annotation, str):
        return annotation == "Context" or annotation.endswith(".Context")
    name = getattr(annotation, "__name__", None) or getattr(annotation, "_name", None)
    return name in ("Context", "Mapping")


def build_call_args(
    spec: TaskSpec[Any],
    context: Mapping[str, Any],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """解析用于调用 ``spec.fn`` 的 ``(args, kwargs)``。

    ``context`` 必须已包含所有硬依赖与软依赖的结果（软依赖被跳过时由
    执行器填入 :attr:`TaskSpec.defaults` 中的默认值）。
    """
    fn = spec.effective_fn
    sig = inspect.signature(fn)
    params = sig.parameters

    var_keyword = next(
        (p for p in params.values() if p.kind == inspect.Parameter.VAR_KEYWORD),
        None,
    )

    # 本任务相关的上下文子集：硬依赖 + 软依赖。
    all_deps = set(spec.depends_on) | set(spec.soft_depends_on)
    dep_context: dict[str, Any] = {name: context[name] for name in all_deps if name in context}

    collisions = set(spec.kwargs) & set(dep_context)
    if collisions:
        raise InjectionError(
            spec.name,
            f"static kwargs {sorted(collisions)} collide with dependency names; "
            + "rename the static kwarg or the dependency.",
        )

    injected_kwargs: dict[str, Any] = {}
    leftover_dep_results: dict[str, Any] = dict(dep_context)

    positional_params: list[str] = []
    positional_kinds = (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    for pname, param in params.items():
        if param.kind in positional_kinds:
            positional_params.append(pname)
    args_filled: set[str] = set(positional_params[: len(spec.args)])

    for pname, param in params.items():
        if pname in args_filled:
            continue

        if _is_context_annotation(param.annotation):
            injected_kwargs[pname] = dep_context
            continue

        if pname in dep_context:
            injected_kwargs[pname] = dep_context[pname]
            leftover_dep_results.pop(pname, None)
            continue

        if pname in spec.kwargs:
            injected_kwargs[pname] = spec.kwargs[pname]
            continue

        if param.default is inspect.Parameter.empty and param.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            raise InjectionError(
                spec.name,
                f"parameter {pname!r} has no dependency, static value, or default.",
            )

    if var_keyword is not None and leftover_dep_results:
        merged = dict(spec.kwargs)
        merged.update(injected_kwargs)
        merged.update(leftover_dep_results)
        injected_kwargs = merged

    return tuple(spec.args), injected_kwargs


def describe_injection(spec: TaskSpec[Any]) -> str:
    """生成任务参数注入方式的人类可读描述。供 ``dry_run`` 使用。"""
    fn = spec.effective_fn
    sig = inspect.signature(fn)
    positional_params = [
        p
        for p, param in sig.parameters.items()
        if param.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    args_filled = set(positional_params[: len(spec.args)])
    all_deps = set(spec.depends_on) | set(spec.soft_depends_on)
    parts = []
    for pname, param in sig.parameters.items():
        if pname in args_filled:
            idx = positional_params.index(pname)
            parts.append(f"{pname}={spec.args[idx]!r}")
        elif _is_context_annotation(param.annotation):
            parts.append(f"{pname}=<Context>")
        elif pname in all_deps:
            tag = "soft" if pname in spec.soft_depends_on else "dep"
            parts.append(f"{pname}=<{tag}:{pname}>")
        elif pname in spec.kwargs:
            parts.append(f"{pname}={spec.kwargs[pname]!r}")
        elif param.default is not inspect.Parameter.empty:
            parts.append(f"{pname}=<default>")
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            parts.append("**kwargs=<all-deps>")
        elif param.kind == inspect.Parameter.VAR_POSITIONAL:
            parts.append("*args")
        else:
            parts.append(f"{pname}=<UNRESOLVED>")
    return f"{spec.name}({', '.join(parts)})"
