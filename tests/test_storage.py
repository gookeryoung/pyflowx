"""状态后端测试。"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import pytest

from pyflowx.errors import StorageError
from pyflowx.storage import JSONBackend, MemoryBackend, StateBackend, resolve_backend


# ---------------------------------------------------------------------- #
# MemoryBackend
# ---------------------------------------------------------------------- #
def test_memory_backend_lifecycle() -> None:
    b = MemoryBackend()
    assert not b.has("a")
    b.save("a", 1)
    assert b.has("a")
    assert b.get("a") == 1
    assert dict(b.load()) == {"a": 1}
    b.clear()
    assert not b.has("a")
    assert dict(b.load()) == {}


def test_memory_backend_get_missing_raises() -> None:
    b = MemoryBackend()
    with pytest.raises(KeyError):
        b.get("nope")


# ---------------------------------------------------------------------- #
# JSONBackend
# ---------------------------------------------------------------------- #
def test_json_backend_save_and_load() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")
        b = JSONBackend(path)
        b.save("a", {"x": 1})
        b.save("b", [1, 2, 3])
        # 重新打开应读到已保存内容
        b2 = JSONBackend(path)
        assert b2.has("a")
        assert b2.get("a") == {"x": 1}
        assert b2.get("b") == [1, 2, 3]
        assert dict(b2.load()) == {"a": {"x": 1}, "b": [1, 2, 3]}


def test_json_backend_clear() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")
        b = JSONBackend(path)
        b.save("a", 1)
        b.clear()
        assert not b.has("a")
        # 文件应被写入空 dict
        with open(path, "r", encoding="utf-8") as fh:
            assert json.load(fh) == {}


def test_json_backend_nonexistent_file_starts_empty() -> None:
    """文件不存在时应正常初始化为空。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "absent.json")
        b = JSONBackend(path)
        assert dict(b.load()) == {}
        assert not b.has("anything")


def test_json_backend_non_serialisable_raises() -> None:
    """不可 JSON 序列化的值应抛 StorageError，且不污染内存状态。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")
        b = JSONBackend(path)
        with pytest.raises(StorageError):
            b.save("a", object())  # object() 不可序列化
        assert not b.has("a")


def test_json_backend_flush_type_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """_flush 时 json.dump 抛 TypeError 应转为 StorageError（覆盖 line 105-106）。

    通过 monkeypatch 让 json.dump 在写入文件时抛 TypeError，模拟值通过
    save 的 dumps 校验但在 dump 到文件句柄时失败（如自定义对象的边缘情况）。
    """
    import json as _json

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")
        b = JSONBackend(path)

        original_dump = _json.dump

        def flaky_dump(*args: Any, **kwargs: Any) -> None:
            raise TypeError("simulated flush failure")

        monkeypatch.setattr(_json, "dump", flaky_dump)
        with pytest.raises(StorageError, match="cannot write"):
            b.save("a", 1)
        # 恢复以便后续测试不受影响
        monkeypatch.setattr(_json, "dump", original_dump)


def test_json_backend_flush_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """_flush 时 OSError 应转为 StorageError。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")
        b = JSONBackend(path)

        original_replace = os.replace

        def fail_replace(*args: Any, **kwargs: Any) -> None:
            raise OSError("simulated os.replace failure")

        monkeypatch.setattr(os, "replace", fail_replace)
        with pytest.raises(StorageError, match="cannot write"):
            b.save("a", 1)
        monkeypatch.setattr(os, "replace", original_replace)


def test_json_backend_corrupt_file_raises() -> None:
    """损坏的 JSON 文件应抛 StorageError。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not valid json")
        with pytest.raises(StorageError):
            JSONBackend(path)


def test_json_backend_non_dict_content_ignored() -> None:
    """文件内容是合法 JSON 但非 dict 时应被忽略（保持空）。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([1, 2, 3], fh)  # list 而非 dict
        b = JSONBackend(path)
        assert dict(b.load()) == {}


# ---------------------------------------------------------------------- #
# resolve_backend
# ---------------------------------------------------------------------- #
def test_resolve_backend_returns_input() -> None:
    b = MemoryBackend()
    assert resolve_backend(b) is b


def test_resolve_backend_creates_memory_when_none() -> None:
    b = resolve_backend(None)
    assert isinstance(b, MemoryBackend)


def test_state_backend_is_abstract() -> None:
    """StateBackend 是 ABC，不能直接实例化。"""
    with pytest.raises(TypeError):
        StateBackend()  # type: ignore[abstract]
