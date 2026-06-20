"""PyFlowX —— 轻量、类型安全的 DAG 任务调度器。

公共 API
--------
* :class:`TaskSpec` —— 不可变任务描述符（唯一需要配置的东西）。
* :class:`Graph` —— 由一组 spec 构建的 DAG；负责校验、分层、可视化。
* :func:`run` —— 以 ``sequential`` / ``thread`` / ``async`` 策略执行图。
* :class:`RunReport` —— 类型化、可查询的运行结果。
* :class:`Context` —— 整体上下文注入的标注标记。
* 状态后端：:class:`StateBackend`、:class:`MemoryBackend`、:class:`JSONBackend`。

快速上手
--------
    import pyflowx as px

    def extract() -> list[int]: return [1, 2, 3]
    def double(extract: list[int]) -> list[int]: return [x * 2 for x in extract]

    graph = px.Graph.from_specs([
        px.TaskSpec("extract", extract),
        px.TaskSpec("double", double, ("extract",)),
    ])
    report = px.run(graph, strategy="sequential")
    print(report["double"])  # [2, 4, 6]
"""

from __future__ import annotations

from .context import Context, build_call_args, describe_injection
from .errors import (
    CycleError,
    DuplicateTaskError,
    InjectionError,
    MissingDependencyError,
    PyFlowXError,
    StorageError,
    TaskFailedError,
    TaskTimeoutError,
)
from .executors import run
from .graph import Graph
from .report import RunReport
from .storage import JSONBackend, MemoryBackend, StateBackend
from .task import TaskEvent, TaskResult, TaskSpec, TaskStatus

__version__ = "0.1.0"

__all__ = [
    # 核心类型
    "TaskSpec",
    "TaskStatus",
    "TaskResult",
    "TaskEvent",
    "Context",
    "Graph",
    "RunReport",
    # 执行
    "run",
    # 状态后端
    "StateBackend",
    "MemoryBackend",
    "JSONBackend",
    # 错误
    "PyFlowXError",
    "DuplicateTaskError",
    "MissingDependencyError",
    "CycleError",
    "TaskFailedError",
    "TaskTimeoutError",
    "InjectionError",
    "StorageError",
    # 辅助（高级）
    "build_call_args",
    "describe_injection",
]
