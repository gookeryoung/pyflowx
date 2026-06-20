"""PyFlowX — lightweight, type-safe DAG task scheduler.

Public API
----------
* :class:`TaskSpec` — immutable task descriptor (the only thing you configure).
* :class:`Graph` — DAG built from a list of specs; validates, layers, visualises.
* :func:`run` — execute a graph with ``sequential`` / ``thread`` / ``async``.
* :class:`RunReport` — typed, queryable result of a run.
* :class:`Context` — annotation marker for whole-context injection.
* State backends: :class:`StateBackend`, :class:`MemoryBackend`, :class:`JSONBackend`.

Quick start
-----------
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
    # core types
    "TaskSpec",
    "TaskStatus",
    "TaskResult",
    "TaskEvent",
    "Context",
    "Graph",
    "RunReport",
    # execution
    "run",
    # state backends
    "StateBackend",
    "MemoryBackend",
    "JSONBackend",
    # errors
    "PyFlowXError",
    "DuplicateTaskError",
    "MissingDependencyError",
    "CycleError",
    "TaskFailedError",
    "TaskTimeoutError",
    "InjectionError",
    "StorageError",
    # helpers (advanced)
    "build_call_args",
    "describe_injection",
]
