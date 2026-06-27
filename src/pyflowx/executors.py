"""执行器与公共 :func:`run` 入口。

三种执行策略共享一个逐层驱动器：

* ``sequential`` —— 确定性、一次一个任务。最适合调试。
* ``thread``     —— 通过线程池实现层内并发。最适合 I/O 密集型同步任务。
* ``async``      —— 通过 ``asyncio.gather`` 实现层内并发。同步任务被
                    卸载到线程池；异步任务运行在事件循环上。最适合
                    I/O 密集型异步任务。

三者都遵循 ``retries``、``timeout``、上下文注入、状态后端（续跑），
并向观察者发出 :class:`~pyflowx.task.TaskEvent`。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Literal, Mapping, cast

from .context import build_call_args, describe_injection
from .errors import TaskFailedError, TaskTimeoutError
from .graph import Graph
from .report import RunReport
from .storage import StateBackend, resolve_backend
from .task import TaskEvent, TaskResult, TaskSpec, TaskStatus

logger = logging.getLogger("pyflowx")

# 观察者回调类型。
EventCallback = Callable[[TaskEvent], None]
Strategy = Literal["sequential", "thread", "async"]


def _is_async_fn(spec: TaskSpec[Any]) -> bool:
    """判断 ``spec.effective_fn`` 是否为协程函数。"""
    return inspect.iscoroutinefunction(spec.effective_fn)


def _emit(
    on_event: EventCallback | None,
    result: TaskResult[Any],
) -> None:
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


def _log_retry(spec: TaskSpec[Any], attempts: int, max_attempts: int, exc: BaseException) -> None:
    """记录重试日志（sync 与 async 共享，便于测试覆盖）。"""
    logger.warning(
        "task %r failed (attempt %d/%d): %r; retrying",
        spec.name,
        attempts,
        max_attempts,
        exc,
    )


def _finalize_failure(
    result: TaskResult[Any],
    layer_idx: int | None,
    on_event: EventCallback | None = None,
) -> None:
    """标记任务为 FAILED 并抛出 TaskFailedError。"""
    result.status = TaskStatus.FAILED
    result.finished_at = datetime.now()
    _emit(on_event, result)
    raise TaskFailedError(
        task=result.spec.name,
        cause=result.error if result.error is not None else RuntimeError("unknown"),
        attempts=result.attempts,
        layer=layer_idx,
    )


def _check_upstream_skipped(
    spec: TaskSpec[Any],
    report: RunReport | None,
) -> tuple[bool, str | None]:
    """检查上游任务是否被 SKIPPED。

    Returns
    -------
    tuple[bool, str | None]
        (是否应该跳过, 跳过原因)
    """
    if report is None:
        return False, None

    # 若任务允许上游跳过，则不检查上游状态
    if spec.allow_upstream_skip:
        return False, None

    for dep in spec.depends_on:
        if dep in report.results and report.results[dep].status == TaskStatus.SKIPPED:
            return True, f"上游任务 '{dep}' 被跳过"
    return False, None


def _check_conditions_for_skip(
    spec: TaskSpec[Any],
) -> str | None:
    """检查任务条件是否满足，返回跳过原因（如果不满足）。

    Returns
    -------
    str | None
        跳过原因，如果条件满足则返回 None
    """
    if spec.should_execute():
        return None

    # 检查是哪个条件不满足
    failed_conditions = []
    for condition in spec.conditions:
        try:
            if not condition():
                failed_conditions.append(condition.__name__ or "匿名条件")
        except Exception:
            failed_conditions.append(condition.__name__ or "匿名条件(执行错误)")

    if failed_conditions:
        return f"条件不满足: {', '.join(failed_conditions)}"
    elif spec.skip_if_missing and not spec._is_cmd_available():
        # _is_cmd_available() 仅对 list[str] 类型返回 False
        cmd_name = spec.cmd[0] if isinstance(spec.cmd, list) and spec.cmd else "unknown"
        return f"命令不存在: {cmd_name}"
    else:
        return "条件不满足"


def _run_sync_with_retry(
    spec: TaskSpec[Any],
    context: Mapping[str, Any],
    layer_idx: int | None,
    on_event: EventCallback | None = None,
    report: RunReport | None = None,
) -> TaskResult[Any]:
    """执行同步任务并带重试；返回填充好的 TaskResult。"""
    result: TaskResult[Any] = TaskResult(spec=spec)

    # 检查上游任务是否被 SKIPPED
    should_skip, skip_reason = _check_upstream_skipped(spec, report)
    if should_skip:
        result.status = TaskStatus.SKIPPED
        result.finished_at = datetime.now()
        result.reason = skip_reason
        _emit(on_event, result)
        if spec.verbose:
            print(f"[skip] 任务 '{spec.name}' 跳过: {skip_reason}", flush=True)
        logger.info("task %r skipped (上游任务被跳过)", spec.name)
        return result

    # 检查条件是否满足
    skip_reason = _check_conditions_for_skip(spec)
    if skip_reason is not None:
        result.status = TaskStatus.SKIPPED
        result.finished_at = datetime.now()
        result.reason = skip_reason
        _emit(on_event, result)
        if spec.verbose:
            print(f"[skip] 任务 '{spec.name}' 跳过: {skip_reason}", flush=True)
        logger.info("task %r skipped (条件不满足)", spec.name)
        return result

    result.started_at = datetime.now()
    max_attempts = spec.retries + 1
    args, kwargs = build_call_args(spec, context)

    while True:
        result.attempts += 1
        try:
            result.value = spec.effective_fn(*args, **kwargs)
            result.status = TaskStatus.SUCCESS
            result.finished_at = datetime.now()
            return result
        except Exception as exc:
            result.error = exc
            if result.attempts >= max_attempts:
                _finalize_failure(result, layer_idx, on_event)
            _log_retry(spec, result.attempts, max_attempts, exc)
    raise AssertionError("unreachable")  # pragma: no cover


async def _execute_async_task(
    spec: TaskSpec[Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    loop: asyncio.AbstractEventLoop,
) -> Any:
    """执行异步或同步任务（带超时处理）。

    Returns
    -------
    Any
        任务返回值
    """
    if _is_async_fn(spec):
        coro = cast(Awaitable[Any], spec.effective_fn(*args, **kwargs))
        if spec.timeout is not None:
            return await asyncio.wait_for(coro, timeout=spec.timeout)
        else:
            return await coro
    else:
        # 将同步工作卸载到线程，保持事件循环存活。
        def fn_call() -> Any:
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
) -> TaskResult[Any]:
    """在事件循环上执行任务（同步或异步）并带重试。"""
    result: TaskResult[Any] = TaskResult[Any](spec=spec)

    # 检查上游任务是否被 SKIPPED
    should_skip, skip_reason = _check_upstream_skipped(spec, report)
    if should_skip:
        result.status = TaskStatus.SKIPPED
        result.finished_at = datetime.now()
        result.reason = skip_reason
        _emit(on_event, result)
        if spec.verbose:
            print(f"[skip] 任务 '{spec.name}' 跳过: {skip_reason}", flush=True)
        logger.info("task %r skipped (上游任务被跳过)", spec.name)
        return result

    # 检查条件是否满足
    skip_reason = _check_conditions_for_skip(spec)
    if skip_reason is not None:
        result.status = TaskStatus.SKIPPED
        result.finished_at = datetime.now()
        result.reason = skip_reason
        _emit(on_event, result)
        if spec.verbose:
            print(f"[skip] 任务 '{spec.name}' 跳过: {skip_reason}", flush=True)
        logger.info("task %r skipped (条件不满足)", spec.name)
        return result

    result.started_at = datetime.now()
    max_attempts = spec.retries + 1
    args, kwargs = build_call_args(spec, context)
    loop = asyncio.get_event_loop()

    while True:
        result.attempts += 1
        try:
            result.value = await _execute_async_task(spec, args, kwargs, loop)
            result.status = TaskStatus.SUCCESS
            result.finished_at = datetime.now()
            return result
        except asyncio.TimeoutError:
            result.error = TaskTimeoutError(spec.name, spec.timeout or 0.0)
            if result.attempts >= max_attempts:
                _finalize_failure(result, layer_idx, on_event)
            logger.warning(
                "task %r timed out (attempt %d/%d); retrying",
                spec.name,
                result.attempts,
                max_attempts,
            )
        except Exception as exc:
            result.error = exc
            if result.attempts >= max_attempts:
                _finalize_failure(result, layer_idx, on_event)
            _log_retry(spec, result.attempts, max_attempts, exc)
    raise AssertionError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------------- #
# 层驱动器
# ---------------------------------------------------------------------- #
def _build_context(
    spec: TaskSpec[Any],
    global_context: Mapping[str, Any],
) -> Mapping[str, Any]:
    """将全局上下文限制为本任务的依赖。"""
    return {dep: global_context[dep] for dep in spec.depends_on if dep in global_context}


def _execute_layer_sequential(
    layer: list[str],
    graph: Graph,
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    layer_idx: int,
    on_event: EventCallback | None,
) -> None:
    """逐个运行某层的任务。"""
    for name in layer:
        spec = graph.spec(name)
        if backend.has(name):
            cached = backend.get(name)
            context[name] = cached
            result = TaskResult(spec=spec, status=TaskStatus.SKIPPED, value=cached, reason="缓存命中")
            report.results[name] = result
            _emit(on_event, result)
            logger.info("task %r skipped (cached)", name)
            continue
        result = _run_sync_with_retry(spec, _build_context(spec, context), layer_idx, on_event, report)
        context[name] = result.value
        backend.save(name, result.value)
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
) -> None:
    """在线程池中并发运行某层的任务。"""
    # 先同步满足已缓存任务。
    to_run: list[str] = []
    for name in layer:
        if backend.has(name):
            cached = backend.get(name)
            context[name] = cached
            result = TaskResult(spec=graph.spec(name), status=TaskStatus.SKIPPED, value=cached, reason="缓存命中")
            report.results[name] = result
            _emit(on_event, result)
        else:
            to_run.append(name)

    if not to_run:
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_name: dict[concurrent.futures.Future[TaskResult[Any]], str] = {}
        for name in to_run:
            spec = graph.spec(name)
            # 为本任务快照上下文以避免竞态。
            task_ctx = _build_context(spec, context)
            fut = pool.submit(_run_sync_with_retry, spec, task_ctx, layer_idx, on_event, report)
            future_to_name[fut] = name

        for fut in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[fut]
            result = fut.result()  # 失败时抛出 TaskFailedError
            context[name] = result.value
            backend.save(name, result.value)
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
) -> None:
    """在事件循环上并发运行某层的任务。"""
    to_run: list[str] = []
    for name in layer:
        if backend.has(name):
            cached = backend.get(name)
            context[name] = cached
            result = TaskResult(spec=graph.spec(name), status=TaskStatus.SKIPPED, value=cached, reason="缓存命中")
            report.results[name] = result
            _emit(on_event, result)
        else:
            to_run.append(name)

    if not to_run:
        return

    coros = []
    for name in to_run:
        spec = graph.spec(name)
        task_ctx = _build_context(spec, context)
        coros.append(_run_async_with_retry(spec, task_ctx, layer_idx, on_event, report))

    results = await asyncio.gather(*coros)
    for name, result in zip(to_run, results):
        context[name] = result.value
        backend.save(name, result.value)
        report.results[name] = result
        _emit(on_event, result)


# ---------------------------------------------------------------------- #
# 公共 API
# ---------------------------------------------------------------------- #
def _make_verbose_callback(
    on_event: EventCallback | None,
) -> EventCallback | None:
    """包装 on_event 回调, 在 verbose 模式下打印任务生命周期.

    Parameters
    ----------
    on_event : EventCallback | None
        用户提供的原始回调, 若为 None 则仅打印.

    Returns
    -------
    EventCallback | None
        包装后的回调.
    """

    def _verbose_callback(event: TaskEvent) -> None:
        # 先打印生命周期信息
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
        elif event.status == TaskStatus.SKIPPED:  # pragma: no branch
            reason = f" ({event.reason})" if event.reason else ""
            print(f"[verbose] 任务 {event.task!r} 跳过{reason}", flush=True)
        else:  # pragma: no cover
            # 不可达: 执行器只发出 RUNNING/SUCCESS/FAILED/SKIPPED 事件
            pass
        # 再调用用户回调
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
) -> RunReport:
    """执行图并返回 :class:`RunReport`。

    参数
    ----
    graph:
        待执行的已校验 :class:`Graph`。
    strategy:
        执行策略, 接受 :class:`Strategy` 枚举成员或字符串
        (``"sequential"`` / ``"thread"`` / ``"async"``). 默认 ``Strategy.SEQUENTIAL``.
    max_workers:
        ``"thread"`` 的线程池大小。默认 ``min(32, len(layer))``。
    dry_run:
        若为 ``True``，打印执行计划（层 + 注入）并返回空报告，不执行
        任何任务。
    verbose:
        若为 ``True``, 打印任务生命周期 (开始/成功/失败/跳过) 到 stdout.
        注意: subprocess 命令的输出由 :class:`TaskSpec` 的 ``verbose`` 字段控制.
    on_event:
        可选回调，在每次状态转换时调用。
    state:
        可选 :class:`StateBackend`，用于断点续跑。默认为内存后端
        （不跨进程持久化）。

    抛出
    ----
    ValueError
        ``strategy`` 不被识别时。
    TaskFailedError
        任何任务耗尽重试后仍失败时。运行在失败层中止；后续层的任务
        不会被执行。
    """
    graph.validate()
    layers = graph.layers()

    if dry_run:
        _print_dry_run(graph, layers)
        return RunReport(success=True)

    # verbose 模式下包装事件回调
    effective_callback: EventCallback | None = _make_verbose_callback(on_event) if verbose else on_event

    backend = resolve_backend(state)
    report = RunReport()
    context: dict[str, Any] = {}

    try:
        if strategy == "sequential":
            _drive_sequential(graph, layers, context, report, backend, effective_callback)
        elif strategy == "thread":
            _drive_threaded(graph, layers, context, report, backend, effective_callback, max_workers)
        else:
            _drive_async(graph, layers, context, report, backend, effective_callback)
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
            print(f"    - {describe_injection(graph.spec(name))}")


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
) -> None:
    for idx, layer in enumerate(layers, 1):
        workers = max_workers or max(1, min(32, len(layer)))
        _execute_layer_threaded(layer, graph, context, report, backend, idx, on_event, workers)


def _drive_async(
    graph: Graph,
    layers: list[list[str]],
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: EventCallback | None,
) -> None:
    asyncio.run(_async_drive(graph, layers, context, report, backend, on_event))


async def _async_drive(
    graph: Graph,
    layers: list[list[str]],
    context: dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: EventCallback | None,
) -> None:
    for idx, layer in enumerate(layers, 1):
        await _execute_layer_async(layer, graph, context, report, backend, idx, on_event)
