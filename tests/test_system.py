"""Tests for tasks/system.py."""

import os
import subprocess
from pathlib import Path

import pytest

from pyflowx.conditions import Constants
from pyflowx.tasks.system import clr, reset_icon_cache, setenv, setenv_group, which, write_file


def test_clr_creates_task_spec() -> None:
    """clr() 应创建 TaskSpec。"""
    spec = clr()
    assert spec.name == "clear_screen"
    assert spec.fn is not None


def test_clr_executes_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """clr() 在 Linux 上应执行 clear 命令。"""
    monkeypatch.setattr(Constants, "IS_WINDOWS", False)
    monkeypatch.setattr(Constants, "IS_LINUX", True)

    # Mock subprocess.run
    ran = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *cmd, **__: ran.append(cmd),
    )

    spec = clr()
    assert spec.fn is not None
    spec.fn()
    assert ran == [(["clear"],)]


def test_clr_executes_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """clr() 在 Windows 上应执行 cls 命令。"""
    monkeypatch.setattr(Constants, "IS_WINDOWS", True)

    # Mock subprocess.run
    ran = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *cmd, **__: ran.append(cmd),
    )

    spec = clr()
    assert spec.fn is not None
    spec.fn()
    assert ran == [(["cls"],)]


def test_reset_icon_cache_non_windows(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """reset_icon_cache() 在非 Windows 上应返回空列表并打印提示。"""
    monkeypatch.setattr(Constants, "IS_WINDOWS", False)

    specs = reset_icon_cache()
    assert specs == []
    captured = capsys.readouterr()
    assert "仅在 Windows 上支持" in captured.out


def test_reset_icon_cache_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """reset_icon_cache() 在 Windows 上应返回任务列表。"""
    monkeypatch.setattr(Constants, "IS_WINDOWS", True)
    monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\test\\AppData\\Local")

    specs = reset_icon_cache()
    assert len(specs) == 4
    assert specs[0].name == "kill_explorer"
    assert specs[1].name == "delete_icon_cache"
    assert specs[2].name == "delete_icon_cache_all"
    assert specs[3].name == "restart_explorer"


def test_setenv_creates_task_spec() -> None:
    """setenv() 应创建 TaskSpec。"""
    spec = setenv("TEST_VAR", "test_value")
    assert spec.name == "setenv_test_var"
    assert spec.verbose is True


def test_setenv_sets_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """setenv() 应设置环境变量。"""
    spec = setenv("PYFLOWX_TEST_VAR_1", "test_value")
    assert spec.fn is not None
    spec.fn()
    assert os.environ["PYFLOWX_TEST_VAR_1"] == "test_value"
    # Clean up
    del os.environ["PYFLOWX_TEST_VAR_1"]


def test_setenv_default_not_overwrite(monkeypatch: pytest.MonkeyPatch) -> None:
    """setenv(default=True) 不应覆盖已存在的环境变量。"""
    os.environ["PYFLOWX_TEST_VAR_EXISTS"] = "original"
    spec = setenv("PYFLOWX_TEST_VAR_EXISTS", "new_value", default=True)
    assert spec.fn is not None
    spec.fn()
    assert os.environ["PYFLOWX_TEST_VAR_EXISTS"] == "original"
    # Clean up
    del os.environ["PYFLOWX_TEST_VAR_EXISTS"]


def test_setenv_default_sets_when_missing() -> None:
    """setenv(default=True) 应在缺失时设置环境变量。"""
    # Ensure variable does not exist
    var_name = "PYFLOWX_TEST_VAR_MISSING"
    if var_name in os.environ:
        del os.environ[var_name]

    spec = setenv(var_name, "default_value", default=True)
    assert spec.fn is not None
    spec.fn()
    assert os.environ[var_name] == "default_value"

    # Clean up after test
    del os.environ[var_name]


def test_which_creates_task_spec() -> None:
    """which() 应创建 TaskSpec。"""
    spec = which("python")
    assert spec.name == "which_python"


def test_which_linux_found(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """which() 在 Linux 上找到命令应打印路径。"""
    monkeypatch.setattr(Constants, "IS_WINDOWS", False)

    class MockResult:
        returncode = 0
        stdout = "/usr/bin/python\n"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_, **__: MockResult(),
    )

    spec = which("python")
    assert spec.fn is not None
    spec.fn()
    captured = capsys.readouterr()
    assert "python ->" in captured.out
    assert "/usr/bin/python" in captured.out


def test_which_windows_found(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """which() 在 Windows 上找到命令应打印路径。"""
    monkeypatch.setattr(Constants, "IS_WINDOWS", True)

    class MockResult:
        returncode = 0
        stdout = "C:\\Python\\python.exe\nC:\\Python\\Scripts\\python.exe\n"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_, **__: MockResult(),
    )

    spec = which("python")
    assert spec.fn is not None
    spec.fn()
    captured = capsys.readouterr()
    assert "python ->" in captured.out
    assert "C:\\Python\\python.exe" in captured.out


def test_which_not_found(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """which() 未找到命令应打印提示。"""
    monkeypatch.setattr(Constants, "IS_WINDOWS", False)

    class MockResult:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_, **__: MockResult(),
    )

    spec = which("nonexistent_cmd")
    assert spec.fn is not None
    spec.fn()
    captured = capsys.readouterr()
    assert "nonexistent_cmd -> 未找到" in captured.out


def test_write_file_creates_task_spec() -> None:
    """write_file() 应创建带 verbose 的 TaskSpec。"""
    spec = write_file("/tmp/unused", "x")
    assert spec.name == "write_file_/tmp/unused"
    assert spec.verbose is True


def test_write_file_writes_content(tmp_path: Path) -> None:
    """write_file() 应将内容写入指定文件."""
    f = tmp_path / "out.txt"
    spec = write_file(str(f), "hello world")
    assert spec.fn is not None
    spec.fn()
    assert f.read_text(encoding="utf-8") == "hello world"


def test_write_file_with_encoding(tmp_path: Path) -> None:
    """write_file() 应支持指定编码."""
    f = tmp_path / "out.txt"
    spec = write_file(str(f), "中文", encoding="utf-8")
    assert spec.fn is not None
    spec.fn()
    assert f.read_text(encoding="utf-8") == "中文"


def test_write_file_failure_propagates(tmp_path: Path) -> None:
    """write_file() 写入失败应抛出异常（不吞异常）."""
    # 父目录不存在时写入应抛 FileNotFoundError
    missing = tmp_path / "no_such_dir" / "out.txt"
    spec = write_file(str(missing), "x")
    assert spec.fn is not None
    with pytest.raises(FileNotFoundError):
        spec.fn()


def test_setenv_group_creates_specs() -> None:
    """setenv_group() 应为每个环境变量创建 TaskSpec."""
    envs = {"VAR_A": "1", "VAR_B": "2"}
    specs = setenv_group(envs)
    assert len(specs) == 2
    assert specs[0].name == "setenv_var_a"
    assert specs[1].name == "setenv_var_b"


def test_setenv_group_default_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """setenv_group(default=True) 不应覆盖已存在的环境变量."""
    monkeypatch.setenv("PYFLOWX_GROUP_EXISTS", "original")
    specs = setenv_group({"PYFLOWX_GROUP_EXISTS": "new"}, default=True)
    for spec in specs:
        assert spec.fn is not None
        spec.fn()
    assert os.environ["PYFLOWX_GROUP_EXISTS"] == "original"
