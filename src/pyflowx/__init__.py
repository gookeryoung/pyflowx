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

命令行任务示例
--------------
    import pyflowx as px
    from pyflowx.conditions import IS_WINDOWS, BuiltinConditions

    graph = px.Graph.from_specs([
        # 使用命令列表
        px.TaskSpec("list_files", cmd=["ls", "-la"]),
        # 使用 shell 命令
        px.TaskSpec("check_git", cmd="git status"),
        # 条件执行：仅在 Windows 上运行
        px.TaskSpec(
            "win_only",
            cmd=["dir"],
            conditions=(IS_WINDOWS,)
        ),
        # 条件执行：仅在 git 已安装时运行
        px.TaskSpec(
            "git_check",
            cmd=["git", "--version"],
            conditions=(BuiltinConditions.HAS_INSTALLED("git"),)
        ),
        # 命令不存在时自动跳过（而非失败）
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
from .graph import Graph
from .report import RunReport
from .runner import CliExitCode, CliRunner
from .storage import JSONBackend, MemoryBackend, StateBackend
from .task import TaskCmd, TaskEvent, TaskResult, TaskSpec, TaskStatus

__version__ = "0.1.7"

__all__ = [
    "IS_LINUX",
    "IS_MACOS",
    "IS_POSIX",
    "IS_WINDOWS",
    "BuiltinConditions",
    "CliExitCode",
    # CLI 运行器
    "CliRunner",
    # 条件判断
    "Condition",
    "Constants",
    "Context",
    "CycleError",
    "DuplicateTaskError",
    "Graph",
    "InjectionError",
    "JSONBackend",
    "MemoryBackend",
    "MissingDependencyError",
    # 错误
    "PyFlowXError",
    "RunReport",
    # 状态后端
    "StateBackend",
    "StorageError",
    "Strategy",
    "TaskCmd",
    "TaskEvent",
    "TaskFailedError",
    "TaskResult",
    # 核心类型
    "TaskSpec",
    "TaskStatus",
    "TaskTimeoutError",
    # 辅助（高级）
    "build_call_args",
    "describe_injection",
    # 执行
    "run",
]
