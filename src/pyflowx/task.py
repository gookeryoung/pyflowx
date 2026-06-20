"""PyFlowX 核心任务数据结构。

本模块全部为纯不可变数据结构——无装饰器、无副作用。一个
:class:`TaskSpec` 完整描述一个任务节点；:class:`Graph`
（见 :mod:`pyflowx.graph`）消费一组 spec 并构建 DAG。

设计要点
--------
* ``TaskSpec`` 是 ``Generic[T]``，因此 ``TaskSpec[int]`` 会把 ``fn`` 的
  返回类型一路传递到 :class:`RunReport`，让调用者可以类型安全地访问
  ``report["name"]``。
* ``Context`` 是唯一刻意保留动态类型的类型：上游任务的结果异构，因此
  跨任务映射为 ``Mapping[str, Any]``。单个任务内部类型仍然完全静态，
  因为函数签名由 mypy 检查。
* ``TaskStatus`` 是封闭枚举；执行器绝不发明临时字符串。
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

# 任务可调用对象可以是同步或异步的。显式保留联合类型，让 mypy 理解两种形态。
TaskFn = Union[
    Callable[..., T],
    Callable[..., Coroutine[Any, Any, T]],
]

# 跨任务结果映射。值刻意使用 ``Any``，因为不同任务返回不同类型；
# 单任务类型由函数签名本身保留。
Context = Mapping[str, Any]


class TaskStatus(Enum):
    """任务在单次运行内的生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # 用于断点续跑与子图过滤


@dataclass(frozen=True)
class TaskSpec(Generic[T]):
    """单个 DAG 节点的不可变描述。

    参数
    ----
    name:
        任务在图内的唯一标识。其他任务通过 ``depends_on`` 引用此名称。
    fn:
        待执行的可调用对象，可为同步或异步。其参数名驱动自动上下文
        注入（见 :mod:`pyflowx.context`）。
    depends_on:
        必须先完成才能运行本任务的任务名列表。顺序无关；框架会做
        拓扑排序。
    args:
        静态位置参数，追加在注入参数*之后*。适用于参数化任务
        （如 ``fetch_user(uid)``）。
    kwargs:
        静态关键字参数。若与注入名冲突则抛出
        :class:`~pyflowx.errors.InjectionError`。
    retries:
        失败后的重试次数。``0`` 表示仅尝试一次。
    timeout:
        最大执行时长（秒）。``None`` 表示不限制。异步任务使用
        :func:`asyncio.wait_for`；线程/异步执行器中的同步任务会
        取消 worker future。
    tags:
        自由标签，供 :meth:`Graph.subgraph` 做选择性执行与调试。
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
    """运行期间产生的可变单任务记录。

    每次运行都会创建全新的 :class:`TaskResult`；spec 本身保持不可变。
    这让同一个图可以安全地重复运行。
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
        """从开始到结束的耗时（秒），未开始/未结束则为 ``None``。"""
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


@dataclass(frozen=True)
class TaskEvent:
    """执行期间向观察者发出的不可变事件。

    传递给 :func:`pyflowx.run` 的 ``on_event`` 回调，让调用者无需耦合
    执行器内部即可构建进度条、指标或结构化日志。
    """

    task: str
    status: TaskStatus
    attempts: int = 0
    error: Optional[str] = None
    duration: Optional[float] = None
