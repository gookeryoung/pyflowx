"""状态后端测试。"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

from pyflowx.errors import StorageError
from pyflowx.storage import JSONBackend, MemoryBackend, StateBackend, resolve_backend


@pytest.fixture
def mock_tmp_json(tmp_path: Path) -> Path:
    """模拟临时 JSON 文件。"""
    path = tmp_path / "state.json"
    path.touch()
    return path


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


def test_memory_backend_ttl_expired() -> None:
    """MemoryBackend TTL 过期后 has/get 返回 False/抛 KeyError."""
    b = MemoryBackend(ttl=0.1)  # 0.1 秒过期
    b.save("a", 1)
    assert b.has("a")
    time.sleep(0.15)
    assert not b.has("a")
    with pytest.raises(KeyError):
        b.get("a")


def test_memory_backend_ttl_load_filters_expired() -> None:
    """MemoryBackend.load() 应过滤过期的条目."""
    b = MemoryBackend(ttl=0.1)
    b.save("a", 1)
    b.save("b", 2)
    time.sleep(0.15)
    # a 过期，但 b 也要过期... 需要更精确控制
    # 使用 monkeypatch 更可控
    b._store["expired"] = ("value", time.monotonic() - 100)  # 手动设置过期时间
    b._store["fresh"] = ("value2", time.monotonic())
    assert "expired" not in dict(b.load())
    assert "fresh" in dict(b.load())


def test_memory_backend_expired_key_not_in_store() -> None:
    """不存在的键 has 返回 False."""
    b = MemoryBackend(ttl=1.0)
    assert b.has("nonexistent") is False


def test_memory_backend_no_ttl_never_expired() -> None:
    """无 TTL 时永不过期."""
    b = MemoryBackend()
    b.save("a", 1)
    b._store["a"] = (1, time.monotonic() - 1000)  # 手动设置很久以前的存储
    assert b.has("a")  # 仍然存在
    assert b.get("a") == 1


# ---------------------------------------------------------------------- #
# JSONBackend
# ---------------------------------------------------------------------- #
def test_json_backend_save_and_load() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
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
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path)
        b.save("a", 1)
        b.clear()
        assert not b.has("a")
        # 文件应被写入空 dict
        with open(path, encoding="utf-8") as fh:
            assert json.load(fh) == {}


def test_json_backend_nonexistent_file_starts_empty() -> None:
    """文件不存在时应正常初始化为空。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "absent.json")
        b = JSONBackend(path)
        assert dict(b.load()) == {}
        assert not b.has("anything")


def test_json_backend_non_serialisable_raises() -> None:
    """不可 JSON 序列化的值应抛 StorageError，且不污染内存状态。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
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
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path)

        original_dump = _json.dump

        def flaky_dump(*_args: Any, **_kwargs: Any) -> None:
            raise TypeError("simulated flush failure")

        monkeypatch.setattr(_json, "dump", flaky_dump)
        with pytest.raises(StorageError, match="cannot write"):
            b.save("a", 1)
        # 恢复以便后续测试不受影响
        monkeypatch.setattr(_json, "dump", original_dump)


def test_json_backend_flush_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """_flush 时 OSError 应转为 StorageError。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path)

        original_replace = os.replace

        def fail_replace(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("simulated os.replace failure")

        monkeypatch.setattr(Path, "replace", fail_replace)
        with pytest.raises(StorageError, match="cannot write"):
            b.save("a", 1)
        monkeypatch.setattr(os, "replace", original_replace)


def test_json_backend_corrupt_file_raises() -> None:
    """损坏的 JSON 文件应抛 StorageError。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        with open(path, "w", encoding="utf-8") as fh:
            _ = fh.write("{not valid json")
        with pytest.raises(StorageError):
            _ = JSONBackend(path)


def test_json_backend_non_dict_content_ignored(tmp_path: Path) -> None:
    """文件内容是合法 JSON 但非 dict 时应被忽略（保持空）。"""
    path = tmp_path / "state.json"
    _ = path.write_text(json.dumps([1, 2, 3]))  # list 而非 dict
    b = JSONBackend(str(path))
    assert dict(b.load()) == {}


def test_json_backend_old_format_migration(tmp_path: Path) -> None:
    """旧格式JSON（纯值）应被迁移为新格式（带ts）。"""
    path = tmp_path / "state.json"
    # 写入旧格式：纯值
    old_data = {"a": 1, "b": "value"}
    _ = path.write_text(json.dumps(old_data))

    b = JSONBackend(str(path))
    # 读取后应有ts字段
    assert "a" in b._store
    assert "value" in b._store["a"]
    assert "ts" in b._store["a"]
    assert b._store["a"]["value"] == 1


# ---------------------------------------------------------------------- #
# JSONBackend TTL 测试
# ---------------------------------------------------------------------- #
def test_json_backend_ttl_expired_has_returns_false() -> None:
    """JSONBackend TTL 过期后 has 返回 False."""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path, ttl=0.1)
        b.save("a", 1)
        assert b.has("a")
        time.sleep(0.15)
        assert not b.has("a")


def test_json_backend_ttl_expired_get_raises_keyerror() -> None:
    """JSONBackend TTL 过期后 get 抛 KeyError."""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path, ttl=0.1)
        b.save("a", 1)
        time.sleep(0.15)
        with pytest.raises(KeyError):
            b.get("a")


def test_json_backend_ttl_load_filters_expired() -> None:
    """JSONBackend.load() 应过滤过期的条目."""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path, ttl=0.1)
        b.save("a", 1)
        b.save("b", 2)
        time.sleep(0.15)
        # 两个都过期了
        assert dict(b.load()) == {}


def test_json_backend_expired_no_ttl() -> None:
    """无 TTL 时永不过期."""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path)
        b.save("a", 1)
        # 手动修改 ts 为很久以前
        b._store["a"]["ts"] = time.time() - 1000
        assert b.has("a") is True  # 无 TTL，永不过期


def test_json_backend_expired_with_ttl() -> None:
    """有 TTL 时过期键 has 返回 False."""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path, ttl=1.0)
        b.save("a", 1)
        # 手动修改 ts 为很久以前
        b._store["a"]["ts"] = time.time() - 10  # 10 秒前，超过 TTL
        assert b.has("a") is False


def test_json_backend_expired_missing_ts() -> None:
    """entry 缺少 ts 时视为过期."""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path, ttl=1.0)
        b._store["a"] = {"value": 1}  # 缺少 ts
        # ts 默认为 0，已经过了很久
        assert b.has("a") is False


def test_json_backend_save_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """save 时 json.dumps 抛 ValueError 应转为 StorageError."""
    import json as _json

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        b = JSONBackend(path)

        original_dumps = _json.dumps

        def flaky_dumps(*_args: Any, **_kwargs: Any) -> str:
            raise ValueError("simulated dumps failure")

        monkeypatch.setattr(_json, "dumps", flaky_dumps)
        with pytest.raises(StorageError, match="not JSON-serialisable"):
            b.save("a", 1)
        monkeypatch.setattr(_json, "dumps", original_dumps)


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
