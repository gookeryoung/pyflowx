"""DAG 构建、校验、分层与可视化。

使用标准库的 :mod:`graphlib`（3.9+）或 :mod:`graphlib_backport`（3.8）
进行拓扑排序。图以增量方式构建并即时校验，使配置错误在构建时（而非
执行时）快速失败。
"""

from __future__ import annotations

import sys
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple

from .errors import CycleError, DuplicateTaskError, MissingDependencyError
from .task import TaskSpec

# graphlib 自 3.9 起进入标准库；3.8 回退到 backport。
if sys.version_info >= (3, 9):  # pragma: no cover
    import graphlib

    _TopologicalSorter = graphlib.TopologicalSorter
else:  # pragma: no cover
    import graphlib  # type: ignore[import-untyped]  # pragma: no cover

    _TopologicalSorter = graphlib.TopologicalSorter  # pragma: no cover


class Graph:
    """校验后不可变的有向无环任务图。

    通过添加 :class:`~pyflowx.task.TaskSpec` 实例构建。每次 ``add`` 都
    执行即时校验（重名、缺失依赖），:meth:`validate` / :meth:`layers`
    执行完整 DAG 校验（环检测）与拓扑分层。

    图仅持有*配置*；运行时状态存于 :class:`~pyflowx.report.RunReport`。
    这使图可安全重复运行并在线程间共享。
    """

    def __init__(self) -> None:
        self._specs: Dict[str, TaskSpec[object]] = {}
        # 任务 -> 其直接依赖（前驱）。
        self._deps: Dict[str, Tuple[str, ...]] = {}

    # ------------------------------------------------------------------ #
    # 构建
    # ------------------------------------------------------------------ #
    def add(self, spec: TaskSpec[object]) -> "Graph":
        """注册一个任务 spec，并即时校验。

        返回 ``self`` 以支持链式调用，但推荐入口是 :meth:`from_specs`，
        它会整批校验（允许单次调用中的前向引用）。
        """
        if spec.name in self._specs:
            raise DuplicateTaskError(spec.name)
        self._specs[spec.name] = spec
        self._deps[spec.name] = spec.depends_on
        # 为增量 API 即时检查重名与缺失依赖。
        self._validate_references()
        return self

    @classmethod
    def from_specs(cls, specs: Iterable[TaskSpec[object]]) -> "Graph":
        """从可迭代的 task spec 构建图。

        先收集所有 spec，再统一校验。这意味着任务可以引用*后出现*的
        依赖——顺序无关，就像声明式配置文件的读取方式。
        """
        graph = cls()
        for spec in specs:
            if spec.name in graph._specs:
                raise DuplicateTaskError(spec.name)
            graph._specs[spec.name] = spec
            graph._deps[spec.name] = spec.depends_on
        graph._validate_references()
        graph.validate()
        return graph

    # ------------------------------------------------------------------ #
    # 校验
    # ------------------------------------------------------------------ #
    def _validate_references(self) -> None:
        """确保每个依赖名都存在于图中。"""
        for name, deps in self._deps.items():
            for dep in deps:
                if dep not in self._specs:
                    raise MissingDependencyError(name, dep)

    def validate(self) -> None:
        """执行完整 DAG 校验。

        存在环时抛出 :class:`~pyflowx.errors.CycleError`。
        依赖存在性由 :meth:`_validate_references` 检查。
        """
        self._validate_references()
        sorter = _TopologicalSorter(self._deps)
        try:
            # prepare() 在有环时抛出 CycleError；此处不需要
            # static_order() 的结果，仅利用其校验副作用。
            sorter.prepare()
        except graphlib.CycleError as exc:
            # exc.args[1] 是构成环的节点列表。
            cycle: Sequence[str] = exc.args[1] if len(exc.args) > 1 else []
            raise CycleError(list(cycle)) from exc

    # ------------------------------------------------------------------ #
    # 内省
    # ------------------------------------------------------------------ #
    @property
    def names(self) -> List[str]:
        """所有已注册任务名（按插入顺序）。"""
        return list(self._specs.keys())

    def spec(self, name: str) -> TaskSpec[object]:
        """返回 ``name`` 的 spec；不存在则 ``KeyError``。"""
        return self._specs[name]

    def dependencies(self, name: str) -> Tuple[str, ...]:
        """``name`` 的直接前驱。"""
        return self._deps[name]

    def all_specs(self) -> Mapping[str, TaskSpec[object]]:
        """name -> spec 的只读视图。"""
        return self._specs

    def layers(self) -> List[List[str]]:
        """将任务分组为可并行执行的层（Kahn 算法）。

        同层任务无相互依赖，可并发执行。层按执行顺序返回。

        图有环时抛出 :class:`~pyflowx.errors.CycleError`。
        """
        self.validate()
        sorter = _TopologicalSorter(self._deps)
        result: List[List[str]] = []
        # ``get_ready`` + ``done`` 每次给出一层，正好是并行执行所需的分组。
        sorter.prepare()
        while sorter.is_active():
            ready = list(sorter.get_ready())
            # 排序以保证确定性、可复现的执行计划。
            ready.sort()
            result.append(ready)
            for node in ready:
                sorter.done(node)
        return result

    # ------------------------------------------------------------------ #
    # 子图 / 标签过滤
    # ------------------------------------------------------------------ #
    def subgraph(self, tags: Iterable[str]) -> "Graph":
        """返回仅包含匹配任意标签的任务的新图。

        依赖会被修剪，仅保留被保留任务之间的边；指向被丢弃任务的边
        会被移除（被保留的任务不再等待它们）。用于调试时运行大型
        DAG 的切片。
        """
        wanted: Set[str] = set(tags)
        kept: List[TaskSpec[object]] = []
        for spec in self._specs.values():
            if wanted & set(spec.tags):
                pruned_deps = tuple(
                    d
                    for d in spec.depends_on
                    if d in self._specs and (wanted & set(self._specs[d].tags))
                )
                kept.append(
                    TaskSpec(
                        name=spec.name,
                        fn=spec.fn,
                        depends_on=pruned_deps,
                        args=spec.args,
                        kwargs=spec.kwargs,
                        retries=spec.retries,
                        timeout=spec.timeout,
                        tags=spec.tags,
                    )
                )
        return Graph.from_specs(kept)

    def subgraph_by_names(self, names: Iterable[str]) -> "Graph":
        """返回限定于 ``names`` 的新图（边已修剪）。"""
        wanted: Set[str] = set(names)
        for n in wanted:
            if n not in self._specs:
                raise KeyError(f"Unknown task name: {n!r}")
        kept: List[TaskSpec[object]] = []
        for spec in self._specs.values():
            if spec.name in wanted:
                pruned_deps = tuple(d for d in spec.depends_on if d in wanted)
                kept.append(
                    TaskSpec(
                        name=spec.name,
                        fn=spec.fn,
                        depends_on=pruned_deps,
                        args=spec.args,
                        kwargs=spec.kwargs,
                        retries=spec.retries,
                        timeout=spec.timeout,
                        tags=spec.tags,
                    )
                )
        return Graph.from_specs(kept)

    # ------------------------------------------------------------------ #
    # 可视化
    # ------------------------------------------------------------------ #
    def to_mermaid(self, orientation: str = "TD") -> str:
        """将 DAG 渲染为 Mermaid ``graph`` 定义字符串。

        无外部依赖；输出可粘贴到 Markdown、由 VS Code 的 Mermaid 预览
        渲染，或保存为文件。
        """
        valid = {"TD", "TB", "BT", "LR", "RL"}
        orientation = orientation.upper()
        if orientation not in valid:
            raise ValueError(
                f"Invalid orientation {orientation!r}; expected one of {sorted(valid)}."
            )
        lines: List[str] = [f"graph {orientation}"]
        for name in self._specs:
            lines.append(f'    {name}["{name}"]')
        for name, deps in self._deps.items():
            for dep in deps:
                lines.append(f"    {dep} --> {name}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ #
    # 调试
    # ------------------------------------------------------------------ #
    def describe(self) -> str:
        """用于调试的人类可读多行摘要。"""
        out: List[str] = [f"Graph(tasks={len(self._specs)})"]
        for layer_idx, layer in enumerate(self.layers(), 1):
            out.append(f"  Layer {layer_idx}: {layer}")
        return "\n".join(out)

    def __repr__(self) -> str:
        return f"Graph(tasks={len(self._specs)})"

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, name: object) -> bool:
        return name in self._specs
