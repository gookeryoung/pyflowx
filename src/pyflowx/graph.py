"""DAG 构建、校验、分层与可视化。

使用标准库的 :mod:`graphlib`（3.9+）或 :mod:`graphlib_backport`（3.8）
进行拓扑排序。图以增量方式构建并即时校验，使配置错误在构建时（而非执行时）快速失败。

支持：
* 图级默认值 :class:`GraphDefaults`，TaskSpec 字段为 ``None`` 时回退。
* :meth:`Graph.map` 工厂批量生成 fan-out 任务。
* 字符串引用与 :func:`compose` 编程式组合多个图。
* 软依赖：仅用于上下文注入，不参与拓扑分层。
"""

from __future__ import annotations

__all__ = [
    "Graph",
    "GraphDefaults",
]

import sys
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Mapping, Sequence

from .errors import CycleError, DuplicateTaskError, MissingDependencyError
from .task import RetryPolicy, TaskSpec

if sys.version_info >= (3, 9):  # pragma: no cover
    import graphlib  # pyright: ignore[reportUnreachable]

    _TopologicalSorter = graphlib.TopologicalSorter
else:  # pragma: no cover
    import graphlib  # type: ignore[import-untyped]

    _TopologicalSorter = graphlib.TopologicalSorter  # pragma: no cover


@dataclass
class GraphDefaults:
    """图级默认值。TaskSpec 对应字段为 ``None`` 时回退到此处。

    仅对可空字段生效（retry/timeout/strategy/env/cwd/tags/priority/
    continue_on_error/concurrency_key）。非空字段（name/fn/cmd）不回退。
    """

    retry: RetryPolicy | None = None
    timeout: float | None = None
    strategy: str | None = None
    tags: tuple[str, ...] = ()
    env: Mapping[str, str] | None = None
    cwd: Any = None  # Path | None
    priority: int = 0
    continue_on_error: bool = False
    concurrency_key: str | None = None
    verbose: bool = False


def _prune_deps(spec: TaskSpec[Any], keep: Callable[[str], bool]) -> TaskSpec[Any]:
    """返回新 spec，其 ``depends_on`` / ``soft_depends_on`` 仅保留 ``keep(dep)`` 为真的依赖。"""
    return replace(
        spec,
        depends_on=tuple(d for d in spec.depends_on if keep(d)),
        soft_depends_on=tuple(d for d in spec.soft_depends_on if keep(d)),
    )


