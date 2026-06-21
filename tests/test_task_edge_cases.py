"""Tests for task module edge cases."""

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx.task import TaskSpec

# 跨平台的 echo 命令
if sys.platform == "win32":
    ECHO_CMD = ["cmd", "/c", "echo"]
else:
    ECHO_CMD = ["echo"]


def test_taskspec_wrap_cmd_with_list():
    """Test TaskSpec._wrap_cmd with command list."""
    spec = TaskSpec("test", cmd=[*ECHO_CMD, "hello"])
    wrapped_fn = spec.effective_fn
    assert wrapped_fn is not None


def test_taskspec_wrap_cmd_with_string():
    """Test TaskSpec._wrap_cmd with command string."""
    if sys.platform == "win32":
        cmd_str = "cmd /c echo hello"
    else:
        cmd_str = "echo hello"
    spec = TaskSpec("test", cmd=cmd_str)
    wrapped_fn = spec.effective_fn
    assert wrapped_fn is not None


def test_taskspec_wrap_cmd_with_timeout():
    """Test TaskSpec._wrap_cmd with timeout."""
    spec = TaskSpec("test", cmd=[*ECHO_CMD, "hello"], timeout=0.1)
    wrapped_fn = spec.effective_fn

    # Should not raise timeout error for quick command
    result = wrapped_fn()
    assert result is None


def test_taskspec_wrap_cmd_with_cwd():
    """Test TaskSpec._wrap_cmd with working directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec = TaskSpec("test", cmd=[*ECHO_CMD, "hello"], cwd=Path(tmpdir))
        wrapped_fn = spec.effective_fn
        result = wrapped_fn()
        assert result is None


def test_taskspec_wrap_cmd_verbose():
    """Test TaskSpec._wrap_cmd with verbose=True."""
    spec = TaskSpec("test", cmd=[*ECHO_CMD, "hello"], verbose=True)
    wrapped_fn = spec.effective_fn

    # Should print verbose output
    result = wrapped_fn()
    assert result is None


def test_taskspec_wrap_cmd_error():
    """Test TaskSpec._wrap_cmd handles command error."""
    spec = TaskSpec("test", cmd=["python", "-c", "import sys; sys.exit(1)"])
    wrapped_fn = spec.effective_fn

    with pytest.raises(RuntimeError, match="命令执行失败"):
        _ = wrapped_fn()


def test_taskspec_wrap_cmd_file_not_found():
    """Test TaskSpec._wrap_cmd handles file not found."""
    spec = TaskSpec("test", cmd=["nonexistent_command"])
    wrapped_fn = spec.effective_fn

    with pytest.raises(RuntimeError, match="命令未找到"):
        _ = wrapped_fn()


def test_taskspec_wrap_cmd_shell_file_not_found():
    """Test TaskSpec._wrap_cmd handles shell command file not found."""
    spec = TaskSpec("test", cmd="nonexistent_shell_command")
    wrapped_fn = spec.effective_fn

    # Shell commands don't raise FileNotFoundError
    # They just return non-zero exit code
    with pytest.raises(RuntimeError):
        _ = wrapped_fn()


def test_taskspec_no_fn_no_cmd():
    """Test TaskSpec raises error when no fn or cmd."""
    with pytest.raises(ValueError, match="必须提供 fn 或 cmd 参数"):
        _ = TaskSpec("test")


def test_taskspec_conditions_check():
    """Test TaskSpec.should_execute with conditions."""
    spec = px.TaskSpec(
        "test",
        fn=lambda: "result",
        conditions=(lambda: True,),
    )

    assert spec.should_execute() is True


def test_taskspec_conditions_false():
    """Test TaskSpec.should_execute with false conditions."""
    spec = px.TaskSpec(
        "test",
        fn=lambda: "result",
        conditions=(lambda: False,),
    )

    assert spec.should_execute() is False


def test_taskspec_conditions_multiple():
    """Test TaskSpec.should_execute with multiple conditions."""
    spec = px.TaskSpec(
        "test",
        fn=lambda: "result",
        conditions=(lambda: True, lambda: True, lambda: True),
    )

    assert spec.should_execute() is True


def test_taskspec_conditions_multiple_one_false():
    """Test TaskSpec.should_execute with one false condition."""
    spec = px.TaskSpec(
        "test",
        fn=lambda: "result",
        conditions=(lambda: True, lambda: False, lambda: True),
    )

    assert spec.should_execute() is False


def test_taskspec_list_cmd_timeout_mocked():
    """Test TaskSpec._wrap_cmd handles list command timeout (mocked)."""
    spec = TaskSpec("test", cmd=["sleep", "10"], timeout=0.1)
    wrapped_fn = spec.effective_fn

    with patch(
        "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["sleep", "10"], timeout=0.1)
    ), pytest.raises(RuntimeError, match="命令执行超时"):
        _ = wrapped_fn()


def test_taskspec_shell_cmd_timeout_mocked():
    """Test TaskSpec._wrap_cmd handles shell command timeout (mocked)."""
    spec = TaskSpec("test", cmd="sleep 10", timeout=0.1)
    wrapped_fn = spec.effective_fn

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep 10", timeout=0.1)), pytest.raises(
        RuntimeError, match="Shell 命令执行超时"
    ):
        _ = wrapped_fn()


def test_taskspec_shell_cmd_file_not_found_mocked():
    """Test TaskSpec._wrap_cmd handles shell command FileNotFoundError (mocked)."""
    spec = TaskSpec("test", cmd="nonexistent_shell_command")
    wrapped_fn = spec.effective_fn

    with patch("subprocess.run", side_effect=FileNotFoundError("not found")), pytest.raises(
        RuntimeError, match="Shell 命令未找到"
    ):
        _ = wrapped_fn()


def test_taskspec_shell_cmd_with_cwd_verbose(capsys):
    """Test TaskSpec._wrap_cmd with shell command, cwd and verbose=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        if sys.platform == "win32":
            shell_cmd = "cmd /c echo hello"
        else:
            shell_cmd = "echo hello"
        spec = TaskSpec("test", cmd=shell_cmd, cwd=Path(tmpdir), verbose=True)
        wrapped_fn = spec.effective_fn
        result = wrapped_fn()
        assert result is None
        captured = capsys.readouterr()
        assert "执行 Shell" in captured.out
        assert "工作目录" in captured.out


def test_taskspec_list_cmd_os_error_mocked():
    """Test TaskSpec._wrap_cmd handles list command OSError (mocked)."""
    spec = TaskSpec("test", cmd=["ls"])
    wrapped_fn = spec.effective_fn

    with patch("subprocess.run", side_effect=OSError("os error")), pytest.raises(RuntimeError, match="命令执行异常"):
        _ = wrapped_fn()


def test_taskspec_shell_cmd_os_error_mocked():
    """Test TaskSpec._wrap_cmd handles shell command OSError (mocked)."""
    spec = TaskSpec("test", cmd="ls")
    wrapped_fn = spec.effective_fn

    with patch("subprocess.run", side_effect=OSError("os error")), pytest.raises(
        RuntimeError, match="Shell 命令执行异常"
    ):
        _ = wrapped_fn()
