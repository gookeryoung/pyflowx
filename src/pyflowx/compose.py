"""图组合：将带字符串引用的多个图展开为纯 :class:`~pyflowx.graph.Graph`。

历史背景：原 ``graph.py`` 同时承载 DAG 构建/校验/分层与多图组合逻辑，
职责过载。组合逻辑（:class:`GraphComposer` / :func:`compose`）与单图 DAG
模型正交，此处抽离为独立模块，便于按需导入与独立演进。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .graph import Graph
from .task import TaskSpec

__all__ = ["GraphComposer", "compose"]


class GraphComposer:
    """将带字符串引用的图展开为纯 :class:`TaskSpec` 图。

    引用格式：
    * ``"command_name"`` —— 引用整个命令图。
    * ``"command_name.task_name"`` —— 引用特定任务。

    引用按顺序展开，后续引用的任务依赖前面引用的最后一个任务；
    原始 ``TaskSpec`` 之间也按出现顺序串行依赖。
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
        """展开图中的字符串引用。若无 ``_pending_refs``，原样返回。"""
        pending_refs = graph._pending_refs
        if not pending_refs:
            return graph

        all_specs: list[TaskSpec[Any]] = []
        previous_ref_last_task: str | None = None

        for ref in pending_refs:
            expanded_specs = self.parse_ref(ref, current_cmd)
            if previous_ref_last_task and expanded_specs:
                for i, task in enumerate(expanded_specs):
                    if i == 0 or not task.depends_on:
                        expanded_specs[i] = replace(task, depends_on=tuple({*task.depends_on, previous_ref_last_task}))
            if expanded_specs:
                previous_ref_last_task = expanded_specs[-1].name
            all_specs.extend(expanded_specs)

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
                    replace(current_task, depends_on=tuple({*current_task.depends_on, previous_task_name}))
                )

        return Graph.from_specs(all_specs, defaults=graph.defaults)

    def parse_ref(self, ref: str, current_cmd: str) -> list[TaskSpec[Any]]:
        """解析单个字符串引用，返回对应的 TaskSpec 列表。"""
        if ref == current_cmd:
            raise ValueError(f"循环引用: 命令 '{current_cmd}' 引用了自己")

        if "." in ref:
            cmd_name, task_name = ref.split(".", 1)
            if cmd_name not in self.graphs:
                raise ValueError(f"引用的命令 '{cmd_name}' 不存在")
            ref_graph = self.graphs[cmd_name]
            if task_name not in ref_graph.all_specs():
                raise ValueError(f"任务 '{task_name}' 不存在于命令 '{cmd_name}' 中")
            return [ref_graph.all_specs()[task_name]]
        else:
            cmd_name = ref
            if cmd_name not in self.graphs:
                raise ValueError(f"引用的命令 '{cmd_name}' 不存在")
            ref_graph = self.graphs[cmd_name]
            ref_graph = self.expand_refs(ref_graph, cmd_name)
            return list(ref_graph.all_specs().values())


def compose(
    graphs: dict[str, Graph],
) -> dict[str, Graph]:
    """编程式解析多图的字符串引用，返回展开后的新图映射。

    与 :class:`GraphComposer` 等价，但作为独立函数暴露，供不使用
    :class:`~pyflowx.runner.CliRunner` 的编程式用户调用。

    Examples
    --------
    >>> graphs = {
    ...     "build": px.Graph.from_specs([px.TaskSpec("b", cmd=["echo", "b"])]),
    ...     "all": px.Graph.from_specs(["build", px.TaskSpec("t", cmd=["echo", "t"])]),
    ... }
    >>> resolved = px.compose(graphs)
    >>> "b" in resolved["all"].all_specs()
    True
    """
    return GraphComposer(graphs).resolve_all()
