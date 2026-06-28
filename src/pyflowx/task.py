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

import logging
import os
import shutil
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import (
    Any,
    Callable,
    ContextManager,
    Coroutine,
    Generator,
    Generic,
    List,
    Mapping,
    Union,
    cast,
)

if sys.version_info >= (3, 13):
    from typing import TypeVar
else:
    from typing_extensions import TypeVar  # pragma: no cover

T = TypeVar("T", default=Any)

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

# 执行策略：sequential/thread/async 为层屏障模型，dependency 为依赖驱动模型。
Strategy = Union[str, "StrategyKind"]
StrategyKind = Any  # 占位，避免循环；executors 模块用 Literal 约束

logger = logging.getLogger(__name__)

# 条件判断函数类型：接收依赖上下文（可能为空映射），返回是否应执行。
Condition = Callable[[Context], bool]

# 缓存键计算函数：基于依赖上下文计算稳定字符串键。
CacheKeyFn = Callable[[Context], str]


def _format_skip_reason(failed_conditions: list[str]) -> str:
    """格式化跳过原因：≤2 个全展示，>2 个仅展示前 2 个并附总数。"""
    if len(failed_conditions) <= 2:
        return f"条件不满足: {', '.join(failed_conditions)}"
    return f"条件不满足: {', '.join(failed_conditions[:2])} 等{len(failed_conditions)}个条件"


# ---------------------------------------------------------------------- #
# 重试策略
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class RetryPolicy:
    """任务失败重试策略。

    参数
    ----
    max_attempts:
        最大尝试次数（含首次）。``1`` 表示仅尝试一次，不重试。
    delay:
        两次尝试之间的初始等待秒数。
    backoff:
        退避倍率。第 n 次重试等待 ``delay * backoff ** (n-1)``。
    jitter:
        抖动上限秒数。每次等待加上 ``[0, jitter)`` 的随机量，避免惊群。
    retry_on:
        仅对这些异常类型重试。默认 ``(Exception,)`` 重试所有异常。
        传入空元组等价于不重试。

    Note
    -----
    替代旧版 ``retries: int``。``retries=2`` 等价于
    ``RetryPolicy(max_attempts=3)``。
    """

    max_attempts: int = 1
    delay: float = 0.0
    backoff: float = 1.0
    jitter: float = 0.0
    retry_on: tuple[type[BaseException], ...] = (Exception,)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(f"RetryPolicy.max_attempts must be >= 1, got {self.max_attempts}.")
        if self.delay < 0:
            raise ValueError(f"RetryPolicy.delay must be >= 0, got {self.delay}.")
        if self.backoff < 0:
            raise ValueError(f"RetryPolicy.backoff must be >= 0, got {self.backoff}.")
        if self.jitter < 0:
            raise ValueError(f"RetryPolicy.jitter must be >= 0, got {self.jitter}.")

    @property
    def retries(self) -> int:
        """重试次数（不含首次），等价于 ``max_attempts - 1``。"""
        return self.max_attempts - 1

    def should_retry(self, exc: BaseException) -> bool:
        """异常是否属于可重试类型。"""
        return isinstance(exc, self.retry_on)

    def wait_seconds(self, attempt: int) -> float:
        """第 ``attempt`` 次失败后应等待的秒数（attempt 从 1 开始）。"""
        if attempt < 1:
            return 0.0
        import random

        base = self.delay * (self.backoff ** max(0, attempt - 1))
        jitter = random.uniform(0, self.jitter) if self.jitter > 0 else 0.0
        return base + jitter


