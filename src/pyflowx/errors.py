"""PyFlowX 错误层级。

所有错误都是 :class:`PyFlowXError` 的具体子类，调用者可以用单个
``except`` 子句捕获整个错误家族，同时仍可按类型区分以做细粒度处理。
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


class PyFlowXError(Exception):
    """所有 PyFlowX 错误的基类。"""


class DuplicateTaskError(PyFlowXError):
    """任务名被重复注册时抛出。"""

    def __init__(self, name: str) -> None:
        super().__init__(f"Task '{name}' is already registered in the graph.")
        self.name = name


class MissingDependencyError(PyFlowXError):
    """任务依赖了图中不存在的名称时抛出。"""

    def __init__(self, task: str, dependency: str) -> None:
        super().__init__(
            f"Task '{task}' depends on unknown task '{dependency}'. "
            "Add the dependency before (or together with) this task."
        )
        self.task = task
        self.dependency = dependency


class CycleError(PyFlowXError):
    """依赖图存在环时抛出。"""

    def __init__(self, cycle: Iterable[str]) -> None:
        cycle_list = list(cycle)
        chain = " -> ".join(cycle_list + cycle_list[:1])
        super().__init__(f"The dependency graph contains a cycle: {chain}")
        self.cycle = cycle_list


class TaskFailedError(PyFlowXError):
    """任务耗尽所有重试后仍失败时抛出。

    原始异常保留在 :attr:`__cause__` 上，同时通过 :attr:`cause` 暴露，
    便于用户代码访问。
    """

    def __init__(
        self,
        task: str,
        cause: BaseException,
        attempts: int,
        layer: Optional[int] = None,
    ) -> None:
        location = f" (layer {layer})" if layer is not None else ""
        super().__init__(f"Task '{task}' failed after {attempts} attempt(s){location}: {cause}")
        self.task = task
        self.cause = cause
        self.attempts = attempts
        self.layer = layer


class TaskTimeoutError(PyFlowXError):
    """任务超出配置的超时时间时抛出。"""

    def __init__(self, task: str, timeout: float) -> None:
        super().__init__(f"Task '{task}' timed out after {timeout:.3f}s.")
        self.task = task
        self.timeout = timeout


class InjectionError(PyFlowXError):
    """上下文注入无法满足任务签名时抛出。"""

    def __init__(self, task: str, detail: str) -> None:
        super().__init__(f"Cannot inject context for task '{task}': {detail}")
        self.task = task


class StorageError(PyFlowXError):
    """状态后端在持久化失败时抛出。"""

    def __init__(self, detail: str, cause: Optional[BaseException] = None) -> None:
        super().__init__(f"State storage error: {detail}")
        self.cause: Any = cause
