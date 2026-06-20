"""Executors and the public :func:`run` entry point.

Three execution strategies share a common layer-by-layer driver:

* ``sequential`` — deterministic, one task at a time. Best for debugging.
* ``thread``     — layer-internal concurrency via a thread pool. Best for
                   I/O-bound sync tasks.
* ``async``      — layer-internal concurrency via ``asyncio.gather``.
                   Sync tasks are offloaded to a thread pool; async tasks
                   run on the event loop. Best for I/O-bound async tasks.

All three honour ``retries``, ``timeout``, context injection, state
backends (resume), and emit :class:`~pyflowx.task.TaskEvent` for observers.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, cast

from .context import build_call_args, describe_injection
from .errors import TaskFailedError, TaskTimeoutError
from .graph import Graph
from .report import RunReport
from .storage import StateBackend, resolve_backend
from .task import TaskEvent, TaskResult, TaskSpec, TaskStatus

logger = logging.getLogger("pyflowx")

# Observer callback type.
EventCallback = Callable[[TaskEvent], None]

# Strategy selector literal.
Strategy = str  # "sequential" | "thread" | "async"


def _is_async_fn(spec: TaskSpec[object]) -> bool:
    """True if ``spec.fn`` is a coroutine function."""
    return inspect.iscoroutinefunction(spec.fn)


def _emit(
    on_event: Optional[EventCallback],
    result: TaskResult[object],
) -> None:
    """Fire an observer event if a callback is registered."""
    if on_event is None:
        return
    on_event(
        TaskEvent(
            task=result.spec.name,
            status=result.status,
            attempts=result.attempts,
            error=repr(result.error) if result.error else None,
            duration=result.duration,
        )
    )


def _log_retry(
    spec: TaskSpec[object], attempts: int, max_attempts: int, exc: BaseException
) -> None:
    """记录重试日志（sync 与 async 共享，便于测试覆盖）。"""
    logger.warning(
        "task %r failed (attempt %d/%d): %r; retrying",
        spec.name,
        attempts,
        max_attempts,
        exc,
    )


def _finalize_failure(result: TaskResult[object], layer_idx: Optional[int]) -> None:
    """标记任务为 FAILED 并抛出 TaskFailedError。"""
    result.status = TaskStatus.FAILED
    result.finished_at = datetime.now()
    raise TaskFailedError(
        task=result.spec.name,
        cause=result.error if result.error is not None else RuntimeError("unknown"),
        attempts=result.attempts,
        layer=layer_idx,
    )


def _run_sync_with_retry(
    spec: TaskSpec[object],
    context: Mapping[str, Any],
    layer_idx: Optional[int],
) -> TaskResult[object]:
    """Execute a sync task with retries; return a populated TaskResult."""
    result: TaskResult[object] = TaskResult(spec=spec)
    result.started_at = datetime.now()
    max_attempts = spec.retries + 1
    args, kwargs = build_call_args(spec, context)

    while True:
        result.attempts += 1
        try:
            result.value = spec.fn(*args, **kwargs)
            result.status = TaskStatus.SUCCESS
            result.finished_at = datetime.now()
            return result
        except Exception as exc:  # noqa: BLE001 - user code may raise anything
            result.error = exc
            if result.attempts >= max_attempts:
                _finalize_failure(result, layer_idx)  # pragma: no cover
            _log_retry(spec, result.attempts, max_attempts, exc)
    raise AssertionError("unreachable")  # pragma: no cover


async def _run_async_with_retry(
    spec: TaskSpec[object],
    context: Mapping[str, Any],
    layer_idx: Optional[int],
) -> TaskResult[object]:
    """Execute a task (sync or async) on the event loop with retries."""
    result: TaskResult[object] = TaskResult(spec=spec)
    result.started_at = datetime.now()
    max_attempts = spec.retries + 1
    args, kwargs = build_call_args(spec, context)
    loop = asyncio.get_event_loop()

    while True:
        result.attempts += 1
        try:
            if _is_async_fn(spec):
                coro = cast(Awaitable[Any], spec.fn(*args, **kwargs))
                if spec.timeout is not None:
                    result.value = await asyncio.wait_for(coro, timeout=spec.timeout)
                else:
                    result.value = await coro
            else:
                # Offload sync work to a thread so the event loop stays alive.
                fn_call: Callable[[], Any] = lambda: spec.fn(*args, **kwargs)
                if spec.timeout is not None:
                    result.value = await asyncio.wait_for(
                        loop.run_in_executor(None, fn_call), timeout=spec.timeout
                    )
                else:
                    result.value = await loop.run_in_executor(None, fn_call)
            result.status = TaskStatus.SUCCESS
            result.finished_at = datetime.now()
            return result
        except asyncio.TimeoutError:
            result.error = TaskTimeoutError(spec.name, spec.timeout or 0.0)
            if result.attempts >= max_attempts:
                _finalize_failure(result, layer_idx)  # pragma: no cover
            logger.warning(
                "task %r timed out (attempt %d/%d); retrying",
                spec.name,
                result.attempts,
                max_attempts,
            )
        except Exception as exc:  # noqa: BLE001
            result.error = exc
            if result.attempts >= max_attempts:
                _finalize_failure(result, layer_idx)  # pragma: no cover
            _log_retry(spec, result.attempts, max_attempts, exc)  # pragma: no cover
    raise AssertionError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------------- #
# Layer driver
# ---------------------------------------------------------------------- #
def _build_context(
    spec: TaskSpec[object],
    global_context: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Restrict the global context to this task's dependencies."""
    return {
        dep: global_context[dep] for dep in spec.depends_on if dep in global_context
    }


