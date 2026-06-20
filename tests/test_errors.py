"""错误类型测试。"""

from __future__ import annotations

import pytest

import pyflowx as px
from pyflowx.errors import (
    CycleError,
    DuplicateTaskError,
    InjectionError,
    MissingDependencyError,
    PyFlowXError,
    StorageError,
    TaskFailedError,
    TaskTimeoutError,
)


def test_all_errors_are_pyflowx_subclass() -> None:
    assert issubclass(DuplicateTaskError, PyFlowXError)
    assert issubclass(MissingDependencyError, PyFlowXError)
    assert issubclass(CycleError, PyFlowXError)
    assert issubclass(TaskFailedError, PyFlowXError)
    assert issubclass(TaskTimeoutError, PyFlowXError)
    assert issubclass(InjectionError, PyFlowXError)
    assert issubclass(StorageError, PyFlowXError)


def test_duplicate_task_error_attributes() -> None:
    err = DuplicateTaskError("foo")
    assert err.name == "foo"
    assert "foo" in str(err)


def test_missing_dependency_error_attributes() -> None:
    err = MissingDependencyError("child", "parent")
    assert err.task == "child"
    assert err.dependency == "parent"
    assert "child" in str(err)
    assert "parent" in str(err)


def test_cycle_error_attributes() -> None:
    err = CycleError(["a", "b", "c"])
    assert err.cycle == ["a", "b", "c"]
    # 链应首尾相接展示
    assert "a -> b -> c -> a" in str(err)


def test_task_failed_error_attributes() -> None:
    cause = ValueError("boom")
    err = TaskFailedError(task="t", cause=cause, attempts=3, layer=2)
    assert err.task == "t"
    assert err.cause is cause
    assert err.attempts == 3
    assert err.layer == 2
    assert "layer 2" in str(err)


def test_task_failed_error_without_layer() -> None:
    err = TaskFailedError(task="t", cause=RuntimeError("x"), attempts=1)
    assert err.layer is None
    assert "layer" not in str(err)


def test_task_timeout_error_attributes() -> None:
    err = TaskTimeoutError(task="t", timeout=1.5)
    assert err.task == "t"
    assert err.timeout == 1.5
    assert "1.500s" in str(err)


def test_injection_error_attributes() -> None:
    err = InjectionError(task="t", detail="missing param")
    assert err.task == "t"
    assert "missing param" in str(err)


def test_storage_error_with_cause() -> None:
    cause = OSError("disk full")
    err = StorageError(detail="write failed", cause=cause)
    assert err.cause is cause
    assert "write failed" in str(err)


def test_storage_error_without_cause() -> None:
    err = StorageError(detail="bad")
    assert err.cause is None
    assert "bad" in str(err)