# ---------------------------------------------------------------------- #
# 任务钩子
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class TaskHooks:
    """任务生命周期钩子。

    所有钩子均为可选。``pre_run`` 在任务实际执行前调用；``post_run``
    在成功后调用并接收返回值；``on_failure`` 在最终失败后调用并接收异常。
    钩子异常不会影响任务状态，仅记录日志。
    """

    pre_run: Callable[[TaskSpec[Any]], None] | None = None
    post_run: Callable[[TaskSpec[Any], Any], None] | None = None
    on_failure: Callable[[TaskSpec[Any], BaseException], None] | None = None


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
    depends_on:
        硬依赖任务名。必须全部成功完成才会运行本任务。
        上游被 SKIPPED 时，本任务也会被 SKIPPED（除非
        ``allow_upstream_skip=True``）。
    soft_depends_on:
        软依赖任务名。会等待其完成，但其结果不影响本任务是否执行：
        - 上游成功：注入其返回值
        - 上游 SKIPPED 或失败：注入 :attr:`defaults` 中提供的默认值
        适用于"可选输入"场景。
    defaults:
        软依赖的默认值映射 ``{dep_name: default_value}``。
        软依赖未提供结果时使用。未在 defaults 中出现的软依赖默认为 ``None``。
    args:
        静态位置参数，追加在注入参数*之后*。
    kwargs:
        静态关键字参数。若与注入名冲突则抛出
        :class:`~pyflowx.errors.InjectionError`。
    retry:
        :class:`RetryPolicy` 重试策略。默认仅尝试一次。
    timeout:
        最大执行时长（秒）。``None`` 表示不限制。异步任务使用
        :func:`asyncio.wait_for`；同步任务通过线程 future 取消。
    tags:
        自由标签，供 :meth:`Graph.subgraph` 做选择性执行与调试，
        也可用于并发限制分组。
    conditions:
        条件判断函数列表，接收依赖上下文，全部返回 ``True`` 时才执行任务。
        任一返回 ``False`` 则任务被标记为 SKIPPED。
    cwd:
        工作目录。对 ``cmd`` 任务作为子进程工作目录；对 ``fn`` 任务
        通过临时切换当前目录生效。
    env:
        环境变量覆盖映射。对 ``cmd`` 任务合并到子进程环境；对 ``fn``
        任务在执行期间临时设置。
    verbose:
        是否打印详细输出。``True`` 时打印执行的命令、返回码与输出
        （仅 ``cmd``），以及任务生命周期。
    skip_if_missing:
        仅对 ``cmd`` 为 ``list[str]`` 有效。``True`` 时通过
        :func:`shutil.which` 检查命令是否存在，不存在则跳过。
    allow_upstream_skip:
        若为 ``True``，硬依赖被 SKIPPED 时本任务仍执行（软依赖不影响）。
        适用于清理类任务。
    strategy:
        单任务执行策略覆盖。``None`` 表示继承图级策略。
        ``"sequential"`` 同步直接调用；``"thread"``/``"async"`` 将同步
        任务卸载到线程池，异步任务跑在事件循环上。
    priority:
        同层任务调度优先级。数值越大越先启动。仅影响同层内启动顺序，
        不打破层屏障。默认 ``0``。
    concurrency_key:
        并发限制分组键。具有相同键的任务共享一个信号量，限制同时
        运行的实例数。具体限额由 :func:`run` 的 ``concurrency_limits``
        参数提供 ``{key: limit}`` 映射。``None`` 表示不限制。
    continue_on_error:
        若为 ``True``，任务最终失败时不中止整图，仅标记本任务 FAILED，
        其硬依赖下游被 SKIPPED，其余任务继续。默认 ``False``。
    cache_key:
        缓存键计算函数。若提供，则用其基于依赖上下文计算的字符串键
        存取状态后端，使不同输入产生独立缓存条目。``None`` 表示用任务名。
    hooks:
        :class:`TaskHooks` 生命周期钩子。
    executor:
        同步任务的执行器：``"thread"``（默认，线程池）/ ``"process"``
        （进程池，绕过 GIL，适合 CPU 密集型；``fn`` 须可 pickle）/
        ``"inline"``（直接在事件循环线程调用，最快但会阻塞循环）。
    """

    name: str
    fn: TaskFn[T] | None = None
    cmd: TaskCmd | None = None
    depends_on: tuple[str, ...] = ()
    soft_depends_on: tuple[str, ...] = ()
    defaults: Mapping[str, Any] = field(default_factory=dict)
    args: tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: float | None = None
    tags: tuple[str, ...] = ()
    conditions: tuple[Condition, ...] = ()
    cwd: Path | None = None
    env: Mapping[str, str] | None = None
    verbose: bool = False
    skip_if_missing: bool = False
    allow_upstream_skip: bool = False
    strategy: str | None = None
    priority: int = 0
    concurrency_key: str | None = None
    continue_on_error: bool = False
    cache_key: CacheKeyFn | None = None
    hooks: TaskHooks = field(default_factory=TaskHooks)
    executor: str = "thread"  # "thread" | "process" | "inline"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TaskSpec.name must be a non-empty string.")
        if self.retry.max_attempts < 1:
            raise ValueError(f"TaskSpec '{self.name}': retry.max_attempts must be >= 1.")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError(f"TaskSpec '{self.name}': timeout must be > 0.")
        if self.name in self.depends_on or self.name in self.soft_depends_on:
            raise ValueError(f"TaskSpec '{self.name}' cannot depend on itself.")
        overlap = set(self.depends_on) & set(self.soft_depends_on)
        if overlap:
            raise ValueError(f"TaskSpec '{self.name}': depends_on 与 soft_depends_on 不能重叠: {sorted(overlap)}")
        if self.fn is None and self.cmd is None:
            raise ValueError(f"TaskSpec '{self.name}': 必须提供 fn 或 cmd 参数。")

    @cached_property
    def effective_fn(self) -> TaskFn[T]:
        """获取有效的执行函数。

        若提供 ``cmd``，返回包装后的命令执行函数；否则返回 ``fn``。
        包装函数在每次调用时从 ``self`` 读取 ``verbose``/``cwd``/``env``/
        ``timeout``，避免闭包捕获运行期参数，使翻转字段无需重建 spec。

        结果按实例缓存（:func:`functools.cached_property`）：frozen dataclass
        字段不可变，``_wrap_cmd`` 生成的闭包稳定，无需每次访问重建。
        """
        if self.cmd is not None:
            return self._wrap_cmd()
        if self.fn is not None:
            return self.fn
        raise ValueError(f"TaskSpec '{self.name}': 没有可执行的函数或命令。")  # pragma: no cover

    def _wrap_cmd(self) -> TaskFn[Any]:
        """将 cmd 包装为可执行函数。

        实际执行逻辑位于 :mod:`pyflowx.command`，避免 :class:`TaskSpec`
        作为纯数据结构混入命令执行逻辑。
        """
        from .command import run_command

        spec = self

        def _run() -> T:
            return cast(T, run_command(spec))

        _run.__name__ = spec.name
        return _run  # type: ignore[return-value]

    def should_execute(self, context: Context) -> tuple[bool, str | None]:
        """检查任务是否应执行。

        Returns
        -------
        (should_run, skip_reason)
            ``should_run`` 为 False 时 ``skip_reason`` 描述跳过原因。
            失败条件超过 2 个时仅展示前 2 个并附总数。
        """
        # 逐个求值条件，记录失败项。
        failed_conditions: list[str] = []
        for condition in self.conditions:
            try:
                ok = condition(context)
            except Exception:
                ok = False
                failed_conditions.append("匿名条件(执行错误)")
                continue
            if not ok:
                reason = getattr(condition, "_reason", None)
                if reason is not None:
                    failed_conditions.append(
                        ", ".join(str(r) for r in reason) if isinstance(reason, list) else str(reason),
                    )
                else:
                    failed_conditions.append(getattr(condition, "__name__", None) or "匿名条件")

        if failed_conditions:
            return False, _format_skip_reason(failed_conditions)

        if self.skip_if_missing and not self._is_cmd_available():
            cmd_name = self.cmd[0] if isinstance(self.cmd, list) and self.cmd else "unknown"
            return False, f"命令不存在: {cmd_name}"

        return True, None

    def _is_cmd_available(self) -> bool:
        """检查 ``cmd`` 是否可用（仅 list[str]）。"""
        cmd = self.cmd
        if isinstance(cmd, list) and cmd:
            return shutil.which(cmd[0]) is not None
        return True

    def env_context(self) -> ContextManager[None]:
        """返回临时应用 ``env`` 与 ``cwd`` 的上下文管理器。

        对 ``fn`` 任务生效。``cmd`` 任务在 :func:`_run_command` 中直接
        传给子进程。
        """
        return _env_and_cwd(self.env, self.cwd)

    def storage_key(self, context: Context) -> str:
        """计算状态后端存储键。"""
        if self.cache_key is None:
            return self.name
        try:
            return f"{self.name}:{self.cache_key(context)}"
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            # cache_key 抛出预期内的数据/类型异常时回退到 name，但仍记录警告
            # 以便用户发现 cache_key 实现中的 bug。
            logger.warning(
                "task %r: cache_key 回退到 name（%s: %s）",
                self.name,
                type(exc).__name__,
                exc,
            )
            return self.name


# 全局锁：序列化对进程级状态（os.environ / os.chdir）的临时修改。
# ``fn`` 任务在 thread/async 策略下并发执行时，若各自配置了不同的
# ``cwd``/``env``，会相互覆盖（os.chdir 与 os.environ 均为进程全局）。
# 该锁仅包裹"切换→执行→恢复"区间，保证正确性；不使用 cwd/env 的任务不受影响。
_env_cwd_lock = threading.RLock()


@contextmanager
def _env_and_cwd(
    env: Mapping[str, str] | None,
    cwd: Path | None,
) -> Generator[None, None, None]:
    """临时设置环境变量与工作目录。

    ``os.environ`` 与 ``os.chdir`` 是进程级全局状态，在 thread/async 策略下
    并发执行多个带 ``env``/``cwd`` 的 ``fn`` 任务时会相互覆盖。本函数通过
    模块级 :data:`_env_cwd_lock` 串行化"切换→执行→恢复"区间，确保正确性。
    无 ``env`` 且无 ``cwd`` 时直接 yield，不获取锁。
    """
    if not env and cwd is None:
        yield
        return
    with _env_cwd_lock:
        saved_env: dict[str, str] = {}
        saved_cwd: str | None = None
        if env:
            for k, v in env.items():
                if k in os.environ:
                    saved_env[k] = os.environ[k]
                os.environ[k] = v
        if cwd is not None:
            saved_cwd = str(Path.cwd())
            os.chdir(cwd)
        try:
            yield
        finally:
            if saved_cwd is not None:
                os.chdir(saved_cwd)
            # 恢复环境变量
            if env:
                for k in env:
                    if k in saved_env:
                        os.environ[k] = saved_env[k]
                    else:
                        os.environ.pop(k, None)


# ---------------------------------------------------------------------- #
# 任务模板：批量生成相似 TaskSpec 的工厂
# ---------------------------------------------------------------------- #
def _task_noop() -> None:
    """task(cmd=...) 形式下的占位 fn（cmd 任务执行期不调用 fn）。"""
    return None


def task(
    fn: TaskFn[Any] | None = None,
    *,
    cmd: TaskCmd | None = None,
    depends_on: tuple[str, ...] = (),
    soft_depends_on: tuple[str, ...] = (),
    defaults: Mapping[str, Any] | None = None,
    args: tuple[Any, ...] = (),
    kwargs: Mapping[str, Any] | None = None,
    retry: RetryPolicy | None = None,
    timeout: float | None = None,
    tags: tuple[str, ...] = (),
    conditions: tuple[Condition, ...] = (),
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    verbose: bool = False,
    skip_if_missing: bool = False,
    allow_upstream_skip: bool = False,
    strategy: str | None = None,
    priority: int = 0,
    concurrency_key: str | None = None,
    continue_on_error: bool = False,
    cache_key: CacheKeyFn | None = None,
    hooks: TaskHooks | None = None,
    name: str | None = None,
) -> Any:
    """装饰器：将函数转为 :class:`TaskSpec`。

    ``name`` 默认取 ``fn.__name__``。可直接装饰函数，或带参数使用。

    Examples
    --------
    >>> @px.task
    ... def extract(): return [1, 2, 3]
    >>> @px.task(depends_on=("extract",))
    ... def double(extract): return [x * 2 for x in extract]
    >>> graph = px.Graph.from_specs([extract, double])
    """

    def _decorate(func: TaskFn[Any]) -> TaskSpec[Any]:
        spec_name = name or func.__name__
        return TaskSpec(
            name=spec_name,
            fn=func,
            cmd=cmd,
            depends_on=depends_on,
            soft_depends_on=soft_depends_on,
            defaults=dict(defaults) if defaults else {},
            args=args,
            kwargs=dict(kwargs) if kwargs else {},
            retry=retry if retry is not None else RetryPolicy(),
            timeout=timeout,
            tags=tags,
            conditions=conditions,
            cwd=Path(cwd) if isinstance(cwd, str) else cwd,
            env=dict(env) if env else None,
            verbose=verbose,
            skip_if_missing=skip_if_missing,
            allow_upstream_skip=allow_upstream_skip,
            strategy=strategy,
            priority=priority,
            concurrency_key=concurrency_key,
            continue_on_error=continue_on_error,
            cache_key=cache_key,
            hooks=hooks if hooks is not None else TaskHooks(),
        )

    if fn is None and cmd is None:
        # 带参数调用：@task(depends_on=...)，等待被装饰函数
        return _decorate
    if fn is None:
        # task(cmd=..., name=...) 直接构造，无被装饰函数
        if name is None:
            raise ValueError("task(cmd=...) 需要显式提供 name")
        return _decorate(_task_noop)
    return _decorate(fn)


def cmd(
    command: list[str],
    *,
    name: str | None = None,
    depends_on: tuple[str, ...] = (),
    **kwargs: Any,
) -> TaskSpec[Any]:
    """从命令列表快速创建 :class:`TaskSpec`。

    ``name`` 默认为 ``"_".join(command[:2])``（如 ``["uv", "build"]`` → ``"uv_build"``）。
    若命令不足两个元素则用 ``"_".join(command)``。

    其余关键字参数透传给 :class:`TaskSpec`（如 ``depends_on``、``tags`` 等）。

    Examples
    --------
    >>> uv_build = px.cmd(["uv", "build"])
    >>> uv_build.name
    'uv_build'
    >>> lint = px.cmd(["ruff", "check", "--fix"], name="lint")
    >>> lint.name
    'lint'
    """
    spec_name = name or "_".join(command[:2]) if len(command) >= 2 else "_".join(command)
    return TaskSpec(
        name=spec_name,
        cmd=command,
        depends_on=depends_on,
        **kwargs,
    )


def task_template(
    fn: TaskFn[Any] | None = None,
    cmd: TaskCmd | None = None,
    **defaults: Any,
) -> Callable[..., TaskSpec[Any]]:
    """创建任务模板工厂。

    返回的工厂接受 ``name`` 与任意覆盖字段，生成 :class:`TaskSpec`。
    适用于批量创建相似任务（如 fan-out）。

    Examples
    --------
    >>> Fetch = px.task_template(fn=fetch_user, retry=px.RetryPolicy(max_attempts=3))
    >>> specs = [Fetch(f"fetch_{uid}", args=(uid,)) for uid in range(5)]
    """
    base = dict(defaults)
    if fn is not None:
        base["fn"] = fn
    if cmd is not None:
        base["cmd"] = cmd

    def _factory(name: str, **overrides: Any) -> TaskSpec[Any]:
        merged = dict(base)
        merged.update(overrides)
        return TaskSpec(name, **merged)

    _factory.__name__ = "task_template_factory"
    return _factory


@dataclass
class TaskResult(Generic[T]):
    """运行期间产生的可变单任务记录。"""

    spec: TaskSpec[T]
    status: TaskStatus = TaskStatus.PENDING
    value: T | None = None
    error: BaseException | None = None
    attempts: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    reason: str | None = None  # 跳过原因

    @property
    def duration(self) -> float | None:
        """从开始到结束的耗时（秒），未开始/未结束则为 ``None``。"""
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


@dataclass(frozen=True)
class TaskEvent:
    """执行期间向观察者发出的不可变事件。"""

    task: str
    status: TaskStatus
    attempts: int = 0
    error: str | None = None
    duration: float | None = None
    reason: str | None = None
