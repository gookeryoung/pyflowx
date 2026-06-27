"""执行器与公共 :func:`run` 入口。

四种执行策略：

* ``sequential`` —— 确定性、一次一个任务。最适合调试。
* ``thread``     —— 通过线程池实现层内并发。最适合 I/O 密集型同步任务。
* ``async``      —— 通过 ``asyncio.gather`` 实现层内并发。同步任务被
                    卸载到线程池；异步任务运行在事件循环上。最适合
                    I/O 密集型异步任务。
* ``dependency`` —— 依赖驱动调度：任务在其所有硬依赖完成后立即启动，
                    无需等待同层其他任务。最大化并行度。

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
# 辅助
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


def _log_retry(spec: TaskSpec[Any], attempt: int, max_attempts: int, exc: BaseException) -> None:
    """记录重试日志。"""
    logger.warning(
        "task %r failed (attempt %d/%d): %r; retrying",
        spec.name,
        attempt,
        max_attempts,
        exc,
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


def _check_upstream_skipped(
    spec: TaskSpec[Any],
    report: RunReport | None,
) -> tuple[bool, str | None]:
    """检查硬依赖上游任务是否被 SKIPPED 或 FAILED。

    软依赖不影响本检查——软依赖被跳过时注入默认值。
    """
    if report is None:  # pragma: no cover
        return False, None  # pragma: no cover

    if spec.allow_upstream_skip:  # pragma: no cover
        return False, None  # pragma: no cover

    for dep in spec.depends_on:
        if dep not in report.results:  # pragma: no cover
            continue  # pragma: no cover
        dep_status = report.results[dep].status
        if dep_status in (TaskStatus.SKIPPED, TaskStatus.FAILED):
            return True, f"上游任务 '{dep}' 状态为 {dep_status.value}"
    return False, None  # pragma: no cover


def _evaluate_conditions(spec: TaskSpec[Any], context: Mapping[str, Any]) -> str | None:
    """求值所有条件，返回跳过原因或 ``None``。

    条件接收上下文映射（硬依赖 + 软依赖结果）。
    """
    failed_conditions: list[str] = []
    for condition in spec.conditions:
        try:
            ok = condition(context)
        except Exception:
            ok = False
            name = getattr(condition, "__name__", None) or "匿名条件(执行错误)"
            failed_conditions.append(name)
            continue

        if not ok:
            failed_conditions.append(getattr(condition, "__name__", None) or "匿名条件")

    if failed_conditions:
        if len(failed_conditions) <= 2:
            return f"条件不满足: {', '.join(failed_conditions)}"
        return f"条件不满足: {', '.join(failed_conditions[:2])} 等{len(failed_conditions)}个条件"

    if spec.skip_if_missing and not spec._is_cmd_available():
        cmd_name = spec.cmd[0] if isinstance(spec.cmd, list) and spec.cmd else "unknown"
        return f"命令不存在: {cmd_name}"

    return None


def _make_skipped_result(
    spec: TaskSpec[Any],
    reason: str,
    on_event: EventCallback | None,
) -> TaskResult[Any]:
    """构造 SKIPPED 的 TaskResult。"""
    result: TaskResult[Any] = TaskResult(
        spec=spec,
        status=TaskStatus.SKIPPED,
        finished_at=datetime.now(),
        reason=reason,
    )
    _emit(on_event, result)
    if spec.verbose:
        print(f"[skip] 任务 '{spec.name}' 跳过: {reason}", flush=True)
    logger.info("task %r skipped (%s)", spec.name, reason)
    return result


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
        elif dep in spec.defaults:  # pragma: no cover
            ctx[dep] = spec.defaults[dep]  # pragma: no cover
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


def _prepare_for_execution(
    spec: TaskSpec[Any],
    context: Mapping[str, Any],
    report: RunReport | None,
    on_event: EventCallback | None,
) -> TaskResult[Any] | None:
    """执行前预检：上游跳过 / 条件跳过。

    返回 SKIPPED TaskResult 或 ``None``（继续执行）。
    """
    should_skip, skip_reason = _check_upstream_skipped(spec, report)
    if should_skip:
        return _make_skipped_result(spec, skip_reason or "上游任务被跳过", on_event)

    skip_reason = _evaluate_conditions(spec, context)
    if skip_reason is not None:
        return _make_skipped_result(spec, skip_reason, on_event)

    return None


def _finalize_failure(
    result: TaskResult[Any],
    layer_idx: int | None,
    on_event: EventCallback | None = None,
    continue_on_error: bool = False,
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


def _sleep_for_retry(spec: TaskSpec[Any], attempt: int) -> None:
    """重试前的同步等待。"""
    wait = spec.retry.wait_seconds(attempt)
    if wait > 0:
        import time

        time.sleep(wait)


async def _async_sleep_for_retry(spec: TaskSpec[Any], attempt: int) -> None:
    """重试前的异步等待。"""
    wait = spec.retry.wait_seconds(attempt)
    if wait > 0:
        await asyncio.sleep(wait)


# ---------------------------------------------------------------------- #
# 同步执行内核
# ---------------------------------------------------------------------- #
def _run_sync_with_retry(
    spec: TaskSpec[Any],
    context: Mapping[str, Any],
    layer_idx: int | None,
    on_event: EventCallback | None = None,
    report: RunReport | None = None,
) -> TaskResult[Any]:
    """执行同步任务并带重试；返回填充好的 TaskResult。"""
    skipped = _prepare_for_execution(spec, context, report, on_event)
    if skipped is not None:
        return skipped

    result: TaskResult[Any] = TaskResult(spec=spec)
    result.started_at = datetime.now()
    max_attempts = spec.retry.max_attempts
    args, kwargs = build_call_args(spec, context)

    _run_hooks(spec.hooks, "pre_run", spec)

    while True:
        result.attempts += 1
        try:
            with spec.env_context():
                result.value = spec.effective_fn(*args, **kwargs)
            result.status = TaskStatus.SUCCESS
            result.finished_at = datetime.now()
            _run_hooks(spec.hooks, "post_run", spec, result.value)
            return result
        except Exception as exc:
            result.error = exc
            if result.attempts >= max_attempts or not spec.retry.should_retry(exc):
                _run_hooks(spec.hooks, "on_failure", spec, exc)
                _finalize_failure(result, layer_idx, on_event, spec.continue_on_error)
                return result
            _log_retry(spec, result.attempts, max_attempts, exc)
            _sleep_for_retry(spec, result.attempts)
    # pragma: no cover


# ---------------------------------------------------------------------- #
# 异步执行内核
# ---------------------------------------------------------------------- #
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
        else:
            return await coro
    else:

        def fn_call() -> Any:
            with spec.env_context():
                return spec.effective_fn(*args, **kwargs)

        if spec.timeout is not None:
            return await asyncio.wait_for(loop.run_in_executor(None, fn_call), timeout=spec.timeout)
        else:
            return await loop.run_in_executor(None, fn_call)


async def _run_async_with_retry(
    spec: TaskSpec[Any],
    context: Mapping[str, Any],
    layer_idx: int | None,
    on_event: EventCallback | None = None,
    report: RunReport | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> TaskResult[Any]:
    """在事件循环上执行任务（同步或异步）并带重试。"""
    skipped = _prepare_for_execution(spec, context, report, on_event)
    if skipped is not None:
        return skipped

    if semaphore is not None:
        async with semaphore:
            return await _run_async_inner(spec, context, layer_idx, on_event, report)
    return await _run_async_inner(spec, context, layer_idx, on_event, report)


async def _run_async_inner(
    spec: TaskSpec[Any],
    context: Mapping[str, Any],
    layer_idx: int | None,
    on_event: EventCallback | None = None,
    report: RunReport | None = None,  # noqa: ARG001
) -> TaskResult[Any]:
    """异步执行内核的内部实现（已获取 semaphore 后）。"""
    result: TaskResult[Any] = TaskResult(spec=spec)
    result.started_at = datetime.now()
    max_attempts = spec.retry.max_attempts
    args, kwargs = build_call_args(spec, context)
    loop = asyncio.get_event_loop()

    _run_hooks(spec.hooks, "pre_run", spec)

    while True:
        result.attempts += 1
        try:
            result.value = await _execute_async_task(spec, args, kwargs, loop)
            result.status = TaskStatus.SUCCESS
            result.finished_at = datetime.now()
            _run_hooks(spec.hooks, "post_run", spec, result.value)
            return result
        except asyncio.TimeoutError:
            exc: BaseException = TaskTimeoutError(spec.name, spec.timeout or 0.0)
            result.error = exc
            if result.attempts >= max_attempts or not spec.retry.should_retry(exc):
                _run_hooks(spec.hooks, "on_failure", spec, exc)
                _finalize_failure(result, layer_idx, on_event, spec.continue_on_error)
                return result
            logger.warning(
                "task %r timed out (attempt %d/%d); retrying",
                spec.name,
                result.attempts,
                max_attempts,
            )
            await _async_sleep_for_retry(spec, result.attempts)
        except Exception as exc:
            result.error = exc
            if result.attempts >= max_attempts or not spec.retry.should_retry(exc):
                _run_hooks(spec.hooks, "on_failure", spec, exc)
                _finalize_failure(result, layer_idx, on_event, spec.continue_on_error)
                return result
            _log_retry(spec, result.attempts, max_attempts, exc)
            await _async_sleep_for_retry(spec, result.attempts)
    # pragma: no cover


# ---------------------------------------------------------------------- #
# 层执行器
# ---------------------------------------------------------------------- #
def _sort_by_priority(layer: list[str], graph: Graph) -> list[str]:
    """按优先级降序排序（稳定排序）。"""
    return sorted(layer, key=lambda n: -graph.resolved_spec(n).priority)


def _execute_layer_sequential(
    layer: list[str],
    graph: Graph,
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    layer_idx: int,
    on_event: EventCallback | None,
) -> None:
    """逐个运行某层的任务（按优先级排序）。"""
    for name in _sort_by_priority(layer, graph):
        spec = graph.resolved_spec(name)
        if _apply_cached(name, spec, context, report, backend, on_event):
            continue
        task_ctx = _build_context(spec, context, report)
        result = _run_sync_with_retry(spec, task_ctx, layer_idx, on_event, report)
        context[name] = result.value
        if result.status == TaskStatus.SUCCESS:
            backend.save(spec.storage_key(task_ctx), result.value)
        report.results[name] = result
        _emit(on_event, result)


def _execute_layer_threaded(
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
    """在线程池中并发运行某层的任务。"""
    to_run: list[str] = []
    for name in layer:
        spec = graph.resolved_spec(name)
        task_ctx = _build_context(spec, context, report)
        if _apply_cached(name, spec, context, report, backend, on_event):
            continue
        to_run.append(name)

    if not to_run:
        return

    to_run = _sort_by_priority(to_run, graph)

    # 为每个 concurrency_key 创建线程信号量
    semaphores: dict[str, threading.Semaphore] = {}
    for name in to_run:
        spec = graph.resolved_spec(name)
        key = spec.concurrency_key
        if key is not None and key not in semaphores:
            limit = concurrency_limits.get(key, 1)
            semaphores[key] = threading.Semaphore(limit)

    context_snapshot = dict(context)
    lock = threading.Lock()

    def _run_threaded_task(name: str) -> TaskResult[Any]:
        spec = graph.resolved_spec(name)
        task_ctx = _build_context(spec, context_snapshot, report)
        sem = semaphores.get(spec.concurrency_key) if spec.concurrency_key else None
        if sem is not None:
            sem.acquire()
        try:
            return _run_sync_with_retry(spec, task_ctx, layer_idx, on_event, report)
        finally:
            if sem is not None:
                sem.release()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_name: dict[concurrent.futures.Future[TaskResult[Any]], str] = {}
        for name in to_run:
            fut = pool.submit(_run_threaded_task, name)
            future_to_name[fut] = name

        completed: dict[str, TaskResult[Any]] = {}
        try:
            for fut in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[fut]
                result = fut.result()
                completed[name] = result
        finally:
            with lock:
                for name, result in completed.items():
                    context[name] = result.value
                    if result.status == TaskStatus.SUCCESS:
                        spec = graph.resolved_spec(name)
                        task_ctx = _build_context(spec, context_snapshot, report)
                        backend.save(spec.storage_key(task_ctx), result.value)
                    report.results[name] = result
                    _emit(on_event, result)


async def _execute_layer_async(
    layer: list[str],
    graph: Graph,
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    layer_idx: int,
    on_event: EventCallback | None,
    concurrency_limits: Mapping[str, int],
) -> None:
    """在事件循环上并发运行某层的任务。"""
    to_run: list[str] = []
    for name in layer:
        spec = graph.resolved_spec(name)
        if _apply_cached(name, spec, context, report, backend, on_event):
            continue
        to_run.append(name)

    if not to_run:
        return

    to_run = _sort_by_priority(to_run, graph)

    # 为每个 concurrency_key 创建异步信号量
    semaphores: dict[str, asyncio.Semaphore] = {}
    for name in to_run:
        spec = graph.resolved_spec(name)
        key = spec.concurrency_key
        if key is not None and key not in semaphores:
            limit = concurrency_limits.get(key, 1)
            semaphores[key] = asyncio.Semaphore(limit)

    context_snapshot = dict(context)

    async def _run_async_task_wrapped(name: str) -> TaskResult[Any]:
        spec = graph.resolved_spec(name)
        task_ctx = _build_context(spec, context_snapshot, report)
        sem = semaphores.get(spec.concurrency_key) if spec.concurrency_key else None
        if sem is not None:
            async with sem:
                return await _run_async_with_retry(spec, task_ctx, layer_idx, on_event, report)
        return await _run_async_with_retry(spec, task_ctx, layer_idx, on_event, report)

    coros = [_run_async_task_wrapped(name) for name in to_run]
    results = await asyncio.gather(*coros)
    for name, result in zip(to_run, results):
        context[name] = result.value
        if result.status == TaskStatus.SUCCESS:
            spec = graph.resolved_spec(name)
            task_ctx = _build_context(spec, context_snapshot, report)
            backend.save(spec.storage_key(task_ctx), result.value)
        report.results[name] = result
        _emit(on_event, result)


# ---------------------------------------------------------------------- #
# 依赖驱动调度
# ---------------------------------------------------------------------- #
async def _drive_dependency_async(
    graph: Graph,
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: EventCallback | None,
    concurrency_limits: Mapping[str, int],
) -> None:
    """依赖驱动调度：任务在硬依赖完成后立即启动，无层屏障。

    所有任务通过 asyncio 并发调度。同步任务卸载到线程池。
    """
    all_names = set(graph.all_specs().keys())
    semaphores: dict[str, asyncio.Semaphore] = {}
    for name in all_names:
        spec = graph.resolved_spec(name)
        key = spec.concurrency_key
        if key is not None and key not in semaphores:
            limit = concurrency_limits.get(key, 1)
            semaphores[key] = asyncio.Semaphore(limit)

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

        sem = semaphores.get(spec.concurrency_key) if spec.concurrency_key else None
        if sem is not None:
            async with sem:
                result = await _run_async_with_retry(spec, task_ctx, None, on_event, report)
        else:
            result = await _run_async_with_retry(spec, task_ctx, None, on_event, report)

        context[name] = result.value
        if result.status == TaskStatus.SUCCESS:
            backend.save(spec.storage_key(task_ctx), result.value)
        report.results[name] = result
        _emit(on_event, result)
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
            _drive_async(graph, layers, context, report, backend, effective_callback, limits)
        elif strategy == "dependency":
            asyncio.run(_drive_dependency_async(graph, context, report, backend, effective_callback, limits))
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
        _execute_layer_sequential(layer, graph, context, report, backend, idx, on_event)


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
        _execute_layer_threaded(layer, graph, context, report, backend, idx, on_event, workers, concurrency_limits)


def _drive_async(
    graph: Graph,
    layers: list[list[str]],
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: EventCallback | None,
    concurrency_limits: Mapping[str, int],
) -> None:
    asyncio.run(_async_drive(graph, layers, context, report, backend, on_event, concurrency_limits))


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
        await _execute_layer_async(layer, graph, context, report, backend, idx, on_event, concurrency_limits)
