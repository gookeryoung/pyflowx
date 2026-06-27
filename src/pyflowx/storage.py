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
from pathlib import Path
from typing import Any, Mapping

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

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


class MemoryBackend(StateBackend):
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
    def load(self) -> Mapping[str, Any]:
        return {k: v for k, (v, _ts) in self._store.items() if not self._expired(k)}

    @override
    def save(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.monotonic())

    @override
    def has(self, key: str) -> bool:
        return key in self._store and not self._expired(key)

    @override
    def get(self, key: str) -> Any:
        if key not in self._store or self._expired(key):
            raise KeyError(key)
        return self._store[key][0]

    @override
    def clear(self) -> None:
        self._store.clear()

    def _expired(self, key: str) -> bool:
        if self._ttl is None or key not in self._store:
            return False
        _value, ts = self._store[key]
        return (time.monotonic() - ts) > self._ttl


class JSONBackend(StateBackend):
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
                        # 旧格式：纯值
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

    def _now(self) -> float:
        return time.time()

    def _expired(self, entry: dict[str, Any]) -> bool:
        if self._ttl is None:
            return False
        return (self._now() - float(entry.get("ts", 0))) > self._ttl

    @override
    def load(self) -> Mapping[str, Any]:
        return {k: v["value"] for k, v in self._store.items() if not self._expired(v)}

    @override
    def save(self, key: str, value: Any) -> None:
        try:
            _ = json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise StorageError(f"result of key {key!r} is not JSON-serialisable", exc) from exc
        self._store[key] = {"value": value, "ts": self._now()}
        self._flush()

    @override
    def has(self, key: str) -> bool:
        return key in self._store and not self._expired(self._store[key])

    @override
    def get(self, key: str) -> Any:
        if key not in self._store or self._expired(self._store[key]):
            raise KeyError(key)
        return self._store[key]["value"]

    @override
    def clear(self) -> None:
        self._store.clear()
        self._flush()


def resolve_backend(backend: StateBackend | None) -> StateBackend:
    """返回 ``backend``；为 ``None`` 时返回新的 :class:`MemoryBackend`。"""
    return backend if backend is not None else MemoryBackend()
