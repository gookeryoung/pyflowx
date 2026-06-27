"""DAG 构建、校验、分层与可视化。

使用标准库的 :mod:`graphlib`（3.9+）或 :mod:`graphlib_backport`（3.8）
进行拓扑排序。图以增量方式构建并即时校验，使配置错误在构建时（而非执行时）快速失败。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

from .errors import CycleError, DuplicateTaskError, MissingDependencyError
from .task import TaskSpec

# graphlib 自 3.9 起进入标准库；3.8 回退到 backport。
if sys.version_info >= (3, 9):  # pragma: no cover
    import graphlib  # pyright: ignore[reportUnreachable]

    _TopologicalSorter = graphlib.TopologicalSorter
else:  # pragma: no cover
    import graphlib  # type: ignore[import-untyped]  # pragma: no cover

    _TopologicalSorter = graphlib.TopologicalSorter  # pragma: no cover


@dataclass
class Graph:
    """校验后的有向无环任务图。

    通过添加 :class:`~pyflowx.task.TaskSpec` 实例构建。每次 ``add`` 都
    执行即时校验（重名、缺失依赖），:meth:`validate` / :meth:`layers`
    执行完整 DAG 校验（环检测）与拓扑分层。

    图仅持有*配置*；运行时状态存于 :class:`~pyflowx.report.RunReport`。
    这使图可安全重复运行并在线程间共享。

    Note
    -----
    Graph 不再使用 ``frozen=True``：内部 ``specs``/``deps`` 本就是可变 dict，
    frozen 既无法真正保证不可变，又迫使 ``_pending_refs`` 等场景用
    ``object.__setattr__`` 绕过。改为普通 dataclass，让赋值显式且可审计。
    """

    specs: dict[str, TaskSpec[Any]] = field(default_factory=dict)
    deps: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # 待解析的字符串引用列表（由 GraphComposer 消费）；为空表示无引用。
    _pending_refs: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # 构建
    # ------------------------------------------------------------------ #
    def add(self, spec: TaskSpec[Any]) -> Graph:
        """注册一个任务 spec，并即时校验。

        返回 ``self`` 以支持链式调用，但推荐入口是 :meth:`from_specs`，
        它会整批校验（允许单次调用中的前向引用）。
        """
        if spec.name in self.specs:
            raise DuplicateTaskError(spec.name)
        self.specs[spec.name] = spec
        self.deps[spec.name] = spec.depends_on
        # 为增量 API 即时检查重名与缺失依赖。
        self._validate_references()
        return self

    @classmethod
    def from_specs(cls, specs: Iterable[TaskSpec[Any] | str]) -> Graph:
        """从可迭代的 task spec 构建图.

        先收集所有 spec，再统一校验。这意味着任务可以引用*后出现*的
        依赖——顺序无关，就像声明式配置文件的读取方式。

        支持字符串引用，允许引用其他命令图中的任务。
        字符串引用将在CliRunner中解析展开。

        Parameters
        ----------
        specs : Iterable[TaskSpec[Any] | str]
            TaskSpec对象或字符串引用的列表

        Returns
        -------
        Graph
            构建完成的图

        Note
        -----
        字符串引用格式：
        - "command_name" - 引用整个命令图
        - "command_name.task_name" - 引用特定任务

        Examples
        --------
        >>> graph = Graph.from_specs([
        ...     TaskSpec("build", cmd=["uv", "build"]),
        ...     "test",  # 引用test命令图
        ... ])
        """
        graph = cls()
        pending_refs: list[str] = []

        for spec in specs:
            if isinstance(spec, str):
                # 字符串引用，稍后解析
                pending_refs.append(spec)
            elif isinstance(spec, TaskSpec):
                if spec.name in graph.specs:
                    raise DuplicateTaskError(spec.name)
                graph.specs[spec.name] = spec
                graph.deps[spec.name] = spec.depends_on
            else:
                raise TypeError(f"from_specs只接受TaskSpec或str，收到: {type(spec)}")

        # 存储待解析的引用，稍后由 GraphComposer 解析展开。
        # Graph 不再 frozen，可直接赋值；保留属性名以保持向后兼容。
        if pending_refs:
            graph._pending_refs = pending_refs

        graph._validate_references()
        graph.validate()
        return graph

    # ------------------------------------------------------------------ #
    # 校验
    # ------------------------------------------------------------------ #
    def _validate_references(self) -> None:
        """确保每个依赖名都存在于图中。"""
        for name, deps in self.deps.items():
            for dep in deps:
                if dep not in self.specs:
                    raise MissingDependencyError(name, dep)

    def validate(self) -> None:
        """执行完整 DAG 校验。

        存在环时抛出 :class:`~pyflowx.errors.CycleError`。
        依赖存在性由 :meth:`_validate_references` 检查。
        """
        self._validate_references()
        sorter = _TopologicalSorter(self.deps)
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
    def names(self) -> list[str]:
        """所有已注册任务名（按插入顺序）。"""
        return list(self.specs.keys())

    def spec(self, name: str) -> TaskSpec[Any]:
        """返回 ``name`` 的 spec；不存在则 ``KeyError``。"""
        return self.specs[name]

    def dependencies(self, name: str) -> tuple[str, ...]:
        """``name`` 的直接前驱。"""
        return self.deps[name]

    def all_specs(self) -> Mapping[str, TaskSpec[Any]]:
        """name -> spec 的只读视图。"""
        return self.specs

    def layers(self) -> list[list[str]]:
        """将任务分组为可并行执行的层（Kahn 算法）。

        同层任务无相互依赖，可并发执行。层按执行顺序返回。

        图有环时抛出 :class:`~pyflowx.errors.CycleError`。
        """
        self.validate()
        sorter = _TopologicalSorter(self.deps)
        result: list[list[str]] = []
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
    def subgraph(self, tags: Iterable[str]) -> Graph:
        """返回仅包含匹配任意标签的任务的新图。

        依赖会被修剪，仅保留被保留任务之间的边；指向被丢弃任务的边
        会被移除（被保留的任务不再等待它们）。用于调试时运行大型
        DAG 的切片。
        """
        wanted: set[str] = set(tags)
        kept: list[TaskSpec[Any]] = []
        for spec in self.specs.values():
            if wanted & set(spec.tags):
                pruned_deps = tuple(
                    d for d in spec.depends_on if d in self.specs and (wanted & set(self.specs[d].tags))
                )
                # 使用 replace 保留所有字段（verbose/skip_if_missing/allow_upstream_skip 等），
                # 避免手动逐字段重建时遗漏新增字段。
                kept.append(replace(spec, depends_on=pruned_deps))
        return Graph.from_specs(kept)

    def subgraph_by_names(self, names: Iterable[str]) -> Graph:
        """返回限定于 ``names`` 的新图（边已修剪）。"""
        wanted: set[str] = set(names)
        for n in wanted:
            if n not in self.specs:
                raise KeyError(f"Unknown task name: {n!r}")
        kept: list[TaskSpec[Any]] = []
        for spec in self.specs.values():
            if spec.name in wanted:
                pruned_deps = tuple(d for d in spec.depends_on if d in wanted)
                kept.append(replace(spec, depends_on=pruned_deps))
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
            raise ValueError(f"Invalid orientation {orientation!r}; expected one of {sorted(valid)}.")
        lines: list[str] = [f"graph {orientation}"]
        for name in self.specs:
            lines.append(f'    {name}["{name}"]')
        for name, deps in self.deps.items():
            for dep in deps:
                lines.append(f"    {dep} --> {name}")
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


class GraphComposer:
    """将带字符串引用的图展开为纯 :class:`TaskSpec` 图。

    从 ``CliRunner`` 抽出，使 ``Graph``（数据）与引用解析（组合逻辑）
    职责分离。引用按顺序展开，后续引用的任务依赖前面引用的最后一个任务；
    原始 ``TaskSpec`` 之间也按出现顺序串行依赖。

    引用格式
    --------
    * ``"command_name"`` —— 引用整个命令图。
    * ``"command_name.task_name"`` —— 引用特定任务。

    Parameters
    ----------
    graphs : dict[str, Graph]
        命令名到图的映射，引用据此解析。
    """

    def __init__(self, graphs: dict[str, Graph]) -> None:
        self.graphs = graphs

    def resolve_all(self) -> dict[str, Graph]:
        """解析所有图的字符串引用，返回展开后的新图映射。"""
        resolved: dict[str, Graph] = {}
        for cmd_name, graph in self.graphs.items():
            resolved[cmd_name] = self.expand_refs(graph, cmd_name)
        return resolved

    def expand_refs(self, graph: Graph, current_cmd: str) -> Graph:
        """展开图中的字符串引用。

        若图无 ``_pending_refs``，原样返回。

        Note
        -----
        引用按顺序展开，后续引用的任务依赖于前面引用的任务完成。
        例如 ``["c", "tc", bump]`` 展开为：
        - c 的所有任务（无依赖）
        - tc 的所有任务（依赖于 c 的最后一个任务）
        - bump 任务（依赖于 tc 的最后一个任务）
        """
        pending_refs = graph._pending_refs
        if not pending_refs:
            return graph

        all_specs: list[TaskSpec[Any]] = []
        previous_ref_last_task: str | None = None

        # 先解析每个引用，并建立依赖链。
        for ref in pending_refs:
            expanded_specs = self.parse_ref(ref, current_cmd)

            # 若有前一个引用，让当前引用的任务依赖其最后一个任务。
            if previous_ref_last_task and expanded_specs:
                for i, task in enumerate(expanded_specs):
                    # 只为没有依赖的任务（或第一个任务）添加依赖。
                    if i == 0 or not task.depends_on:
                        expanded_specs[i] = replace(task, depends_on=tuple({*task.depends_on, previous_ref_last_task}))

            if expanded_specs:
                previous_ref_last_task = expanded_specs[-1].name

            all_specs.extend(expanded_specs)

        # 然后添加原始 TaskSpec，按出现顺序串行依赖。
        original_specs = list(graph.all_specs().values())
        if original_specs:
            if previous_ref_last_task:
                first = original_specs[0]
                all_specs.append(replace(first, depends_on=tuple({*first.depends_on, previous_ref_last_task})))
            else:
                all_specs.append(original_specs[0])

            for i in range(1, len(original_specs)):
                current_task = original_specs[i]
                previous_task_name = original_specs[i - 1].name
                all_specs.append(
                    replace(
                        current_task,
                        depends_on=tuple({*current_task.depends_on, previous_task_name}),
                    )
                )

        return Graph.from_specs(all_specs)

    def parse_ref(self, ref: str, current_cmd: str) -> list[TaskSpec[Any]]:
        """解析单个字符串引用，返回对应的 TaskSpec 列表。

        Raises
        ------
        ValueError
            引用无效、目标命令/任务不存在，或检测到循环引用。
        """
        # 避免循环引用。
        if ref == current_cmd:
            raise ValueError(f"循环引用: 命令 '{current_cmd}' 引用了自己")

        if "." in ref:
            # 特定任务引用: "command_name.task_name"
            cmd_name, task_name = ref.split(".", 1)
            if cmd_name not in self.graphs:
                raise ValueError(f"引用的命令 '{cmd_name}' 不存在")

            ref_graph = self.graphs[cmd_name]
            if task_name not in ref_graph.all_specs():
                raise ValueError(f"任务 '{task_name}' 不存在于命令 '{cmd_name}' 中")

            return [ref_graph.all_specs()[task_name]]
        else:
            # 整个命令图引用: "command_name"
            cmd_name = ref
            if cmd_name not in self.graphs:
                raise ValueError(f"引用的命令 '{cmd_name}' 不存在")

            ref_graph = self.graphs[cmd_name]
            # 递归展开（若引用的图自身也含引用）。
            ref_graph = self.expand_refs(ref_graph, cmd_name)
            return list(ref_graph.all_specs().values())
