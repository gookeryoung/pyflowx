"""用于断点续跑的状态持久化后端。

:class:`StateBackend` 存储每个成功完成任务的结果。在后续运行中，
执行器向后端查询某任务是否已有存储结果；若有则跳过该任务，并将其
存储值注入下游任务。

本模块刻意保持最小化：仅持久化*成功*结果（失败任务会重跑），存储
形态为扁平的 ``{task_name: result}`` 映射。内置两个后端：

* :class:`MemoryBackend` —— 快速、进程内、无 I/O。默认。
* :class:`JSONBackend` —— 持久化到 JSON 文件，支持跨进程续跑。

两者均零依赖（``json`` 为标准库）。用户可子类化
:class:`StateBackend` 接入 SQLite、Redis 等。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping

from .errors import StorageError


class StateBackend(ABC):
    """可续跑状态存储的抽象基类。"""

    @abstractmethod
    def load(self) -> Mapping[str, Any]:
        """返回完整的存储映射（可能为空）。"""

    @abstractmethod
    def save(self, name: str, value: Any) -> None:
        """持久化单个任务的成功结果。"""

    @abstractmethod
    def has(self, name: str) -> bool:
        """``name`` 是否已有存储结果。"""

    @abstractmethod
    def get(self, name: str) -> Any:
        """返回 ``name`` 的存储结果（不存在则抛 ``KeyError``）。"""

    @abstractmethod
    def clear(self) -> None:
        """清除所有存储状态。"""


class MemoryBackend(StateBackend):
    """进程内 dict 后端。进程退出即丢失。"""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def load(self) -> Mapping[str, Any]:
        return dict(self._store)

    def save(self, name: str, value: Any) -> None:
        self._store[name] = value

    def has(self, name: str) -> bool:
        return name in self._store

    def get(self, name: str) -> Any:
        return self._store[name]

    def clear(self) -> None:
        self._store.clear()


class JSONBackend(StateBackend):
    """基于文件的 JSON 存储，用于跨进程续跑。

    结果必须可 JSON 序列化。不可序列化的值会抛出
    :class:`~pyflowx.errors.StorageError`（运行本身不会中止；仅该条
    结果的持久化失败）。
    """

    def __init__(self, path: str) -> None:
        self._path: str = path
        self._store: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not Path(self._path).exists():
            return
        try:
            with open(self._path, encoding="utf-8") as fh:
                data: Any = json.load(fh)
            if isinstance(data, dict):
                self._store = data
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

    def load(self) -> Mapping[str, Any]:
        return dict(self._store)

    def save(self, name: str, value: Any) -> None:
        # 在修改内存状态前先校验可序列化性。
        try:
            _ = json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise StorageError(
                f"result of task {name!r} is not JSON-serialisable", exc
            ) from exc
        self._store[name] = value
        self._flush()

    def has(self, name: str) -> bool:
        return name in self._store

    def get(self, name: str) -> Any:
        return self._store[name]

    def clear(self) -> None:
        self._store.clear()
        self._flush()


def resolve_backend(backend: StateBackend | None) -> StateBackend:
    """返回 ``backend``；为 ``None`` 时返回新的 :class:`MemoryBackend`。"""
    return backend if backend is not None else MemoryBackend()
