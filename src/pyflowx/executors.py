"""执行器与公共 :func:`run` 入口。

四种执行策略：

* ``sequential`` —— 确定性、一次一个任务。最适合调试。
* ``thread``     —— 通过线程池实现层内并发。最适合 I/O 密集型同步任务。
* ``async``      —— 通过 ``asyncio.gather`` 实现层内并发。同步任务被
                    卸载到线程池；异步任务运行在事件循环上。最适合
                    I/O 密集型异步任务。
* ``dependency`` —— 依赖驱动调度：任务在其所有硬依赖完成后立即启动，
                    无需等待同层其他任务。最大化并行度。

架构
----
本模块通过 **Mixin** 组合消除同步/异步与各层执行器之间的重复代码：

* :class:`_TaskSkipMixin`  —— 上游跳过 / 条件跳过的预检逻辑。
* :class:`_TaskRetryMixin` —— 重试决策、成功/失败后处理、finalize。
* :class:`_LayerMixin`     —— 缓存过滤、优先级排序、信号量构建、结果存储。
* :class:`SyncTaskRunner` / :class:`AsyncTaskRunner` —— 任务级执行器，组合上述 Mixin。
* :class:`SequentialLayerRunner` / :class:`ThreadedLayerRunner` /
  :class:`AsyncLayerRunner` / :class:`DependencyRunner` —— 层级执行器，组合 :class:`_LayerMixin`。

所有策略共享统一异步内核，支持：
* :class:`RetryPolicy`（max_attempts/delay/backoff/jitter/retry_on）
* 软依赖注入与默认值
* :class:`TaskHooks`（pre_run/post_run/on_failure）
* 按任务策略覆盖
* 优先级排序（同层内）
* 并发限制（concurrency_key + concurrency_limits）
* ``continue_on_error``
* ``cache_key`` 存储键
* 条件判断（上下文感知）
* 状态后端（续跑）
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import logging
import threading
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Literal, Mapping, cast

from .context import build_call_args, describe_injection
from .errors import TaskFailedError, TaskTimeoutError
from .graph import Graph
from .report import RunReport
from .storage import StateBackend, resolve_backend
from .task import TaskEvent, TaskHooks, TaskResult, TaskSpec, TaskStatus

logger = logging.getLogger("pyflowx")

# 观察者回调类型。
EventCallback = Callable[[TaskEvent], None]
Strategy = Literal["sequential", "thread", "async", "dependency"]


# ---------------------------------------------------------------------- #
# 无状态公共辅助
# ---------------------------------------------------------------------- #
def _is_async_fn(spec: TaskSpec[Any]) -> bool:
    """判断 ``spec.effective_fn`` 是否为协程函数。"""
    return inspect.iscoroutinefunction(spec.effective_fn)


def _emit(on_event: EventCallback | None, result: TaskResult[Any]) -> None:
    """若注册了回调则触发一个观察者事件。"""
    if on_event is None:
        return
    on_event(
        TaskEvent(
            task=result.spec.name,
            status=result.status,
            attempts=result.attempts,
            error=repr(result.error) if result.error else None,
            duration=result.duration,
            reason=result.reason,
        )
    )


def _run_hooks(hooks: TaskHooks, fn_name: str, *args: Any) -> None:
    """安全调用钩子（异常仅记录，不影响任务状态）。"""
    hook: Callable[..., None] | None = getattr(hooks, fn_name, None)
    if hook is None:
        return
    try:
        hook(*args)
    except Exception as exc:
        logger.warning("hook %s raised: %r", fn_name, exc)


def _build_context(
    spec: TaskSpec[Any],
    global_context: Mapping[str, Any],
    report: RunReport | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """构建本任务的上下文：硬依赖 + 软依赖（含默认值回退）。

    硬依赖：若上游 SKIPPED/FAILED 则不注入（本任务通常也会被跳过）。
    软依赖：上游成功则注入其值；否则注入 ``spec.defaults`` 中的默认值（或 ``None``）。
    """
    ctx: dict[str, Any] = {}
    for dep in spec.depends_on:
        if dep in global_context:
            ctx[dep] = global_context[dep]
    for dep in spec.soft_depends_on:
        if dep in global_context:
            ctx[dep] = global_context[dep]
        elif dep in spec.defaults:
            ctx[dep] = spec.defaults[dep]
        else:
            ctx[dep] = None
    return ctx


def _apply_cached(
    name: str,
    spec: TaskSpec[Any],
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: EventCallback | None,
) -> bool:
    """若 ``name`` 命中缓存，写入 context/report 并返回 True。"""
    storage_key = spec.storage_key(context)
    if not backend.has(storage_key):
        return False
    cached = backend.get(storage_key)
    context[name] = cached
    result = TaskResult(spec=spec, status=TaskStatus.SKIPPED, value=cached, reason="缓存命中")
    report.results[name] = result
    _emit(on_event, result)
    logger.info("task %r skipped (cached)", name)
    return True


def _sort_by_priority(layer: list[str], graph: Graph) -> list[str]:
    """按优先级降序排序（稳定排序）。"""
    return sorted(layer, key=lambda n: -graph.resolved_spec(n).priority)


# ---------------------------------------------------------------------- #
# Mixin：任务级跳过 / 重试 / 成功处理
# ---------------------------------------------------------------------- #
class _TaskSkipMixin:
    """任务级跳过预检共享逻辑。

    将"上游被跳过/失败"与"条件不满足"两类跳过判断统一为单一入口，
    被 :class:`SyncTaskRunner` 与 :class:`AsyncTaskRunner` 复用。
    """

    @staticmethod
    def _upstream_skip_reason(spec: TaskSpec[Any], report: RunReport | None) -> str | None:
        """硬依赖被 SKIPPED/FAILED 时返回原因字符串，否则 ``None``。

        软依赖不影响本检查——软依赖被跳过时注入默认值。
        """
        if report is None or spec.allow_upstream_skip:
            return None
        for dep in spec.depends_on:
            if dep not in report.results:
                continue
            dep_status = report.results[dep].status
            if dep_status in (TaskStatus.SKIPPED, TaskStatus.FAILED):
                return f"上游任务 '{dep}' 状态为 {dep_status.value}"
        return None

    @staticmethod
    def _prepare_for_execution(
        spec: TaskSpec[Any],
        context: Mapping[str, Any],
        report: RunReport | None,
        on_event: EventCallback | None,
    ) -> TaskResult[Any] | None:
        """执行前预检：上游跳过 / 条件跳过。

        返回 SKIPPED TaskResult 或 ``None``（继续执行）。
        条件判断委托给 :meth:`TaskSpec.should_execute`，避免重复实现。
        """
        # 1. 上游被跳过/失败
        skip_reason = _TaskSkipMixin._upstream_skip_reason(spec, report)
        # 2. 条件 / skip_if_missing（单一来源：TaskSpec.should_execute）
        if skip_reason is None:
            should_run, cond_reason = spec.should_execute(context)
            if not should_run:
                skip_reason = cond_reason or "条件不满足"
        if skip_reason is None:
            return None
        # 构造 SKIPPED 结果
        result: TaskResult[Any] = TaskResult(
            spec=spec,
            status=TaskStatus.SKIPPED,
            finished_at=datetime.now(),
            reason=skip_reason,
        )
        _emit(on_event, result)
        logger.info("task %r skipped (%s)", spec.name, skip_reason)
        return result


class _TaskRetryMixin:
    """任务级重试决策与失败/成功后处理共享逻辑。"""

    @staticmethod
    def _should_retry(spec: TaskSpec[Any], attempts: int, exc: BaseException) -> bool:
        """是否应继续重试。"""
        return attempts < spec.retry.max_attempts and spec.retry.should_retry(exc)

    @staticmethod
    def _mark_success(spec: TaskSpec[Any], result: TaskResult[Any], value: Any) -> None:
        """标记任务成功并触发 post_run 钩子。"""
        result.value = value
        result.status = TaskStatus.SUCCESS
        result.finished_at = datetime.now()
        _run_hooks(spec.hooks, "post_run", spec, value)

    @staticmethod
    def _finalize_failure(
        result: TaskResult[Any],
        layer_idx: int | None,
        on_event: EventCallback | None,
        continue_on_error: bool,
    ) -> None:
        """标记任务为 FAILED。若 ``continue_on_error`` 为真则不抛出异常。"""
        result.status = TaskStatus.FAILED
        result.finished_at = datetime.now()
        _emit(on_event, result)
        if continue_on_error:
            logger.warning(
                "task %r failed but continue_on_error=True; continuing.",
                result.spec.name,
            )
            return
        raise TaskFailedError(
            task=result.spec.name,
            cause=result.error if result.error is not None else RuntimeError("unknown"),
            attempts=result.attempts,
            layer=layer_idx,
        )

    @staticmethod
    def _handle_failure(
        spec: TaskSpec[Any],
        result: TaskResult[Any],
        exc: BaseException,
        layer_idx: int | None,
        on_event: EventCallback | None,
    ) -> bool:
        """统一处理失败：超时转换、重试决策、finalize。

        Returns
        -------
        bool
            ``True`` 表示已 finalize（不再重试）；``False`` 表示应继续重试。
        """
        # asyncio.TimeoutError → TaskTimeoutError（统一异常类型）
        if isinstance(exc, asyncio.TimeoutError):
            exc = TaskTimeoutError(spec.name, spec.timeout or 0.0)
            logger.warning(
                "task %r timed out (attempt %d/%d); retrying",
                spec.name,
                result.attempts,
                spec.retry.max_attempts,
            )
        else:
            logger.warning(
                "task %r failed (attempt %d/%d): %r; retrying",
                spec.name,
                result.attempts,
                spec.retry.max_attempts,
                exc,
            )
        result.error = exc
        if _TaskRetryMixin._should_retry(spec, result.attempts, exc):
            return False
        _run_hooks(spec.hooks, "on_failure", spec, exc)
        _TaskRetryMixin._finalize_failure(result, layer_idx, on_event, spec.continue_on_error)
        return True


# ---------------------------------------------------------------------- #
# 任务执行器：同步 / 异步（复用 _TaskSkipMixin + _TaskRetryMixin）
# ---------------------------------------------------------------------- #
class SyncTaskRunner(_TaskSkipMixin, _TaskRetryMixin):
    """同步任务执行器：带重试与跳过预检。"""

    @staticmethod
    def run(
        spec: TaskSpec[Any],
        context: Mapping[str, Any],
        layer_idx: int | None,
        on_event: EventCallback | None = None,
        report: RunReport | None = None,
    ) -> TaskResult[Any]:
        skipped = _TaskSkipMixin._prepare_for_execution(spec, context, report, on_event)
        if skipped is not None:
            return skipped

        result: TaskResult[Any] = TaskResult(spec=spec)
        result.started_at = datetime.now()
        args, kwargs = build_call_args(spec, context)

        _run_hooks(spec.hooks, "pre_run", spec)

        while True:
            result.attempts += 1
            try:
                with spec.env_context():
                    value = spec.effective_fn(*args, **kwargs)
                _TaskRetryMixin._mark_success(spec, result, value)
                return result
            except Exception as exc:
                if _TaskRetryMixin._handle_failure(spec, result, exc, layer_idx, on_event):
                    return result
                wait = spec.retry.wait_seconds(result.attempts)
                if wait > 0:
                    time.sleep(wait)


class AsyncTaskRunner(_TaskSkipMixin, _TaskRetryMixin):
    """异步任务执行器：在事件循环上运行同步或异步任务，带重试与跳过预检。"""

    @staticmethod
    async def run(
        spec: TaskSpec[Any],
        context: Mapping[str, Any],
        layer_idx: int | None,
        on_event: EventCallback | None = None,
        report: RunReport | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> TaskResult[Any]:
        skipped = _TaskSkipMixin._prepare_for_execution(spec, context, report, on_event)
        if skipped is not None:
            return skipped

        async def _inner() -> TaskResult[Any]:
            result: TaskResult[Any] = TaskResult(spec=spec)
            result.started_at = datetime.now()
            args, kwargs = build_call_args(spec, context)
            loop = asyncio.get_event_loop()

            _run_hooks(spec.hooks, "pre_run", spec)

            while True:
                result.attempts += 1
                try:
                    value = await _execute_async_task(spec, args, kwargs, loop)
                    _TaskRetryMixin._mark_success(spec, result, value)
                    return result
                except Exception as exc:
                    if _TaskRetryMixin._handle_failure(spec, result, exc, layer_idx, on_event):
                        return result
                    wait = spec.retry.wait_seconds(result.attempts)
                    if wait > 0:
                        await asyncio.sleep(wait)

        if semaphore is not None:
            async with semaphore:
                return await _inner()
        return await _inner()


async def _execute_async_task(
    spec: TaskSpec[Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    loop: asyncio.AbstractEventLoop,
) -> Any:
    """执行异步或同步任务（带超时处理）。"""
    if _is_async_fn(spec):
        coro = cast(Awaitable[Any], spec.effective_fn(*args, **kwargs))
        if spec.timeout is not None:
            return await asyncio.wait_for(coro, timeout=spec.timeout)
        return await coro

    def fn_call() -> Any:
        with spec.env_context():
            return spec.effective_fn(*args, **kwargs)

    if spec.timeout is not None:
        return await asyncio.wait_for(loop.run_in_executor(None, fn_call), timeout=spec.timeout)
    return await loop.run_in_executor(None, fn_call)


# ---------------------------------------------------------------------- #
# Mixin：层执行共享逻辑
# ---------------------------------------------------------------------- #
class _LayerMixin:
    """层执行共享逻辑：缓存过滤、优先级排序、信号量构建、结果存储。

    四个层执行器（sequential/threaded/async/dependency）通过组合此 Mixin
    消除"过滤缓存→排序→运行→存结果"的样板代码。
    """

    @staticmethod
    def _filter_and_sort(
        layer: list[str],
        graph: Graph,
        context: dict[str, Any],
        report: RunReport,
        backend: StateBackend,
        on_event: EventCallback | None,
    ) -> list[str]:
        """过滤掉已命中缓存的任务，按优先级排序返回待运行列表。"""
        to_run: list[str] = []
        for name in layer:
            spec = graph.resolved_spec(name)
            if not _apply_cached(name, spec, context, report, backend, on_event):
                to_run.append(name)
        return _sort_by_priority(to_run, graph)

    @staticmethod
    def _store_result(
        name: str,
        result: TaskResult[Any],
        graph: Graph,
        context: dict[str, Any],
        report: RunReport,
        backend: StateBackend,
        on_event: EventCallback | None,
        context_snapshot: Mapping[str, Any] | None = None,
    ) -> None:
        """存储任务结果到 context/report/backend 并触发事件。"""
        context[name] = result.value
        if result.status == TaskStatus.SUCCESS:
            spec = graph.resolved_spec(name)
            task_ctx = _build_context(spec, context_snapshot if context_snapshot is not None else context, report)
            backend.save(spec.storage_key(task_ctx), result.value)
        report.results[name] = result
        _emit(on_event, result)

    @staticmethod
    def _build_semaphores(
        to_run: list[str],
        graph: Graph,
        sem_factory: Callable[[int], Any],
        concurrency_limits: Mapping[str, int],
    ) -> dict[str, Any]:
        """为每个 ``concurrency_key`` 创建一个信号量。"""
        semaphores: dict[str, Any] = {}
        for name in to_run:
            spec = graph.resolved_spec(name)
            key = spec.concurrency_key
            if key is not None and key not in semaphores:
                limit = concurrency_limits.get(key, 1)
                semaphores[key] = sem_factory(limit)
        return semaphores

    @staticmethod
    def _get_sem(semaphores: Mapping[str, Any], spec: TaskSpec[Any]) -> Any | None:
        """获取任务对应的信号量（无 concurrency_key 则返回 None）。"""
        if spec.concurrency_key is None:
            return None
        return semaphores.get(spec.concurrency_key)


# ---------------------------------------------------------------------- #
# 层执行器
# ---------------------------------------------------------------------- #
class SequentialLayerRunner(_LayerMixin):
    """逐个运行某层的任务（按优先级排序）。"""

    @staticmethod
    def execute(
        layer: list[str],
        graph: Graph,
        context: dict[str, Any],
        report: RunReport,
        backend: StateBackend,
        layer_idx: int,
        on_event: EventCallback | None,
    ) -> None:
        for name in SequentialLayerRunner._filter_and_sort(layer, graph, context, report, backend, on_event):
            spec = graph.resolved_spec(name)
            task_ctx = _build_context(spec, context, report)
            result = SyncTaskRunner.run(spec, task_ctx, layer_idx, on_event, report)
            SequentialLayerRunner._store_result(name, result, graph, context, report, backend, on_event)


class ThreadedLayerRunner(_LayerMixin):
    """在线程池中并发运行某层的任务。"""

    @staticmethod
    def execute(
        layer: list[str],
        graph: Graph,
        context: dict[str, Any],
        report: RunReport,
        backend: StateBackend,
        layer_idx: int,
        on_event: EventCallback | None,
        max_workers: int,
        concurrency_limits: Mapping[str, int],
    ) -> None:
        to_run = ThreadedLayerRunner._filter_and_sort(layer, graph, context, report, backend, on_event)
        if not to_run:
            return
        semaphores = ThreadedLayerRunner._build_semaphores(to_run, graph, threading.Semaphore, concurrency_limits)
        context_snapshot = dict(context)
        lock = threading.Lock()

        def _run_threaded_task(name: str) -> TaskResult[Any]:
            spec = graph.resolved_spec(name)
            task_ctx = _build_context(spec, context_snapshot, report)
            sem = ThreadedLayerRunner._get_sem(semaphores, spec)
            if sem is not None:
                sem.acquire()
            try:
                return SyncTaskRunner.run(spec, task_ctx, layer_idx, on_event, report)
            finally:
                if sem is not None:
                    sem.release()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_name: dict[concurrent.futures.Future[TaskResult[Any]], str] = {
                pool.submit(_run_threaded_task, name): name for name in to_run
            }
            completed: dict[str, TaskResult[Any]] = {}
            try:
                for fut in concurrent.futures.as_completed(future_to_name):
                    name = future_to_name[fut]
                    completed[name] = fut.result()
            finally:
                with lock:
                    for name, result in completed.items():
                        ThreadedLayerRunner._store_result(
                            name, result, graph, context, report, backend, on_event, context_snapshot
                        )


class AsyncLayerRunner(_LayerMixin):
    """在事件循环上并发运行某层的任务。"""

    @staticmethod
    async def execute(
        layer: list[str],
        graph: Graph,
        context: dict[str, Any],
        report: RunReport,
        backend: StateBackend,
        layer_idx: int,
        on_event: EventCallback | None,
        concurrency_limits: Mapping[str, int],
    ) -> None:
        to_run = AsyncLayerRunner._filter_and_sort(layer, graph, context, report, backend, on_event)
        if not to_run:
            return
        semaphores = AsyncLayerRunner._build_semaphores(to_run, graph, asyncio.Semaphore, concurrency_limits)
        context_snapshot = dict(context)

        async def _run_async_task(name: str) -> TaskResult[Any]:
            spec = graph.resolved_spec(name)
            task_ctx = _build_context(spec, context_snapshot, report)
            sem = AsyncLayerRunner._get_sem(semaphores, spec)
            return await AsyncTaskRunner.run(spec, task_ctx, layer_idx, on_event, report, sem)

        results = await asyncio.gather(*[_run_async_task(name) for name in to_run])
        for name, result in zip(to_run, results):
            AsyncLayerRunner._store_result(name, result, graph, context, report, backend, on_event, context_snapshot)


class DependencyRunner(_LayerMixin):
    """依赖驱动调度：任务在硬/软依赖完成后立即启动，无层屏障。

    所有任务通过 asyncio 并发调度。同步任务卸载到线程池。
    """

    @staticmethod
    async def execute(
        graph: Graph,
        context: dict[str, Any],
        report: RunReport,
        backend: StateBackend,
        on_event: EventCallback | None,
        concurrency_limits: Mapping[str, int],
    ) -> None:
        all_names = list(graph.all_specs().keys())
        semaphores = DependencyRunner._build_semaphores(all_names, graph, asyncio.Semaphore, concurrency_limits)
        futures: dict[str, asyncio.Future[TaskResult[Any]]] = {}

        async def _run_task(name: str) -> TaskResult[Any]:
            spec = graph.resolved_spec(name)
            # 等待所有硬依赖完成
            for dep in spec.depends_on:
                if dep in futures:
                    await futures[dep]
            # 等待所有软依赖完成（但不检查其状态）
            for dep in spec.soft_depends_on:
                if dep in futures:
                    await futures[dep]

            task_ctx = _build_context(spec, context, report)
            if _apply_cached(name, spec, context, report, backend, on_event):
                return report.results[name]

            sem = DependencyRunner._get_sem(semaphores, spec)
            result = await AsyncTaskRunner.run(spec, task_ctx, None, on_event, report, sem)
            DependencyRunner._store_result(name, result, graph, context, report, backend, on_event)
            return result

        loop = asyncio.get_event_loop()
        for name in all_names:
            futures[name] = loop.create_task(_run_task(name))
        await asyncio.gather(*futures.values())


# ---------------------------------------------------------------------- #
# 公共 API
# ---------------------------------------------------------------------- #
def _make_verbose_callback(on_event: EventCallback | None) -> EventCallback:
    """包装 on_event 回调, 在 verbose 模式下打印任务生命周期。"""

    def _verbose_callback(event: TaskEvent) -> None:
        dur = f" ({event.duration:.3f}s)" if event.duration is not None else ""
        if event.status == TaskStatus.RUNNING:  # pragma: no cover
            print(f"[verbose] 任务 {event.task!r} 开始执行...", flush=True)
        elif event.status == TaskStatus.SUCCESS:
            print(f"[verbose] 任务 {event.task!r} 成功{dur}", flush=True)
        elif event.status == TaskStatus.FAILED:
            err = f": {event.error}" if event.error else ""
            print(
                f"[verbose] 任务 {event.task!r} 失败{dur} (尝试 {event.attempts} 次){err}",
                flush=True,
            )
        elif event.status == TaskStatus.SKIPPED:
            reason = f" ({event.reason})" if event.reason else ""
            print(f"[verbose] 任务 {event.task!r} 跳过{reason}", flush=True)
        if on_event is not None:
            on_event(event)

    return _verbose_callback


def run(
    graph: Graph,
    strategy: Strategy = "sequential",
    *,
    max_workers: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    on_event: EventCallback | None = None,
    state: StateBackend | None = None,
    concurrency_limits: Mapping[str, int] | None = None,
) -> RunReport:
    """执行图并返回 :class:`RunReport`。

    参数
    ----
    graph:
        待执行的已校验 :class:`Graph`。
    strategy:
        执行策略: ``"sequential"`` / ``"thread"`` / ``"async"`` /
        ``"dependency"``。``"dependency"`` 为依赖驱动调度，无层屏障。
    max_workers:
        ``"thread"`` 的线程池大小。默认 ``min(32, len(layer))``。
    dry_run:
        若为 ``True``，打印执行计划并返回空报告，不执行任务。
    verbose:
        若为 ``True``, 打印任务生命周期到 stdout。
    on_event:
        可选回调，在每次状态转换时调用。
    state:
        可选 :class:`StateBackend`，用于断点续跑。
    concurrency_limits:
        ``{concurrency_key: max_concurrent}`` 映射。具有相同
        ``concurrency_key`` 的任务共享信号量，限制同时运行实例数。

    抛出
    ----
    ValueError
        ``strategy`` 不被识别时。
    TaskFailedError
        任何任务耗尽重试后仍失败时（除非 ``continue_on_error=True``）。
    """
    graph.validate()
    layers = graph.layers()

    if dry_run:
        _print_dry_run(graph, layers)
        return RunReport(success=True)

    effective_callback: EventCallback | None = _make_verbose_callback(on_event) if verbose else on_event
    backend = resolve_backend(state)
    report = RunReport()
    context: dict[str, Any] = {}
    limits = concurrency_limits or {}

    try:
        if strategy == "sequential":
            _drive_sequential(graph, layers, context, report, backend, effective_callback)
        elif strategy == "thread":
            _drive_threaded(graph, layers, context, report, backend, effective_callback, max_workers, limits)
        elif strategy == "async":
            asyncio.run(_async_drive(graph, layers, context, report, backend, effective_callback, limits))
        elif strategy == "dependency":
            asyncio.run(DependencyRunner.execute(graph, context, report, backend, effective_callback, limits))
        else:
            raise ValueError(f"Unknown strategy: {strategy!r}")
    except TaskFailedError:
        report.success = False
        raise

    return report


def _print_dry_run(graph: Graph, layers: list[list[str]]) -> None:
    """打印执行计划但不运行任何任务。"""
    print(f"Dry run: {len(graph)} tasks, {len(layers)} layers")
    for idx, layer in enumerate(layers, 1):
        print(f"  Layer {idx}: {layer}")
        for name in layer:
            print(f"    - {describe_injection(graph.resolved_spec(name))}")


def _drive_sequential(
    graph: Graph,
    layers: list[list[str]],
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: EventCallback | None,
) -> None:
    for idx, layer in enumerate(layers, 1):
        SequentialLayerRunner.execute(layer, graph, context, report, backend, idx, on_event)


def _drive_threaded(
    graph: Graph,
    layers: list[list[str]],
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: EventCallback | None,
    max_workers: int | None,
    concurrency_limits: Mapping[str, int],
) -> None:
    for idx, layer in enumerate(layers, 1):
        workers = max_workers or max(1, min(32, len(layer)))
        ThreadedLayerRunner.execute(layer, graph, context, report, backend, idx, on_event, workers, concurrency_limits)


async def _async_drive(
    graph: Graph,
    layers: list[list[str]],
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: EventCallback | None,
    concurrency_limits: Mapping[str, int],
) -> None:
    for idx, layer in enumerate(layers, 1):
        await AsyncLayerRunner.execute(layer, graph, context, report, backend, idx, on_event, concurrency_limits)
