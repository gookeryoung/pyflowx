"""用于断点续跑的状态持久化后端。

:class:`StateBackend` 存储每个成功完成任务的结果。在后续运行中，
执行器向后端查询某任务是否已有存储结果；若有则跳过该任务，并将其
存储值注入下游任务。

存储键由 :meth:`TaskSpec.storage_key` 计算，默认为任务名；若任务配置
了 ``cache_key``，则键为 ``"name:cache_key_value"``，使不同输入产生
独立缓存条目。

支持 TTL：``has`` 在条目过期时返回 ``False``。
"""

from __future__ import annotations

import json
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, ContextManager, Mapping

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override  # pragma: no cover

from .errors import StorageError


class StateBackend(ABC):
    """可续跑状态存储的抽象基类。

    所有方法以 ``key`` 为参数（通常为任务名或 ``name:cache_key``）。
    """

    @abstractmethod
    def load(self) -> Mapping[str, Any]:
        """返回完整的存储映射（可能为空）。"""

    @abstractmethod
    def save(self, key: str, value: Any) -> None:
        """持久化单个任务的成功结果。"""

    @abstractmethod
    def has(self, key: str) -> bool:
        """``key`` 是否已有未过期的存储结果。"""

    @abstractmethod
    def get(self, key: str) -> Any:
        """返回 ``key`` 的存储结果（不存在则抛 ``KeyError``）。"""

    @abstractmethod
    def clear(self) -> None:
        """清除所有存储状态。"""

    def flush(self) -> None:  # noqa: B027
        """将内存中暂存的状态持久化到外部介质。

        默认无操作（如 :class:`MemoryBackend` 无需落盘）。
        :class:`JSONBackend` 在 :meth:`batch` 期间会延迟落盘，需在退出时调用。
        """

    def batch(self) -> ContextManager[None]:
        """返回一个上下文管理器，期间 :meth:`save` 可延迟 :meth:`flush`。

        默认实现为 no-op（如 :class:`MemoryBackend`）。:class:`JSONBackend`
        覆盖为：进入时标记延迟，退出时统一 flush 一次，将每任务一次落盘
        （N 次写入）降为整次运行一次（O(N) 而非 O(N²)）。
        """
        return nullcontext()


class _TTLStateBackendMixin(StateBackend):
    """TTL 状态后端共享逻辑。

    将 ``has`` / ``get`` / ``load`` / ``save`` / ``clear`` 的统一实现
    委托给四个原始存取原语：:meth:`_get_raw`、:meth:`_put_raw`、
    :meth:`_iter_raw`、:meth:`_clear_raw`，并基于 :meth:`_now` 与
    ``self._ttl`` 提供统一的过期判断 :meth:`_is_expired`。

    子类需设置 ``self._ttl`` 并实现上述四个原语；如需自定义时间源
    （如 ``time.monotonic``）可覆盖 :meth:`_now`。
    """

    _ttl: float | None

    # ---- 原语：由子类实现 ---- #
    @abstractmethod
    def _get_raw(self, key: str) -> tuple[Any, float] | None:
        """返回 ``(value, ts)``；键不存在时返回 ``None``。"""

    @abstractmethod
    def _put_raw(self, key: str, value: Any, ts: float) -> None:
        """写入一条记录。"""

    @abstractmethod
    def _iter_raw(self) -> Iterator[tuple[str, Any, float]]:
        """迭代所有记录（不做过期过滤），yield ``(key, value, ts)``。"""

    @abstractmethod
    def _clear_raw(self) -> None:
        """清空所有记录。"""

    # ---- 共享实现 ---- #
    def _now(self) -> float:
        """当前时间戳，默认为 wall-clock 秒。"""
        return time.time()

    def _is_expired(self, ts: float) -> bool:
        """时间戳 ``ts`` 是否已过期。"""
        if self._ttl is None:
            return False
        return (self._now() - ts) > self._ttl

    @override
    def load(self) -> Mapping[str, Any]:
        return {k: v for k, v, ts in self._iter_raw() if not self._is_expired(ts)}

    @override
    def save(self, key: str, value: Any) -> None:
        self._put_raw(key, value, self._now())

    @override
    def has(self, key: str) -> bool:
        entry = self._get_raw(key)
        return entry is not None and not self._is_expired(entry[1])

    @override
    def get(self, key: str) -> Any:
        entry = self._get_raw(key)
        if entry is None or self._is_expired(entry[1]):
            raise KeyError(key)
        return entry[0]

    @override
    def clear(self) -> None:
        self._clear_raw()


