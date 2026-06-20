"""上下文注入：把上游结果转换为函数参数。

本机制让用户可以编写普通函数，其参数名*就是*依赖声明，从而消除其他
DAG 库中泛滥的样板包装器（如 ``def wrapper(): return fn(workflow.get_task_result('x'))``）。

注入规则（按顺序求值）
----------------------
1. **标注为** :class:`Context` 的参数接收完整结果映射。适用于需要遍历
   所有输入的任务。
2. **名称匹配某个依赖**的参数接收该依赖的结果。
3. ``**kwargs`` 参数以 dict 形式接收*所有*依赖结果。
4. ``TaskSpec.args`` / ``TaskSpec.kwargs`` 为*非依赖*参数提供静态值。

若某参数无法解析且无默认值，则抛出 :class:`~pyflowx.errors.InjectionError`，
并附带精确错误信息。
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, List, Mapping, Set, Tuple

from .errors import InjectionError
from .task import Context, TaskSpec

__all__ = ["Context", "build_call_args", "describe_injection", "_is_context_annotation"]


def _is_context_annotation(annotation: Any) -> bool:
    """判断参数标注是否为（或指向）``Context``。

    处理三种形式：
    * ``Context`` 别名对象本身；
    * ``__name__``/``_name`` 为 ``Context`` 或 ``Mapping`` 的 typing 别名；
    * *字符串*标注（``from __future__ import annotations`` 会在运行时
      把所有标注变为字符串），如 ``"Context"`` 或 ``"px.Context"``。
    """
    if annotation is Context:
        return True
    # `from __future__ import annotations` 产生的字符串标注。
    if isinstance(annotation, str):
        # 匹配 "Context"、"px.Context"、"pyflowx.Context" 等。
        return annotation == "Context" or annotation.endswith(".Context")
    # 按限定名匹配，支持 ``from pyflowx import Context`` 再导出。
    name = getattr(annotation, "__name__", None) or getattr(annotation, "_name", None)
    if name in ("Context", "Mapping"):
        return True
    return False


def build_call_args(
    spec: TaskSpec[object],
    context: Mapping[str, Any],
) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    """解析用于调用 ``spec.fn`` 的 ``(args, kwargs)``。

    参数
    ----
    spec:
        任务 spec，提供 ``fn``、``depends_on``、``args``、``kwargs``。
    context:
        依赖名 -> 结果值的映射。仅保证本任务自身的 ``depends_on`` 条目
        存在；其他任务的结果被排除，以保持注入的确定性。

    返回
    ----
    (args, kwargs)
        可直接展开为 ``spec.fn(*args, **kwargs)``。

    抛出
    ----
    InjectionError
        若必需参数无法满足，或静态 ``kwargs`` 与注入依赖名冲突。
    """
    # 使用 effective_fn 而不是 fn，以支持 cmd 参数
    fn = spec.effective_fn
    sig = inspect.signature(fn)
    params = sig.parameters

    # 检测特殊参数类型。
    var_keyword = next(
        (p for p in params.values() if p.kind == inspect.Parameter.VAR_KEYWORD),
        None,
    )

    # 与本任务相关的上下文子集。
    dep_context: Dict[str, Any] = {
        name: context[name] for name in spec.depends_on if name in context
    }

    # 检测静态 kwargs 与依赖名的冲突。
    collisions = set(spec.kwargs) & set(dep_context)
    if collisions:
        raise InjectionError(
            spec.name,
            f"static kwargs {sorted(collisions)} collide with dependency names; "
            "rename the static kwarg or the dependency.",
        )

    injected_kwargs: Dict[str, Any] = {}
    leftover_dep_results: Dict[str, Any] = dict(dep_context)

    # 被 spec.args 消费的位置参数。记录哪些参数名已被位置填充，
    # 以便在基于名称的注入（依赖 / Context / 静态 kwargs）时跳过。
    positional_params: List[str] = []
    positional_kinds = (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    for pname, param in params.items():
        if param.kind in positional_kinds:
            positional_params.append(pname)
    # 前 len(spec.args) 个位置参数由 spec.args 填充。
    args_filled: Set[str] = set(positional_params[: len(spec.args)])

    for pname, param in params.items():
        # 跳过已被位置 spec.args 填充的参数。
        if pname in args_filled:
            continue

        # 规则 1：标注为 Context -> 完整映射。
        if _is_context_annotation(param.annotation):
            injected_kwargs[pname] = dep_context
            continue

        # 规则 2：名称匹配某个依赖。
        if pname in dep_context:
            injected_kwargs[pname] = dep_context[pname]
            leftover_dep_results.pop(pname, None)
            continue

        # 规则 3：在循环后通过 **kwargs 处理。

        # 规则 4：静态 kwargs 填充其余参数。
        if pname in spec.kwargs:
            injected_kwargs[pname] = spec.kwargs[pname]
            continue

        # 该参数无来源：必须有默认值，否则报错。
        if param.default is inspect.Parameter.empty and param.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            raise InjectionError(
                spec.name,
                f"parameter {pname!r} has no dependency, static value, or default.",
            )

    # 规则 3：**kwargs 吞掉剩余依赖结果。
    if var_keyword is not None and leftover_dep_results:
        # 先合并静态 kwargs，再合并依赖结果（冲突已在上方拒绝）。
        merged = dict(spec.kwargs)
        merged.update(injected_kwargs)
        merged.update(leftover_dep_results)
        injected_kwargs = merged

    return tuple(spec.args), injected_kwargs


def describe_injection(spec: TaskSpec[object]) -> str:
    """生成任务参数注入方式的人类可读描述。

    供 ``dry_run`` 使用，在不执行的情况下展示执行计划。
    """
    # 使用 effective_fn 而不是 fn，以支持 cmd 参数
    fn = spec.effective_fn
    sig = inspect.signature(fn)
    # 确定哪些位置参数由 spec.args 填充。
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
    parts = []
    for pname, param in sig.parameters.items():
        if pname in args_filled:
            idx = positional_params.index(pname)
            parts.append(f"{pname}={spec.args[idx]!r}")
        elif _is_context_annotation(param.annotation):
            parts.append(f"{pname}=<Context>")
        elif pname in spec.depends_on:
            parts.append(f"{pname}=<result:{pname}>")
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
