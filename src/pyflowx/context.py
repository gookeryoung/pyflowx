"""Context injection: turn upstream results into function arguments.

This is the mechanism that lets users write plain functions whose
parameter names *are* the dependency declarations, removing the boiler-
plate wrappers that plague other DAG libraries (e.g. ``def wrapper():
return fn(workflow.get_task_result('x'))``).

Injection rules (evaluated in order)
-----------------------------------
1. A parameter whose **annotation is** :class:`Context` receives the full
   result mapping. Useful for tasks that need to iterate over all inputs.
2. A parameter whose **name matches a dependency** receives that
   dependency's result.
3. A ``**kwargs`` parameter receives *all* dependency results as a dict.
4. ``TaskSpec.args`` / ``TaskSpec.kwargs`` supply static values for
   parameters that are *not* dependencies.

If a parameter cannot be resolved and has no default, an
:class:`~pyflowx.errors.InjectionError` is raised with a precise message.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, List, Mapping, Set, Tuple

from .errors import InjectionError
from .task import Context, TaskSpec

__all__ = ["Context", "build_call_args", "describe_injection"]


def _is_context_annotation(annotation: Any) -> bool:
    """True when a parameter annotation is (or refers to) ``Context``.

    Handles three forms:
    * the ``Context`` alias object itself;
    * a typing alias whose ``__name__``/``_name`` is ``Context`` or ``Mapping``;
    * a *string* annotation (``from __future__ import annotations`` makes all
      annotations strings at runtime) such as ``"Context"`` or ``"px.Context"``.
    """
    if annotation is Context:
        return True
    # String annotation from `from __future__ import annotations`.
    if isinstance(annotation, str):
        # Match "Context", "px.Context", "pyflowx.Context", etc.
        return annotation == "Context" or annotation.endswith(".Context")
    # Match by qualified name to support ``from pyflowx import Context``
    # re-exports.
    name = getattr(annotation, "__name__", None) or getattr(annotation, "_name", None)
    if name in ("Context", "Mapping"):
        return True
    return False


def build_call_args(
    spec: TaskSpec[object],
    context: Mapping[str, Any],
) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    """Resolve the ``(args, kwargs)`` to call ``spec.fn`` with.

    Parameters
    ----------
    spec:
        The task spec, providing ``fn``, ``depends_on``, ``args``, ``kwargs``.
    context:
        Mapping of dependency-name -> result value. Only the task's own
        ``depends_on`` entries are guaranteed present; other tasks' results
        are excluded to keep injection deterministic.

    Returns
    -------
    (args, kwargs)
        Ready to splat into ``spec.fn(*args, **kwargs)``.

    Raises
    ------
    InjectionError
        If a required parameter cannot be satisfied, or if static
        ``kwargs`` collide with an injected dependency name.
    """
    sig = inspect.signature(spec.fn)
    params = sig.parameters

    # Detect special parameter kinds.
    var_keyword = next(
        (p for p in params.values() if p.kind == inspect.Parameter.VAR_KEYWORD),
        None,
    )

    # The subset of context relevant to this task.
    dep_context: Dict[str, Any] = {
        name: context[name] for name in spec.depends_on if name in context
    }

    # Detect collisions between static kwargs and dependency names.
    collisions = set(spec.kwargs) & set(dep_context)
    if collisions:
        raise InjectionError(
            spec.name,
            f"static kwargs {sorted(collisions)} collide with dependency names; "
            "rename the static kwarg or the dependency.",
        )

    injected_kwargs: Dict[str, Any] = {}
    leftover_dep_results: Dict[str, Any] = dict(dep_context)

    # Positional parameters consumed by spec.args. We track which param
    # names are filled positionally so they are skipped during name-based
    # injection (dependency / Context / static kwargs).
    positional_params: List[str] = []
    positional_kinds = (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    for pname, param in params.items():
        if param.kind in positional_kinds:
            positional_params.append(pname)
    # The first len(spec.args) positional params are filled by spec.args.
    args_filled: Set[str] = set(positional_params[: len(spec.args)])

    for pname, param in params.items():
        # Skip params already filled by positional spec.args.
        if pname in args_filled:
            continue

        # Rule 1: annotated as Context -> full mapping.
        if _is_context_annotation(param.annotation):
            injected_kwargs[pname] = dep_context
            continue

        # Rule 2: name matches a dependency.
        if pname in dep_context:
            injected_kwargs[pname] = dep_context[pname]
            leftover_dep_results.pop(pname, None)
            continue

        # Rule 3: handled after the loop via **kwargs.

        # Rule 4: static kwargs fill the rest.
        if pname in spec.kwargs:
            injected_kwargs[pname] = spec.kwargs[pname]
            continue

        # No source for this parameter: must have a default, else error.
        if param.default is inspect.Parameter.empty and param.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            raise InjectionError(
                spec.name,
                f"parameter {pname!r} has no dependency, static value, or default.",
            )

    # Rule 3: **kwargs swallows remaining dependency results.
    if var_keyword is not None and leftover_dep_results:
        # Merge static kwargs first, then dependency results (static wins
        # on collision — but we already rejected collisions above).
        merged = dict(spec.kwargs)
        merged.update(injected_kwargs)
        merged.update(leftover_dep_results)
        injected_kwargs = merged

    return tuple(spec.args), injected_kwargs


def describe_injection(spec: TaskSpec[object]) -> str:
    """Human-readable description of how a task's args will be injected.

    Used by ``dry_run`` to show the execution plan without executing it.
    """
    sig = inspect.signature(spec.fn)
    # Determine which positional params are filled by spec.args.
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
