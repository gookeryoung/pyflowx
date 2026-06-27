"""PyFlowX —— 轻量、类型安全的 DAG 任务调度器。

公共 API
--------
* :class:`TaskSpec` —— 不可变任务描述符（唯一需要配置的东西）。
* :class:`Graph` —— 由一组 spec 构建的 DAG；负责校验、分层、可视化。
* :func:`run` ——以 ``sequential`` / ``thread`` / ``async`` / ``dependency``
  策略执行图。
* :class:`RunReport` —— 类型化、可查询的运行结果。
* :class:`Context` —— 整体上下文注入的标注标记。
* :class:`RetryPolicy` —— 重试策略（max_attempts/delay/backoff/jitter/retry_on）。
* :class:`TaskHooks` —— 任务生命周期钩子（pre_run/post_run/on_failure）。
* :class:`GraphDefaults` —— 图级默认值。
* :func:`compose` —— 编程式组合多图。
* :func:`task_template` —— 批量生成相似 TaskSpec 的工厂。
* 状态后端：:class:`StateBackend`、:class:`MemoryBackend`、:class:`JSONBackend`。

快速上手
--------
    import pyflowx as px

    def extract() -> list[int]: return [1, 2, 3]
    def double(extract: list[int]) -> list[int]: return [x * 2 for x in extract]

    graph = px.Graph.from_specs([
        px.TaskSpec("extract", extract),
        px.TaskSpec("double", double, depends_on=("extract",)),
    ])
    report = px.run(graph, strategy="sequential")
    print(report["double"])  # [2, 4, 6]

命令行任务示例
--------------
    import pyflowx as px
    from pyflowx.conditions import IS_WINDOWS, BuiltinConditions

    graph = px.Graph.from_specs([
        px.TaskSpec("list_files", cmd=["ls", "-la"]),
        px.TaskSpec("check_git", cmd="git status"),
        px.TaskSpec(
            "win_only",
            cmd=["dir"],
            conditions=(IS_WINDOWS,)
        ),
        px.TaskSpec(
            "git_check",
            cmd=["git", "--version"],
            conditions=(BuiltinConditions.HAS_INSTALLED("git"),)
        ),
        px.TaskSpec(
            "optional_build",
            cmd=["maturin", "build"],
            skip_if_missing=True
        ),
    ])
    report = px.run(graph)
"""

from __future__ import annotations

from .conditions import (
    IS_LINUX,
    IS_MACOS,
    IS_POSIX,
    IS_WINDOWS,
    BuiltinConditions,
    Condition,
    Constants,
)
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
from .executors import Strategy, run
from .graph import Graph, GraphComposer, GraphDefaults, compose
from .report import RunReport
from .runner import CliExitCode, CliRunner
from .storage import JSONBackend, MemoryBackend, StateBackend
from .task import (
    CacheKeyFn,
    RetryPolicy,
    TaskCmd,
    TaskEvent,
    TaskHooks,
    TaskResult,
    TaskSpec,
    TaskStatus,
    task_template,
)

__version__ = "0.3.1"

__all__ = [
    "IS_LINUX",
    "IS_MACOS",
    "IS_POSIX",
    "IS_WINDOWS",
    "BuiltinConditions",
    "CacheKeyFn",
    "CliExitCode",
    "CliRunner",
    "Condition",
    "Constants",
    "Context",
    "CycleError",
    "DuplicateTaskError",
    "Graph",
    "GraphComposer",
    "GraphDefaults",
    "InjectionError",
    "JSONBackend",
    "MemoryBackend",
    "MissingDependencyError",
    "PyFlowXError",
    "RetryPolicy",
    "RunReport",
    "StateBackend",
    "StorageError",
    "Strategy",
    "TaskCmd",
    "TaskEvent",
    "TaskFailedError",
    "TaskHooks",
    "TaskResult",
    "TaskSpec",
    "TaskStatus",
    "TaskTimeoutError",
    "build_call_args",
    "compose",
    "describe_injection",
    "run",
    "task_template",
]
