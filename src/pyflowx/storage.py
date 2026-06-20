"""State persistence backends for resumable runs.

A :class:`StateBackend` stores the result of every successfully completed
task. On a subsequent run, the executor asks the backend whether a task
already has a stored result; if so, the task is skipped and its stored
value is injected into downstream tasks.

This is intentionally minimal: only *successful* results are persisted
(failed tasks are re-run), and the storage shape is a flat
``{task_name: result}`` mapping. Two backends ship in-tree:

* :class:`MemoryBackend` — fast, in-process, no I/O. Default.
* :class:`JSONBackend` — persists to a JSON file for cross-process resume.

Both are zero-dependency (``json`` is stdlib). Users can subclass
:class:`StateBackend` to plug in SQLite, Redis, etc.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Mapping, Optional

from .errors import StorageError


class StateBackend(ABC):
    """Abstract base for resumable state storage."""

    @abstractmethod
    def load(self) -> Mapping[str, Any]:
        """Return the full stored mapping (may be empty)."""

    @abstractmethod
    def save(self, name: str, value: Any) -> None:
        """Persist a single task's successful result."""

    @abstractmethod
    def has(self, name: str) -> bool:
        """Whether ``name`` has a stored result."""

    @abstractmethod
    def get(self, name: str) -> Any:
        """Return the stored result for ``name`` (raise ``KeyError`` if absent)."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all stored state."""


class MemoryBackend(StateBackend):
    """In-process dict backend. Lost when the process exits."""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

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
    """File-backed JSON storage for cross-process resume.

    Results must be JSON-serialisable. Non-serialisable values raise
    :class:`~pyflowx.errors.StorageError` (the run itself is not aborted;
    only persistence of that one result fails).
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._store: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._store = data
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"cannot read state file {self._path!r}", exc) from exc

    def _flush(self) -> None:
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._store, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except (OSError, TypeError) as exc:
            raise StorageError(f"cannot write state file {self._path!r}", exc) from exc

    def load(self) -> Mapping[str, Any]:
        return dict(self._store)

    def save(self, name: str, value: Any) -> None:
        # Validate serialisability before mutating in-memory state.
        try:
            json.dumps(value)
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


def resolve_backend(backend: Optional[StateBackend]) -> StateBackend:
    """Return ``backend`` or a fresh :class:`MemoryBackend` if ``None``."""
    return backend if backend is not None else MemoryBackend()
