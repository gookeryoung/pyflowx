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

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Coroutine,
    Generic,
    List,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
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

# 命令类型支持
TaskCmd = Union[
    List[str],  # 命令列表, 如 ["ls", "-la"]
    str,  # shell 命令字符串
    Callable[..., Any],  # Python 函数
]

# 条件判断函数类型
Condition = Callable[[], bool]


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
        若提供 ``cmd`` 参数，则此参数会被忽略。
    cmd:
        命令列表或 shell 字符串，支持三种形态：
        - ``list[str]``: 命令及参数列表，如 ``["ls", "-la"]``
        - ``str``: shell 命令字符串，如 ``"pip freeze > requirements.txt"``
        - ``Callable``: Python 函数，与 ``fn`` 参数等效
        若提供此参数，会自动包装为执行函数，覆盖 ``fn`` 参数。
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
    conditions:
        条件判断函数列表，只有所有条件都返回 ``True`` 时才执行任务。
        若任一条件返回 ``False``，任务会被标记为 SKIPPED。
        用于平台判断、环境变量检查等场景。
    cwd:
        命令执行的工作目录，仅在使用 ``cmd`` 参数时有效。
        ``None`` 表示当前目录。
    verbose:
        是否在命令执行时显示详细输出。``True`` 时会打印执行的命令
        及其标准输出/标准错误。仅在使用 ``cmd`` 参数时有效。
        ``False`` 时静默捕获输出（失败时仍会包含在错误信息中）。
    skip_if_missing:
        仅对 ``cmd`` 为 ``list[str]`` 的任务有效。``True`` 时自动检查
        命令是否存在（通过 :func:`shutil.which`），不存在则跳过任务
        （标记为 SKIPPED）而非失败。适用于构建工具场景，避免因未安装
        某些工具（如 maturin、tox）而导致整个图执行失败。
        对于 ``str`` (shell) 和 ``Callable`` 类型的 ``cmd``，此参数无效。
    """

    name: str
    fn: Optional[TaskFn[T]] = None
    cmd: Optional[TaskCmd] = None
    depends_on: Tuple[str, ...] = ()
    args: Tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    retries: int = 0
    timeout: Optional[float] = None
    tags: Tuple[str, ...] = ()
    conditions: Tuple[Condition, ...] = ()
    cwd: Optional[Path] = None
    verbose: bool = False
    skip_if_missing: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TaskSpec.name must be a non-empty string.")
        if self.retries < 0:
            raise ValueError(f"TaskSpec '{self.name}': retries must be >= 0.")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError(f"TaskSpec '{self.name}': timeout must be > 0.")
        if self.name in self.depends_on:
            raise ValueError(f"TaskSpec '{self.name}' cannot depend on itself.")
        if self.fn is None and self.cmd is None:
            raise ValueError(f"TaskSpec '{self.name}': 必须提供 fn 或 cmd 参数。")

    @property
    def effective_fn(self) -> TaskFn[T]:
        """获取有效的执行函数.

        若提供了 ``cmd`` 参数，则返回包装后的命令执行函数；
        否则返回 ``fn`` 参数。
        """
        if self.cmd is not None:
            return self._wrap_cmd()
        if self.fn is not None:
            return self.fn

        raise ValueError(f"TaskSpec '{self.name}': 没有可执行的函数或命令。")  # pragma: no cover

    def _wrap_cmd(self) -> TaskFn[Any]:
        """将 cmd 包装为可执行函数.

        Returns
        -------
        TaskFn[Any]
            包装后的执行函数.
        """
        cmd = self.cmd
        cwd = self.cwd
        timeout = self.timeout
        verbose = self.verbose

        if isinstance(cmd, list):
            cmd_list = cast(List[str], cmd)

            def _run_list() -> T:
                import subprocess

                cmd_str = " ".join(str(arg) for arg in cmd_list)
                if verbose:
                    print(f"[verbose] 执行命令: {cmd_str}", flush=True)
                    if cwd is not None:
                        print(f"[verbose] 工作目录: {cwd}", flush=True)
                try:
                    result = subprocess.run(
                        cmd_list,
                        cwd=cwd,
                        timeout=timeout,
                        capture_output=not verbose,
                        text=True,
                        check=False,
                    )
                except FileNotFoundError:
                    raise RuntimeError(f"命令未找到: {cmd_str}") from None
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f"命令执行超时: {cmd_str} ({timeout}s)") from None
                except OSError as e:
                    raise RuntimeError(f"命令执行异常: {cmd_str}: {e}") from e

                if verbose:
                    print(f"[verbose] 返回码: {result.returncode}", flush=True)

                if result.returncode == 0:
                    return cast(T, None)  # type: ignore[return-value]

                err_msg = f"命令执行失败: `{cmd_str}`, 返回码: {result.returncode}"
                if not verbose and result.stderr.strip():
                    err_msg += f"\n{result.stderr.strip()}"
                raise RuntimeError(err_msg)

            _run_list.__name__ = self.name
            return _run_list  # type: ignore[return-value]

        if isinstance(cmd, str):

            def _run_shell() -> T:
                import subprocess

                if verbose:
                    print(f"[verbose] 执行 Shell: {cmd}", flush=True)
                    if cwd is not None:
                        print(f"[verbose] 工作目录: {cwd}", flush=True)
                try:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        cwd=cwd,
                        timeout=timeout,
                        capture_output=not verbose,
                        text=True,
                        check=False,
                    )
                except FileNotFoundError:
                    raise RuntimeError(f"Shell 命令未找到: {cmd}") from None
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f"Shell 命令执行超时: {cmd} ({timeout}s)") from None
                except OSError as e:
                    raise RuntimeError(f"Shell 命令执行异常: {cmd}: {e}") from e

                if verbose:
                    print(f"[verbose] 返回码: {result.returncode}", flush=True)

                if result.returncode == 0:
                    return cast(T, None)  # type: ignore[return-value]

                err_msg = f"Shell 命令执行失败: `{cmd}`, 返回码: {result.returncode}"
                if not verbose and result.stderr.strip():
                    err_msg += f"\n{result.stderr.strip()}"
                raise RuntimeError(err_msg)

            _run_shell.__name__ = self.name
            return _run_shell  # type: ignore[return-value]

        if callable(cmd):
            return cmd  # type: ignore[return-value]

        raise TypeError(f"TaskSpec '{self.name}': 不支持的 cmd 类型 {type(cmd).__name__}")  # pragma: no cover

    def should_execute(self) -> bool:
        """检查任务是否应该执行.

        Returns
        -------
        bool
            若所有条件都返回 ``True``，且 ``skip_if_missing`` 检查通过，
            则返回 ``True``；否则返回 ``False``。
        """
        if not all(condition() for condition in self.conditions):
            return False

        return not (self.skip_if_missing and not self._is_cmd_available())

    def _is_cmd_available(self) -> bool:
        """检查 ``cmd`` 是否可用.

        仅对 ``list[str]`` 类型的 ``cmd`` 进行检查（通过 :func:`shutil.which`）。
        对于 ``str`` (shell) 和 ``Callable`` 类型，始终返回 ``True``。

        Returns
        -------
        bool
            命令可用返回 ``True``，否则返回 ``False``。
        """
        import shutil

        cmd = self.cmd
        if isinstance(cmd, list) and cmd:
            first_arg = cast(str, cmd[0])
            return shutil.which(first_arg) is not None
        return True


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