def _execute_layer_sequential(
    layer: List[str],
    graph: Graph,
    context: Dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    layer_idx: int,
    on_event: Optional[EventCallback],
) -> None:
    """Run a layer's tasks one by one."""
    for name in layer:
        spec = graph.spec(name)
        if backend.has(name):
            cached = backend.get(name)
            context[name] = cached
            result = TaskResult(spec=spec, status=TaskStatus.SKIPPED, value=cached)
            report.results[name] = result
            _emit(on_event, result)
            logger.info("task %r skipped (cached)", name)
            continue
        result = _run_sync_with_retry(spec, _build_context(spec, context), layer_idx)
        context[name] = result.value
        backend.save(name, result.value)
        report.results[name] = result
        _emit(on_event, result)


def _execute_layer_threaded(
    layer: List[str],
    graph: Graph,
    context: Dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    layer_idx: int,
    on_event: Optional[EventCallback],
    max_workers: int,
) -> None:
    """Run a layer's tasks concurrently in a thread pool."""
    # First, satisfy cached tasks synchronously.
    to_run: List[str] = []
    for name in layer:
        if backend.has(name):
            cached = backend.get(name)
            context[name] = cached
            result = TaskResult(
                spec=graph.spec(name), status=TaskStatus.SKIPPED, value=cached
            )
            report.results[name] = result
            _emit(on_event, result)
        else:
            to_run.append(name)

    if not to_run:
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_name: Dict[concurrent.futures.Future[TaskResult[object]], str] = {}
        for name in to_run:
            spec = graph.spec(name)
            # Snapshot the context for this task to avoid races.
            task_ctx = _build_context(spec, context)
            fut = pool.submit(_run_sync_with_retry, spec, task_ctx, layer_idx)
            future_to_name[fut] = name

        for fut in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[fut]
            result = fut.result()  # raises TaskFailedError on failure
            context[name] = result.value
            backend.save(name, result.value)
            report.results[name] = result
            _emit(on_event, result)