@dataclass
class Graph:
    """校验后的有向无环任务图。

    通过添加 :class:`~pyflowx.task.TaskSpec` 实例构建。每次 ``add`` 都
    执行即时校验（重名、缺失依赖），:meth:`validate` / :meth:`layers`
    执行完整 DAG 校验（环检测）与拓扑分层。

    图仅持有*配置*；运行时状态存于 :class:`~pyflowx.report.RunReport`。
    这使图可安全重复运行并在线程间共享。
    """

    specs: dict[str, TaskSpec[Any]] = field(default_factory=dict)
    deps: dict[str, tuple[str, ...]] = field(default_factory=dict)
    defaults: GraphDefaults = field(default_factory=GraphDefaults)

    # 待解析的字符串引用列表（由 GraphComposer 消费）；为空表示无引用。
    _pending_refs: list[str] = field(default_factory=list)

    # resolved_spec 缓存：避免执行期每个任务多次重复 dataclasses.replace 判断。
    # 在 specs / defaults 变更时失效。
    _resolved_cache: dict[str, TaskSpec[Any]] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # 构建
    # ------------------------------------------------------------------ #
    def add(self, spec: TaskSpec[Any]) -> Graph:
        """注册一个任务 spec，并即时校验。返回 ``self`` 支持链式调用。"""
        self._register(spec)
        self._validate_references()
        return self

    def _register(self, spec: TaskSpec[Any]) -> None:
        if spec.name in self.specs:
            raise DuplicateTaskError(spec.name)
        self.specs[spec.name] = spec
        # 拓扑依赖仅含硬依赖；软依赖仅用于注入，不影响分层。
        self.deps[spec.name] = spec.depends_on
        self._resolved_cache.clear()

    @classmethod
    def from_specs(
        cls,
        specs: Iterable[TaskSpec[Any] | str],
        defaults: GraphDefaults | None = None,
    ) -> Graph:
        """从可迭代的 task spec 构建图。

        先收集所有 spec，再统一校验。允许前向引用。支持字符串引用，
        由 :func:`compose` 或 :class:`GraphComposer` 解析展开。

        Parameters
        ----------
        specs:
            TaskSpec 对象或字符串引用的列表。
        defaults:
            图级默认值。``None`` 使用空 :class:`GraphDefaults`。
        """
        graph = cls(defaults=defaults or GraphDefaults())
        pending_refs: list[str] = []

        for spec in specs:
            if isinstance(spec, str):
                pending_refs.append(spec)
            elif isinstance(spec, TaskSpec):
                graph._register(spec)
            else:
                raise TypeError(f"from_specs 只接受 TaskSpec 或 str，收到: {type(spec)}")

        if pending_refs:
            graph._pending_refs = pending_refs

        graph._validate_references()
        graph.validate()
        return graph

    # ------------------------------------------------------------------ #
    # 校验
    # ------------------------------------------------------------------ #
    def _validate_references(self) -> None:
        """确保每个依赖名都存在于图中。硬依赖与软依赖都校验。"""
        for name, spec in self.specs.items():
            for dep in spec.depends_on:
                if dep not in self.specs:
                    raise MissingDependencyError(name, dep)
            for dep in spec.soft_depends_on:
                if dep not in self.specs:
                    raise MissingDependencyError(name, dep)

    def validate(self) -> None:
        """执行完整 DAG 校验。存在环时抛出 :class:`CycleError`。"""
        self._validate_references()
        sorter = _TopologicalSorter(self.deps)
        try:
            sorter.prepare()
        except graphlib.CycleError as exc:  # type: ignore[name-defined]
            cycle: Sequence[str] = exc.args[1] if len(exc.args) > 1 else []
            raise CycleError(list(cycle)) from exc

    # ------------------------------------------------------------------ #
    # 内省
    # ------------------------------------------------------------------ #
    @property
    def names(self) -> list[str]:
        """所有已注册任务名（按插入顺序）。"""
        return list(self.specs.keys())

    def spec(self, name: str) -> TaskSpec[Any]:
        """返回 ``name`` 的 spec；不存在则 ``KeyError``。"""
        return self.specs[name]

    def resolved_spec(self, name: str) -> TaskSpec[Any]:
        """返回应用图级默认值后的 spec（不修改原图）。

        对于 ``retry``/``timeout``/``strategy``/``env``/``cwd`` 等可空
        字段，若 spec 字段为默认空值且图级默认值非空，则用
        :func:`dataclasses.replace` 生成带默认值的副本。

        结果按 ``name`` 缓存；specs / defaults 变更时缓存失效。
        """
        cached = self._resolved_cache.get(name)
        if cached is not None:
            return cached
        spec = self.specs[name]
        d = self.defaults
        overrides: dict[str, Any] = {}
        if spec.retry == RetryPolicy() and d.retry is not None:
            overrides["retry"] = d.retry
        if spec.timeout is None and d.timeout is not None:
            overrides["timeout"] = d.timeout
        if spec.strategy is None and d.strategy is not None:
            overrides["strategy"] = d.strategy
        if spec.env is None and d.env is not None:
            overrides["env"] = d.env
        if spec.cwd is None and d.cwd is not None:
            overrides["cwd"] = d.cwd
        if spec.priority == 0 and d.priority != 0:
            overrides["priority"] = d.priority
        if not spec.continue_on_error and d.continue_on_error:
            overrides["continue_on_error"] = True
        if spec.concurrency_key is None and d.concurrency_key is not None:
            overrides["concurrency_key"] = d.concurrency_key
        if not spec.verbose and d.verbose:
            overrides["verbose"] = True
        if not spec.tags and d.tags:
            overrides["tags"] = d.tags
        resolved = spec if not overrides else replace(spec, **overrides)
        self._resolved_cache[name] = resolved
        return resolved

    def dependencies(self, name: str) -> tuple[str, ...]:
        """``name`` 的直接硬依赖前驱。"""
        return self.deps[name]

    def all_deps(self, name: str) -> tuple[str, ...]:
        """``name`` 的硬依赖 + 软依赖。"""
        spec = self.specs[name]
        return tuple(spec.depends_on) + tuple(spec.soft_depends_on)

    def all_specs(self) -> Mapping[str, TaskSpec[Any]]:
        """name -> spec 的只读视图。"""
        return self.specs

    def layers(self) -> list[list[str]]:
        """将任务分组为可并行执行的层（Kahn 算法）。

        同层任务无相互硬依赖，可并发执行。软依赖不参与分层。
        层按执行顺序返回。图有环时抛出 :class:`CycleError`。

        .. note::
            本方法假定图已通过 :meth:`validate` 校验（由 :func:`pyflowx.run`
            在入口统一执行一次）。若直接调用本方法，需自行先校验。
        """
        sorter = _TopologicalSorter(self.deps)
        result: list[list[str]] = []
        sorter.prepare()
        while sorter.is_active():
            ready = list(sorter.get_ready())
            ready.sort()
            result.append(ready)
            for node in ready:
                sorter.done(node)
        return result

    # ------------------------------------------------------------------ #
    # 子图 / 标签过滤
    # ------------------------------------------------------------------ #
    def subgraph(self, tags: Iterable[str]) -> Graph:
        """返回仅包含匹配任意标签的任务的新图。依赖边被修剪。"""
        wanted: set[str] = set(tags)

        def _dep_kept(dep: str) -> bool:
            return dep in self.specs and bool(wanted & set(self.specs[dep].tags))

        kept: list[TaskSpec[Any]] = [
            _prune_deps(spec, _dep_kept) for spec in self.specs.values() if wanted & set(spec.tags)
        ]
        return Graph.from_specs(kept, defaults=self.defaults)

    def subgraph_by_names(self, names: Iterable[str]) -> Graph:
        """返回限定于 ``names`` 的新图（边已修剪）。"""
        wanted: set[str] = set(names)
        for n in wanted:
            if n not in self.specs:
                raise KeyError(f"Unknown task name: {n!r}")
        kept: list[TaskSpec[Any]] = [
            _prune_deps(spec, lambda d: d in wanted) for spec in self.specs.values() if spec.name in wanted
        ]
        return Graph.from_specs(kept, defaults=self.defaults)

    # ------------------------------------------------------------------ #
    # Fan-out / map-reduce
    # ------------------------------------------------------------------ #
    def map(
        self,
        name_fn: Callable[[int], str],
        spec: TaskSpec[Any],
        items: Sequence[Any],
        arg_factory: Callable[[Any], tuple[Any, ...]] | None = None,
        depends_on_per: Callable[[int], tuple[str, ...]] | None = None,
    ) -> list[TaskSpec[Any]]:
        """为 ``items`` 中每个元素生成一个 TaskSpec 并加入图。

        用于 fan-out / map-reduce 模式。返回生成的 spec 列表，便于
        后续 reduce 任务依赖。

        Parameters
        ----------
        name_fn:
            接受索引 ``i``，返回任务名。需保证唯一。
        spec:
            模板 spec。其 ``name`` 与 ``args`` 会被覆盖。
        items:
            待分发的数据序列。
        arg_factory:
            接受一个 item，返回位置参数元组，覆盖 spec.args。
            ``None`` 则将单个 item 作为唯一位置参数。
        depends_on_per:
            接受索引 ``i``，返回该任务的额外硬依赖。``None`` 则继承 spec.depends_on。

        Returns
        -------
        list[TaskSpec]
            生成的 spec 列表（已加入图）。

        Examples
        --------
        >>> fetch_tmpl = px.TaskSpec("", fn=fetch_user)
        >>> specs = graph.map(lambda i: f"fetch_{i}", fetch_tmpl, [1, 2, 3])
        >>> reduce_spec = px.TaskSpec("reduce", fn=reduce_fn, depends_on=tuple(s.name for s in specs))
        """
        generated: list[TaskSpec[Any]] = []
        for i, item in enumerate(items):
            name = name_fn(i)
            args = arg_factory(item) if arg_factory is not None else (item,)
            extra_deps = depends_on_per(i) if depends_on_per is not None else ()
            new_spec = replace(
                spec,
                name=name,
                args=tuple(args),
                depends_on=tuple(spec.depends_on) + tuple(extra_deps),
            )
            self.add(new_spec)
            generated.append(new_spec)
        return generated

    # ------------------------------------------------------------------ #
    # 可视化
    # ------------------------------------------------------------------ #
    def to_mermaid(self, orientation: str = "TD") -> str:
        """将 DAG 渲染为 Mermaid ``graph`` 定义字符串。"""
        valid = {"TD", "TB", "BT", "LR", "RL"}
        orientation = orientation.upper()
        if orientation not in valid:
            raise ValueError(f"Invalid orientation {orientation!r}; expected one of {sorted(valid)}.")
        lines: list[str] = [f"graph {orientation}"]
        for name in self.specs:
            lines.append(f'    {name}["{name}"]')
        for name, deps in self.deps.items():
            for dep in deps:
                lines.append(f"    {dep} --> {name}")
        # 软依赖用虚线
        for name, spec in self.specs.items():
            for dep in spec.soft_depends_on:
                lines.append(f"    {dep} -.-> {name}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ #
    # 调试
    # ------------------------------------------------------------------ #
    def describe(self) -> str:
        """用于调试的人类可读多行摘要。"""
        out: list[str] = [f"Graph(tasks={len(self.specs)})"]
        for layer_idx, layer in enumerate(self.layers(), 1):
            out.append(f"  Layer {layer_idx}: {layer}")
        return "\n".join(out)

    def __repr__(self) -> str:
        return f"Graph(tasks={len(self.specs)})"

    def __len__(self) -> int:
        return len(self.specs)

    def __contains__(self, name: Any) -> bool:
        return name in self.specs
