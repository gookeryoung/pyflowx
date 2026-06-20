"""Core task data structures for PyFlowX.

Everything here is a plain, immutable data structure — no decorators, no
side effects. A :class:`TaskSpec` fully describes a task node; the
:class:`Graph` (see :mod:`pyflowx.graph`) consumes a list of specs and
builds the DAG.

Design notes
------------
* ``TaskSpec`` is a ``Generic[T]`` so that ``TaskSpec[int]`` carries the
  return type of ``fn`` all the way to :class:`RunReport`, giving callers
  typed access to ``report["name"]``.
* ``Context`` is the only intentionally-dynamic type: results from
  upstream tasks are heterogeneous, so the cross-task mapping is
  ``Mapping[str, Any]``. Within a single task the types remain fully
  static because the function signature is checked by mypy.
* ``TaskStatus`` is a closed enum; executors never invent ad-hoc strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Generic,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar("T")

# A task callable may be synchronous or asynchronous. We keep the union
# explicit so mypy understands both shapes.
TaskFn = Union[
    Callable[..., T],
    Callable[..., Coroutine[Any, Any, T]],
]

# The cross-task result mapping. Deliberately ``Any`` for values because
# different tasks return different types; per-task typing is preserved by
# the function signature itself.
Context = Mapping[str, Any]


class TaskStatus(Enum):
    """Lifecycle states of a task during a single run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # used by resumable runs and subgraph filtering


@dataclass(frozen=True)
class TaskSpec(Generic[T]):
    """Immutable description of a single DAG node.

    Parameters
    ----------
    name:
        Unique identifier of the task within a graph. Other tasks reference
        this name in ``depends_on``.
    fn:
        The callable to execute. May be sync or async. Its parameter names
        drive automatic context injection (see :mod:`pyflowx.context`).
    depends_on:
        Names of tasks whose results must be available before this task
        runs. Order is irrelevant; the framework topologically sorts.
    args:
        Static positional arguments appended *after* injected parameters.
        Useful for parameterised tasks (e.g. ``fetch_user(uid)``).
    kwargs:
        Static keyword arguments. Conflict with injected names raises
        :class:`~pyflowx.errors.InjectionError`.
    retries:
        Number of retry attempts on failure. ``0`` means a single attempt.
    timeout:
        Maximum execution time in seconds. ``None`` disables the timeout.
        For async tasks this uses :func:`asyncio.wait_for`; for sync tasks
        in the threaded/async executors it cancels the worker future.
    tags:
        Free-form labels used by :meth:`Graph.subgraph` for selective
        execution and debugging.
    """

    name: str
    fn: TaskFn[T]
    depends_on: Tuple[str, ...] = ()
    args: Tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    retries: int = 0
    timeout: Optional[float] = None
    tags: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TaskSpec.name must be a non-empty string.")
        if self.retries < 0:
            raise ValueError(f"TaskSpec '{self.name}': retries must be >= 0.")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError(f"TaskSpec '{self.name}': timeout must be > 0.")
        if self.name in self.depends_on:
            raise ValueError(f"TaskSpec '{self.name}' cannot depend on itself.")


@dataclass
class TaskResult(Generic[T]):
    """Mutable per-task record produced during a run.

    A fresh :class:`TaskResult` is created for every run; the spec itself
    stays immutable. This keeps the same graph safely re-runnable.
    """

    spec: TaskSpec[T]
    status: TaskStatus = TaskStatus.PENDING
    value: Optional[T] = None
    error: Optional[BaseException] = None
    attempts: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def duration(self) -> Optional[float]:
        """Elapsed seconds between start and finish, or ``None``."""
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


@dataclass(frozen=True)
class TaskEvent:
    """Immutable event emitted during execution for observers.

    Passed to the ``on_event`` callback of :func:`pyflowx.run` so callers
    can build progress bars, metrics, or structured logs without coupling
    to executor internals.
    """

    task: str
    status: TaskStatus
    attempts: int = 0
    error: Optional[str] = None
    duration: Optional[float] = None
