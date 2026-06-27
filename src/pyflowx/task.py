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

import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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

# 条件判断函数类型：接收依赖上下文（可能为空映射），返回是否应执行。
Condition = Callable[[Context], bool]

# 缓存键计算函数：基于依赖上下文计算稳定字符串键。
CacheKeyFn = Callable[[Context], str]


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

    @property
    def effective_fn(self) -> TaskFn[T]:
        """获取有效的执行函数。

        若提供 ``cmd``，返回包装后的命令执行函数；否则返回 ``fn``。
        包装函数在每次调用时从 ``self`` 读取 ``verbose``/``cwd``/``env``/
        ``timeout``，避免闭包捕获运行期参数，使翻转字段无需重建 spec。
        """
        if self.cmd is not None:
            return self._wrap_cmd()
        if self.fn is not None:
            return self.fn
        raise ValueError(f"TaskSpec '{self.name}': 没有可执行的函数或命令。")  # pragma: no cover

    def _wrap_cmd(self) -> TaskFn[Any]:
        """将 cmd 包装为可执行函数。"""
        spec = self

        def _run() -> T:
            return cast(T, _run_command(spec))

        _run.__name__ = spec.name
        return _run  # type: ignore[return-value]

    def should_execute(self, context: Context) -> tuple[bool, str | None]:
        """检查任务是否应执行。

        Returns
        -------
        (should_run, skip_reason)
            ``should_run`` 为 False 时 ``skip_reason`` 描述跳过原因。
        """
        # 逐个求值条件，记录失败项。
        failed_conditions: list[str] = []
        for condition in self.conditions:
            try:
                ok = condition(context)
            except Exception:
                ok = False
                name = getattr(condition, "__name__", None) or "匿名条件(执行错误)"
                failed_conditions.append(name)
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
            return False, f"条件不满足: {', '.join(failed_conditions)}"

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
        if self.cache_key is not None:
            try:
                return f"{self.name}:{self.cache_key(context)}"
            except Exception:
                return self.name
        return self.name


@contextmanager
def _env_and_cwd(
    env: Mapping[str, str] | None,
    cwd: Path | None,
) -> Generator[None, None, None]:
    """临时设置环境变量与工作目录。"""
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


def _run_command(spec: TaskSpec[Any]) -> Any:  # noqa: PLR0912
    """执行 ``spec.cmd`` 指定的命令（list / shell 字符串 / 可调用对象）。"""
    cmd = spec.cmd
    verbose = spec.verbose
    cwd = spec.cwd
    timeout = spec.timeout
    env_override = spec.env

    # 可调用对象：直接调用，返回其结果。
    if callable(cmd) and not isinstance(cmd, (list, str)):
        name = getattr(cmd, "__name__", "callable")
        if verbose:
            print(f"[verbose] 执行可调用命令: {name}", flush=True)
            if cwd is not None:
                print(f"[verbose] 工作目录: {cwd}", flush=True)
        try:
            return cmd()
        except Exception as e:
            raise RuntimeError(f"可调用命令执行异常: {name}: {e}") from e

    is_list = isinstance(cmd, list)
    if is_list:
        cmd_str = " ".join(arg for arg in cmd)  # type: ignore[union-attr]
        verb = "执行命令"
        label = "命令"
    else:
        cmd_str = cast(str, cmd)
        verb = "执行 Shell"
        label = "Shell 命令"

    if verbose:
        print(f"[verbose] {verb}: {cmd_str}", flush=True)
        if cwd is not None:
            print(f"[verbose] 工作目录: {cwd}", flush=True)

    # 合并环境变量
    run_env: dict[str, str] | None = None
    if env_override:
        run_env = dict(os.environ)
        run_env.update(env_override)

    try:
        result = subprocess.run(
            cast(Union[str, List[str]], cmd),
            shell=not is_list,
            cwd=cwd,
            env=run_env,
            timeout=timeout,
            capture_output=not verbose,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError(f"{label}未找到: {cmd_str}") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{label}执行超时: {cmd_str} ({timeout}s)") from None
    except OSError as e:
        raise RuntimeError(f"{label}执行异常: {cmd_str}: {e}") from e

    if verbose:
        print(f"[verbose] 返回码: {result.returncode}", flush=True)

    if result.returncode == 0:
        return None

    err_msg = f"{label}执行失败: `{cmd_str}`, 返回码: {result.returncode}"
    if not verbose and result.stderr.strip():
        err_msg += f"\n{result.stderr.strip()}"
    raise RuntimeError(err_msg)


# ---------------------------------------------------------------------- #
# 任务模板：批量生成相似 TaskSpec 的工厂
# ---------------------------------------------------------------------- #
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