async def _execute_layer_async(
    layer: List[str],
    graph: Graph,
    context: Dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    layer_idx: int,
    on_event: Optional[EventCallback],
) -> None:
    """Run a layer's tasks concurrently on the event loop."""
    to_run: List[str] = []
    for name in layer:
        if backend.has(name):
            cached = backend.get(name)
            context[name] = cached
            result = TaskResult(
                spec=graph.spec(name), status=TaskStatus.SKIPPED, value=cached
            )
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
        coros.append(_run_async_with_retry(spec, task_ctx, layer_idx))

    results = await asyncio.gather(*coros)
    for name, result in zip(to_run, results):
        context[name] = result.value
        backend.save(name, result.value)
        report.results[name] = result
        _emit(on_event, result)


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #
def run(
    graph: Graph,
    strategy: Strategy = "sequential",
    *,
    max_workers: Optional[int] = None,
    dry_run: bool = False,
    on_event: Optional[EventCallback] = None,
    state: Optional[StateBackend] = None,
) -> RunReport:
    """Execute a graph and return a :class:`RunReport`.

    Parameters
    ----------
    graph:
        The validated :class:`Graph` to execute.
    strategy:
        ``"sequential"`` (default), ``"thread"``, or ``"async"``.
    max_workers:
        Thread-pool size for ``"thread"``. Defaults to ``min(32, len(layer))``.
    dry_run:
        If ``True``, print the execution plan (layers + injection) and
        return an empty report without executing anything.
    on_event:
        Optional callback invoked on every status transition.
    state:
        Optional :class:`StateBackend` for resumable runs. Defaults to an
        in-memory backend (no persistence across processes).

    Raises
    ------
    ValueError
        If ``strategy`` is not recognised.
    TaskFailedError
        If any task fails after exhausting retries. The run aborts at the
        failing layer; tasks in later layers are not attempted.
    """
    if strategy not in ("sequential", "thread", "async"):
        raise ValueError(
            f"unknown strategy {strategy!r}; expected 'sequential', 'thread', or 'async'."
        )

    graph.validate()
    layers = graph.layers()

    if dry_run:
        _print_dry_run(graph, layers)
        return RunReport(success=True)

    backend = resolve_backend(state)
    report = RunReport()
    context: Dict[str, Any] = {}

    try:
        if strategy == "sequential":
            _drive_sequential(graph, layers, context, report, backend, on_event)
        elif strategy == "thread":
            _drive_threaded(
                graph, layers, context, report, backend, on_event, max_workers
            )
        else:
            _drive_async(graph, layers, context, report, backend, on_event)
    except TaskFailedError:
        report.success = False
        raise

    return report


def _print_dry_run(graph: Graph, layers: List[List[str]]) -> None:
    """Print the execution plan without running anything."""
    print(f"Dry run: {len(graph)} tasks, {len(layers)} layers")
    for idx, layer in enumerate(layers, 1):
        print(f"  Layer {idx}: {layer}")
        for name in layer:
            print(f"    - {describe_injection(graph.spec(name))}")


def _drive_sequential(
    graph: Graph,
    layers: List[List[str]],
    context: Dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: Optional[EventCallback],
) -> None:
    for idx, layer in enumerate(layers, 1):
        _execute_layer_sequential(layer, graph, context, report, backend, idx, on_event)


def _drive_threaded(
    graph: Graph,
    layers: List[List[str]],
    context: Dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: Optional[EventCallback],
    max_workers: Optional[int],
) -> None:
    for idx, layer in enumerate(layers, 1):
        workers = max_workers or max(1, min(32, len(layer)))
        _execute_layer_threaded(
            layer, graph, context, report, backend, idx, on_event, workers
        )


def _drive_async(
    graph: Graph,
    layers: List[List[str]],
    context: Dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: Optional[EventCallback],
) -> None:
    asyncio.run(_async_drive(graph, layers, context, report, backend, on_event))


async def _async_drive(
    graph: Graph,
    layers: List[List[str]],
    context: Dict[str, Any],
    report: RunReport,
    backend: StateBackend,
    on_event: Optional[EventCallback],
) -> None:
    for idx, layer in enumerate(layers, 1):
        await _execute_layer_async(
            layer, graph, context, report, backend, idx, on_event
        )
