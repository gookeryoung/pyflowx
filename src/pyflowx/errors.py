"""PyFlowX error hierarchy.

All errors are concrete subclasses of :class:`PyFlowXError` so callers can
catch the entire family with a single ``except`` clause, while still being
able to discriminate by type for fine-grained handling.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


class PyFlowXError(Exception):
    """Base class for every PyFlowX error."""


class DuplicateTaskError(PyFlowXError):
    """Raised when a task name is registered more than once."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Task '{name}' is already registered in the graph.")
        self.name = name


class MissingDependencyError(PyFlowXError):
    """Raised when a task depends on a name that is not in the graph."""

    def __init__(self, task: str, dependency: str) -> None:
        super().__init__(
            f"Task '{task}' depends on unknown task '{dependency}'. "
            "Add the dependency before (or together with) this task."
        )
        self.task = task
        self.dependency = dependency


class CycleError(PyFlowXError):
    """Raised when the dependency graph contains a cycle."""

    def __init__(self, cycle: Iterable[str]) -> None:
        cycle_list = list(cycle)
        chain = " -> ".join(cycle_list + cycle_list[:1])
        super().__init__(f"The dependency graph contains a cycle: {chain}")
        self.cycle = cycle_list


class TaskFailedError(PyFlowXError):
    """Raised when a task fails after exhausting all retries.

    The original exception is preserved on :attr:`__cause__` and also exposed
    via :attr:`cause` for convenient access in user code.
    """

    def __init__(
        self,
        task: str,
        cause: BaseException,
        attempts: int,
        layer: Optional[int] = None,
    ) -> None:
        location = f" (layer {layer})" if layer is not None else ""
        super().__init__(
            f"Task '{task}' failed after {attempts} attempt(s){location}: {cause}"
        )
        self.task = task
        self.cause = cause
        self.attempts = attempts
        self.layer = layer


class TaskTimeoutError(PyFlowXError):
    """Raised when a task exceeds its configured timeout."""

    def __init__(self, task: str, timeout: float) -> None:
        super().__init__(f"Task '{task}' timed out after {timeout:.3f}s.")
        self.task = task
        self.timeout = timeout


class InjectionError(PyFlowXError):
    """Raised when context injection cannot satisfy a task signature."""

    def __init__(self, task: str, detail: str) -> None:
        super().__init__(f"Cannot inject context for task '{task}': {detail}")
        self.task = task


class StorageError(PyFlowXError):
    """Raised by state backends on persistence failures."""

    def __init__(self, detail: str, cause: Optional[BaseException] = None) -> None:
        super().__init__(f"State storage error: {detail}")
        self.cause: Any = cause