class MemoryBackend(_TTLStateBackendMixin):
    """进程内 dict 后端。进程退出即丢失。

    Parameters
    ----------
    ttl:
        条目存活秒数。``None`` 表示永不过期。``has`` 在条目超过 ttl 后
        返回 ``False``（但不主动删除，下次 ``save`` 覆盖）。
    """

    def __init__(self, ttl: float | None = None) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl

    @override
    def _now(self) -> float:
        return time.monotonic()

    @override
    def _get_raw(self, key: str) -> tuple[Any, float] | None:
        return self._store.get(key)

    @override
    def _put_raw(self, key: str, value: Any, ts: float) -> None:
        self._store[key] = (value, ts)

    @override
    def _iter_raw(self) -> Iterator[tuple[str, Any, float]]:
        for k, (v, ts) in self._store.items():
            yield k, v, ts

    @override
    def _clear_raw(self) -> None:
        self._store.clear()

    def _expired(self, key: str) -> bool:
        """键是否已过期（兼容旧测试 API）。"""
        entry = self._get_raw(key)
        if entry is None:
            return False
        return self._is_expired(entry[1])


class JSONBackend(_TTLStateBackendMixin):
    """基于文件的 JSON 存储，用于跨进程续跑。

    存储格式：``{key: {"value": v, "ts": epoch_seconds}}``。
    ``ts`` 用于 TTL 判断。结果必须可 JSON 序列化。

    Parameters
    ----------
    path:
        JSON 文件路径。
    ttl:
        条目存活秒数。``None`` 表示永不过期。
    """

    def __init__(self, path: str, ttl: float | None = None) -> None:
        self._path: str = path
        self._ttl = ttl
        self._store: dict[str, dict[str, Any]] = {}
        self._defer_flush: bool = False
        self._load()

    def _load(self) -> None:
        if not Path(self._path).exists():
            return
        try:
            with open(self._path, encoding="utf-8") as fh:
                data: Any = json.load(fh)
            if isinstance(data, dict):
                # 兼容纯值格式与带元数据格式
                self._store = {}
                for k, v in data.items():
                    if isinstance(v, dict) and "value" in v and "ts" in v:
                        self._store[k] = v
                    else:
                        self._store[k] = {"value": v, "ts": time.time()}
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"cannot read state file {self._path!r}", exc) from exc

    def _flush(self) -> None:
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._store, fh, ensure_ascii=False, indent=2)
            _ = Path(tmp).replace(Path(self._path))
        except (OSError, TypeError) as exc:
            raise StorageError(f"cannot write state file {self._path!r}", exc) from exc

    @override
    def _get_raw(self, key: str) -> tuple[Any, float] | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        return entry["value"], float(entry.get("ts", 0))

    @override
    def _put_raw(self, key: str, value: Any, ts: float) -> None:
        self._store[key] = {"value": value, "ts": ts}

    @override
    def _iter_raw(self) -> Iterator[tuple[str, Any, float]]:
        for k, entry in self._store.items():
            yield k, entry["value"], float(entry.get("ts", 0))

    @override
    def _clear_raw(self) -> None:
        self._store.clear()

    @override
    def clear(self) -> None:
        super().clear()
        self._flush()

    @override
    def save(self, key: str, value: Any) -> None:
        try:
            _ = json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise StorageError(f"result of key {key!r} is not JSON-serialisable", exc) from exc
        super().save(key, value)
        if not self._defer_flush:
            self._flush()

    @override
    def flush(self) -> None:
        self._flush()

    @override
    @contextmanager
    def batch(self) -> Iterator[None]:
        """进入批量模式：``save`` 暂不落盘，退出时统一 flush 一次。

        将整次运行 N 个任务的 N 次全量落盘降为 1 次。
        """
        self._defer_flush = True
        try:
            yield
        finally:
            self._defer_flush = False
            self._flush()

    def _expired(self, entry: Mapping[str, Any]) -> bool:
        """带元数据的条目是否已过期（兼容旧测试 API）。"""
        return self._is_expired(float(entry.get("ts", 0)))


def resolve_backend(backend: StateBackend | None) -> StateBackend:
    """返回 ``backend``；为 ``None`` 时返回新的 :class:`MemoryBackend`。"""
    return backend if backend is not None else MemoryBackend()
